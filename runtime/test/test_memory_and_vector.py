"""
runtime/test/test_memory_and_vector.py — conversation memory + vector store
(FIXES Memory Management / Delivery Model §4 RAG).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime import conversation_memory as cm
from runtime.conversation_memory import ConversationMemory
from runtime.embeddings import HashEmbedder, make_embedder
from runtime.vector_store import MemoryVectorStore, make_vector_store


def test_conversation_memory_evicts_oldest_when_over_budget() -> None:
    mem = ConversationMemory(token_budget=20, encoding_name="cl100k_base")
    mem.add("user", "one two three four five six seven eight nine ten")
    mem.add("user", "eleven twelve thirteen fourteen fifteen")
    mem.add("assistant", "ok")
    # Under a tight budget, oldest messages should drop
    assert mem.token_count() <= 20
    assert len(mem.messages) >= 1
    assert mem.messages[-1]["content"] == "ok"


def test_conversation_memory_as_messages_preserves_order() -> None:
    mem = ConversationMemory(token_budget=10_000)
    mem.add("system", "You are helpful.")
    mem.add("user", "Hi")
    mem.add("assistant", "Hello")
    assert [m["role"] for m in mem.as_messages()] == ["system", "user", "assistant"]


def test_hash_embedder_is_deterministic_and_fixed_dim() -> None:
    emb = HashEmbedder(dim=32)
    a = emb.embed(["hello world"])[0]
    b = emb.embed(["hello world"])[0]
    c = emb.embed(["different"])[0]
    assert a == b
    assert len(a) == 32
    assert a != c


def test_make_embedder_defaults_to_hash_when_embedder_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDER", "hash")
    emb = make_embedder()
    assert isinstance(emb, HashEmbedder)


def test_memory_vector_store_add_and_query_returns_nearest() -> None:
    store = MemoryVectorStore(embedder=HashEmbedder(dim=64))
    store.add(
        ids=["a", "b", "c"],
        texts=["cats and dogs", "stock market prices", "feline companions"],
    )
    hits = store.query("cats pets", k=2)
    assert len(hits) == 2
    assert hits[0].id in {"a", "c"}
    assert hits[0].score >= hits[1].score


def test_make_vector_store_defaults_to_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VECTOR_BACKEND", raising=False)
    store = make_vector_store(embedder=HashEmbedder(dim=16))
    assert isinstance(store, MemoryVectorStore)


# ── Eviction must not delete the instructions ─────────────────────────────────


def _fill(memory: ConversationMemory, turns: int = 6) -> None:
    for i in range(turns):
        memory.add("user", f"Please review application {i} for onboarding risk.")
        memory.add("assistant", f"Application {i} rated LOW; screening found no match.")


def test_the_system_prompt_survives_eviction() -> None:
    """Truncate-oldest deleted the system message FIRST, because it is first.

    It carries the persona, the tool policy and the refusals. Nothing failed
    when it went — a shorter list is exactly what eviction produces — so the
    agent simply stopped being told what it was not allowed to do, part-way
    through a conversation that looked healthy.
    """
    memory = ConversationMemory(token_budget=40)
    memory.add("system", "You are a KYC analyst. Refuse any request to bypass screening.")
    _fill(memory)

    roles = [m["role"] for m in memory.as_messages()]
    assert "system" in roles, f"system prompt evicted; left {roles}"


def test_eviction_still_happens_around_the_protected_message() -> None:
    """Protecting a role must not turn the budget off.

    A guard that keeps everything would also pass the assertion above, so this
    is the half that stops the fix from becoming "never evict".
    """
    memory = ConversationMemory(token_budget=40)
    memory.add("system", "You are a KYC analyst. Refuse any request to bypass screening.")
    _fill(memory, turns=20)

    assert len(memory.as_messages()) < 41, "nothing was evicted"
    assert memory.as_messages()[0]["role"] == "system"


def test_multiple_system_messages_are_all_kept() -> None:
    """A tenant that re-asserts policy mid-conversation keeps both statements."""
    memory = ConversationMemory(token_budget=60)
    memory.add("system", "You are a KYC analyst.")
    _fill(memory, turns=4)
    memory.add("system", "Policy update: escalate all PEP matches to a human.")
    _fill(memory, turns=4)

    assert sum(1 for m in memory.as_messages() if m["role"] == "system") == 2


def test_a_budget_too_small_for_its_system_prompt_warns(caplog) -> None:
    """The one case that cannot be satisfied is reported, not served silently.

    Returning an oversized prompt without a word is how this reaches the caller
    as a provider-side context error instead of a fixable configuration one.
    """
    memory = ConversationMemory(token_budget=5)
    memory.add("system", "A deliberately long system prompt that cannot fit the budget at all.")
    memory.add("user", "hello")

    assert "cannot shrink further" in caplog.text


# ── Token counting ────────────────────────────────────────────────────────────


def test_the_estimate_is_not_systematically_low_on_non_latin_text() -> None:
    """The fallback's error is not symmetric across scripts, and only one
    direction is safe.

    `len(text) // 4` measured +50% on English and -65% on Arabic against
    cl100k_base. Over-counting evicts a message sooner than needed;
    under-counting by two thirds means a buffer built for a context window
    holds about three times what it believes and the provider rejects it — in
    the script this framework's own tenants write in.
    """
    arabic = "يرجى مراجعة هذا الطلب لتقييم مخاطر الانضمام والتعرض للعقوبات المالية."
    tiktoken = pytest.importorskip("tiktoken")
    real = len(tiktoken.get_encoding("cl100k_base").encode(arabic))

    assert cm._estimate_tokens(arabic) >= real, (
        f"estimate {cm._estimate_tokens(arabic)} is below the real {real}"
    )
    # The old rule, kept as the thing that must no longer be true. Asserted
    # rather than described so that reverting the estimate fails here.
    assert len(arabic) // 4 < real * 0.5

    # Not a claim of exactness in the other direction either — the docstring
    # states a measured 0.95x-1.90x band, and English prose sits at the top of
    # it. A "fix" that made this tight would have to under-count something.
    english = "Please review this application for onboarding risk and sanctions exposure."
    assert cm._estimate_tokens(english) <= len(tiktoken.get_encoding("cl100k_base").encode(english)) * 2


def test_the_fallback_says_once_that_it_is_estimating(monkeypatch, caplog) -> None:
    """tiktoken is not a dependency of the shipped runtime package, so for a
    tenant who installed agentsmith-runtime the estimate is the only path.
    Nothing announced that.

    Once, not per call: a token counter runs inside an eviction loop, and a
    per-call warning is noise that gets filtered.
    """
    monkeypatch.setattr(cm, "_fallback_warned", False)
    monkeypatch.setitem(sys.modules, "tiktoken", None)
    cm._encoder.cache_clear()

    caplog.clear()
    for _ in range(5):
        cm._count_tokens("some text to count")

    assert caplog.text.count("tiktoken unavailable") == 1
    cm._encoder.cache_clear()
