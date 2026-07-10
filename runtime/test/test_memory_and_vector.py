"""
runtime/test/test_memory_and_vector.py — conversation memory + vector store
(FIXES Memory Management / Delivery Model §4 RAG).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime.conversation_memory import ConversationMemory  # noqa: E402
from runtime.embeddings import HashEmbedder, make_embedder  # noqa: E402
from runtime.vector_store import MemoryVectorStore, make_vector_store  # noqa: E402


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
