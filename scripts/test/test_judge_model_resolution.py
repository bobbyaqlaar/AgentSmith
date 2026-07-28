"""
scripts/test/test_judge_model_resolution.py — `_shared.judge_model()` resolves
the eval judge from the model registry, not from a constant of its own.

Why this is tested rather than assumed: the judge id used to be hardcoded in
this file's module, which made it a SECOND independent setting alongside the
`judge` role a tenant declares in its own models.yaml. A tenant could route its
runtime judge to one model and have its CI scorecard graded by another without
anything reporting a conflict. These lock the precedence
(env > registry > fallback) and the fail-open behaviour that keeps evals
working in a scripts-only install with no runtime/ on the path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import _shared  # noqa: E402


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_JUDGE_MODEL", raising=False)


def test_resolves_the_judge_role_from_the_framework_registry() -> None:
    """Run from the framework repo root, the `judge` role in
    runtime/models.yaml is what grades evals."""
    assert _shared._registry_judge_model() == "falcon3:3b"
    assert _shared.judge_model() == "falcon3:3b"


def test_judge_is_not_the_architect_model() -> None:
    """Judge/actor separation at the registry level: the model grading a
    rationale must not be the one that wrote it
    (runtime.judging.judge_independence_warning)."""
    from runtime.llm_gateway import load_model_registry
    from runtime.judging import judge_independence_warning

    reg = load_model_registry()
    assert (
        judge_independence_warning(
            (reg.get("architect") or {}).get("id"), (reg.get("judge") or {}).get("id")
        )
        is None
    )


def test_fallback_matches_the_registry_role() -> None:
    """The last-resort constant and the registry must not name different
    graders — that split is what reading the registry removed."""
    assert _shared.DEFAULT_JUDGE_MODEL == _shared._registry_judge_model()


def test_registry_is_readable_from_a_directly_invoked_script(tmp_path: Path) -> None:
    """The invocation that actually matters: `python3 scripts/foo.py` puts
    scripts/ on sys.path[0], NOT the repo root, so a bare `import runtime`
    fails there. Under pytest the root IS on the path, so this whole feature
    passed its tests while silently falling back to the constant in every real
    run — caught by running verify_system.py for real, not by the suite."""
    import subprocess

    probe = REPO / "scripts" / "_test_probe_judge.py"
    probe.write_text("import _shared; print(_shared._registry_judge_model())", encoding="utf-8")
    try:
        out = subprocess.run(
            [sys.executable, str(probe)], capture_output=True, text=True, cwd=REPO
        )
    finally:
        probe.unlink()
    assert out.stdout.strip() == "falcon3:3b", out.stderr[-400:]


def test_env_var_wins_over_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_JUDGE_MODEL", "qwen2.5")
    assert _shared.judge_model() == "qwen2.5"


def test_blank_env_var_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """`export AGENT_JUDGE_MODEL=` used to resolve to the empty string and be
    passed to the judge as a model id."""
    monkeypatch.setenv("AGENT_JUDGE_MODEL", "   ")
    assert _shared.judge_model() == "falcon3:3b"


def test_falls_back_when_the_registry_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scripts/ installed to ~/.agent-framework and run in a tenant repo with
    no runtime/ must still resolve a judge rather than crash."""
    monkeypatch.setattr(_shared, "_registry_judge_model", lambda: None)
    assert _shared.judge_model() == _shared.DEFAULT_JUDGE_MODEL


def test_a_tenant_judge_role_overrides_the_framework_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The point of reading the registry: a tenant that declares its own judge
    route gets its CI evals graded by that same model, with no second setting
    to keep in sync. Mirrors KYC Sentinel's models.yaml."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "models.yaml").write_text(
        "models:\n  judge:\n    id: tenant-judge-model\n    provider: ollama\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert _shared.judge_model() == "tenant-judge-model"


def test_routing_override_also_reaches_the_judge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(
        "gateway:\n  routing_overrides:\n    judge: override-judge-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert _shared.judge_model() == "override-judge-model"
