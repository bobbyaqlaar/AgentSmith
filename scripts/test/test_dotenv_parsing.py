"""
scripts/test/test_dotenv_parsing.py — .env values must not absorb inline
comments.

`OLLAMA_BASE_URL=http://localhost:11434   # intake route` set the variable to
the URL *and the comment*, so every local model call went to
`http://localhost:11434   # intake route/chat/completions` and returned
405 method not allowed. That reads like a broken endpoint, not a parse bug, and
`KEY=value  # note` is a near-universal convention — the .env was correct.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from _shared import _dotenv_value, _load_dotenv  # noqa: E402


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("http://localhost:11434   # intake route", "http://localhost:11434"),
        ("http://localhost:11434\t# tab-separated", "http://localhost:11434"),
        ("plain-value", "plain-value"),
        ("  spaced  ", "spaced"),
        ('"quoted value"', "quoted value"),
        ("'single quoted'", "single quoted"),
        # A '#' not preceded by whitespace is part of the value — URL
        # fragments and generated passwords rely on this.
        ("secret#123", "secret#123"),
        ("http://host/path#frag", "http://host/path#frag"),
        # Quoted values keep everything between the quotes, comments included.
        ('"a#b # c"', "a#b # c"),
        ('"trailing"  # note', "trailing"),
        ("", ""),
    ],
)
def test_value_parsing(raw: str, expected: str) -> None:
    assert _dotenv_value(raw) == expected


def test_the_exact_line_that_broke_the_judge(tmp_path: Path, monkeypatch) -> None:
    """End to end: the real line from KYC Sentinel's .env."""
    (tmp_path / ".env").write_text(
        "OLLAMA_BASE_URL=http://localhost:11434   # intake (sovereign) route\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    _load_dotenv(tmp_path)
    assert os_environ_value() == "http://localhost:11434"


def os_environ_value() -> str:
    import os

    return os.environ["OLLAMA_BASE_URL"]


def test_export_prefix_is_tolerated(tmp_path: Path, monkeypatch) -> None:
    """`export KEY=value` is common in files people also source from a shell."""
    (tmp_path / ".env").write_text("export SOME_TEST_VAR=abc  # note\n", encoding="utf-8")
    monkeypatch.delenv("SOME_TEST_VAR", raising=False)
    _load_dotenv(tmp_path)
    import os

    assert os.environ["SOME_TEST_VAR"] == "abc"


def test_existing_environment_still_wins(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("SOME_TEST_VAR2=from-file\n", encoding="utf-8")
    monkeypatch.setenv("SOME_TEST_VAR2", "from-env")
    _load_dotenv(tmp_path)
    import os

    assert os.environ["SOME_TEST_VAR2"] == "from-env"


# ── Ollama base URL normalisation ────────────────────────────────────────────


@pytest.mark.parametrize(
    "env,expected",
    [
        ("http://localhost:11434", "http://localhost:11434/v1"),
        ("http://localhost:11434/", "http://localhost:11434/v1"),
        ("http://localhost:11434/v1", "http://localhost:11434/v1"),
        ("http://ollama.internal:11434", "http://ollama.internal:11434/v1"),
    ],
)
def test_ollama_base_url_tolerates_both_conventions(env, expected, monkeypatch) -> None:
    """runtime/llm_gateway.py reads this variable as `${OLLAMA_BASE_URL}/v1`,
    appending the suffix itself. cost_router used it raw, so a tenant setting
    the bare host — what Ollama's own docs show — worked on the workload path
    and 404'd on the eval path. One variable must not mean two things."""
    import cost_router

    monkeypatch.setenv("OLLAMA_BASE_URL", env)
    assert cost_router._ollama_base_url() == expected


def test_ollama_base_url_defaults_without_the_variable(monkeypatch) -> None:
    import cost_router

    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    assert cost_router._ollama_base_url() == "http://localhost:11434/v1"


# ── The on-prem bundle carries its own copy of this rule ──────────────────────


def test_the_onprem_bundle_parses_values_identically() -> None:
    """`templates/onprem-deploy/scripts/_env.parse_value` duplicates
    `_dotenv_value` on purpose — that bundle is copied to a customer host,
    often air-gapped, where `scripts/` does not exist, so it cannot import
    this one.

    A deliberate duplicate still needs a drift test, the same way the
    `_FALLBACK_*` provider maps in `_shared` do. Without it the two rules can
    diverge silently, and the symptom is a deployment where a commented .env
    line produces a broken backend URL — which reads as a broken deployment,
    not a parse bug. That is the exact failure the bundle copy was fixing.
    """
    import sys
    from pathlib import Path

    from _shared import _dotenv_value

    # sys.path rather than a hand-rolled importlib loader: `_shared.load_script`
    # only reaches scripts/, and the repo forbids a second loader (see
    # test_security_registry.test_scripts_has_exactly_one_script_loader).
    root = Path(__file__).resolve().parent.parent.parent
    bundle = root / "templates" / "onprem-deploy" / "scripts"
    if str(bundle) not in sys.path:
        sys.path.insert(0, str(bundle))
    import _env as module  # type: ignore  # noqa: E402

    cases = [
        "8080  # the app port",
        "plain",
        '"quoted value"',
        "'single'",
        '"a#b # c"',
        "http://x/y#z",
        "  spaced  ",
        "#leading",
        '"unterminated',
        "",
        "value\twith\ttabs  # note",
    ]
    for raw in cases:
        assert module.parse_value(raw) == _dotenv_value(raw), (
            f"on-prem bundle disagrees with _shared on {raw!r}: "
            f"{module.parse_value(raw)!r} vs {_dotenv_value(raw)!r}"
        )
