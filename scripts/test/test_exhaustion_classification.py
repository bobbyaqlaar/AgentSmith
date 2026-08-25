"""
scripts/test/test_exhaustion_classification.py — both LLM call paths must agree
on what "the provider is exhausted" means, and must disagree on what to DO
about it.

`runtime/llm_gateway.py` degrades to the next `degrade_to` tier.
`scripts/cost_router.py` — the eval path — does not: its caller is the judge,
and a substituted grader emits confident verdicts into the same `score` field,
compared against the same threshold, gating the same merges, with nothing
downstream able to tell it happened. So it classifies identically and then
fails loudly instead.

Two definitions of "exhausted" would make that split incoherent, which is why
the markers live in one module with a version-skew fallback that is pinned here.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import cost_router  # noqa: E402
from runtime.provider_dispatch import (  # noqa: E402
    _EXHAUSTION_MARKERS,
    is_provider_exhausted,
)


def test_fallback_markers_match_the_runtime_definition() -> None:
    """The duplicate exists only as a version-skew shim; it must not drift."""
    assert cost_router._FALLBACK_EXHAUSTION_MARKERS == _EXHAUSTION_MARKERS


def test_the_error_that_started_this_is_classified() -> None:
    """The live failure: a valid key, a well-formed request, a valid model, and
    an account with no credits. It arrives as a 400, not a 401 — auth
    succeeded — so only the body distinguishes it from a malformed request."""
    exc = RuntimeError(
        'HTTP 400 from https://api.anthropic.com/v1/messages: {"type":"error",'
        '"error":{"type":"invalid_request_error","message":"Your credit balance '
        'is too low to access the Anthropic API. Please go to Plans & Billing to '
        'upgrade or purchase credits."}}'
    )
    assert is_provider_exhausted(exc)
    assert cost_router._exhausted(exc)


def test_a_bare_status_line_is_not_classifiable() -> None:
    """Why both paths must surface the response body rather than
    raise_for_status(): the marker text lives in the body. Without it this
    returns False for the one case it exists to catch — the bug that has now
    been fixed twice, once per path."""
    assert not is_provider_exhausted(RuntimeError("Client error '400 Bad Request' for url ..."))


def test_ordinary_failures_are_not_exhaustion() -> None:
    """A malformed request must stay a hard error — misclassifying it as
    exhaustion would make the gateway degrade through every tier on a bug in
    the prompt, and make the eval path report a billing problem that isn't."""
    for msg in (
        "HTTP 400: model 'typo-model-name' not found",
        "HTTP 401: invalid x-api-key",
        "connection timed out",
    ):
        assert not is_provider_exhausted(RuntimeError(msg)), msg
        assert not cost_router._exhausted(RuntimeError(msg)), msg


def test_digits_that_merely_contain_429_are_not_exhaustion() -> None:
    """`"429" in msg` matched the digits anywhere.

    A context-length error quotes the token count, and a provider error body
    quotes a request id — both routinely contain 429 as a substring. Classified
    as exhaustion, the gateway degrades through every tier on a hard user bug
    and the eval path names a billing state that does not exist.
    """
    for msg in (
        "This model's maximum context length is 8192 tokens, however you requested 14290 tokens",
        "HTTP 400 (request_id=req_4290ab): invalid 'messages[0].role'",
        "connection reset after 429 ms",
    ):
        assert not is_provider_exhausted(RuntimeError(msg)), msg
        assert not cost_router._exhausted(RuntimeError(msg)), msg


def test_a_real_throttle_is_still_exhaustion() -> None:
    """Removing the bare digits must not lose the case they were there for."""
    for msg in (
        "HTTP 429 Too Many Requests: rate limit exceeded for model gpt-4",
        "429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric 'Generate requests'",
        "Error: The model is overloaded. Please try again later.",
    ):
        assert is_provider_exhausted(RuntimeError(msg)), msg
        assert cost_router._exhausted(RuntimeError(msg)), msg


def test_a_status_code_is_believed_over_the_body() -> None:
    """An exception carrying a real 429/402 response is exhaustion even when
    its text says nothing recognisable — which is the case for a bare
    raise_for_status() on a provider that puts the reason in headers."""

    class _Response:
        def __init__(self, code: int) -> None:
            self.status_code = code

    class _StatusError(Exception):
        def __init__(self, code: int) -> None:
            super().__init__("Client error for url https://api.example.com/v1/chat")
            self.response = _Response(code)

    assert is_provider_exhausted(_StatusError(429))
    assert is_provider_exhausted(_StatusError(402))
    assert not is_provider_exhausted(_StatusError(400))


def test_classifier_survives_an_older_runtime(monkeypatch) -> None:
    """scripts/ can be newer than the pinned runtime wheel. When the shared
    helper isn't there yet, cost_router must still classify rather than raise —
    importing it as a hard dependency would turn a version skew into 'every LLM
    call fails', which is exactly how the credential-lookup regression broke
    KYC Sentinel's CI."""
    import runtime.provider_dispatch as pd

    monkeypatch.delattr(pd, "is_provider_exhausted")
    assert cost_router._exhausted(RuntimeError("credit balance is too low"))
    assert not cost_router._exhausted(RuntimeError("some other failure"))


def test_cost_router_does_not_walk_the_degrade_chain() -> None:
    """The behavioural half of the split, asserted structurally: this path must
    never consult degrade_to. If someone adds a ladder here, the judge silently
    changes model mid-scorecard and this test should stop them long enough to
    read why."""
    src = (REPO / "scripts" / "cost_router.py").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    assert "degrade_to" not in code, (
        "cost_router.py now references degrade_to — the eval judge must not "
        "fall back to another model; see the rationale at the raise site"
    )


def test_openrouter_credit_exhaustion_is_classified() -> None:
    """OpenRouter returns 402 with its own wording, which matched none of the
    original markers — so the analyst HARD-FAILED instead of degrading to the
    cheaper tier, which is the exact situation the ladder exists for.

    Caught by running KYC Sentinel's pipeline against live OpenRouter routes:
    intake and research succeeded, the analyst hit 402, and nothing degraded.
    """
    exc = RuntimeError(
        "LLM API error 402 (model='anthropic/claude-sonnet-4.5'): This request "
        "requires more credits, or fewer max_tokens. You requested up to 1024 "
        "tokens, but can only afford 402."
    )
    assert is_provider_exhausted(exc)
    assert cost_router._exhausted(exc)


def test_a_bare_status_number_is_not_a_diagnosis() -> None:
    """Why "402" is NOT a marker: the real message contains "afford 402", so a
    bare-number marker would match for the wrong reason — and would fire on any
    unrelated text that happens to contain those digits."""
    assert not is_provider_exhausted(RuntimeError("HTTP 402"))
    assert not is_provider_exhausted(RuntimeError("processed 4029 records"))
