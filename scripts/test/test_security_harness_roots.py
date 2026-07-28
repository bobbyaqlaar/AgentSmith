"""
scripts/test/test_security_harness_roots.py — the harness must grade the repo
it is RUN IN, not the checkout it is installed from.

The two roots are the same directory only when the framework grades itself,
which is why this went unnoticed: `_install_root()` is file-relative (correct
for the control registry and templates), and `_tenant_security_dir` was built
from it too. A tenant runs

    cd my-tenant && python3 $AGENTSMITH_DIR/scripts/run-security-checks.py --strict

so every tenant's strict security gate was resolving `.agent-rfc/security/`
inside the FRAMEWORK checkout. The pack `ai-tenant-init` seeds into a tenant
(G5) was read by nothing, and a tenant's green SEC-RISK-001 was evidence about
somebody else's repo.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _harness():
    """Load run-security-checks.py by path — its filename has dashes, so it is
    not importable as a module the normal way."""
    spec = importlib.util.spec_from_file_location(
        "run_security_checks", REPO / "scripts" / "run-security-checks.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_tenant_root_follows_cwd_not_the_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    assert harness._tenant_root() == tmp_path.resolve()
    assert harness._install_root() == REPO
    assert harness._tenant_security_dir(harness._tenant_root()) == (
        tmp_path.resolve() / ".agent-rfc" / "security"
    )


def test_tenant_root_walks_up_to_the_repo_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Same semantics as _shared._repo_root(): run from a subdirectory and the
    pack still resolves against the repo root."""
    harness = _harness()
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "workflows" / "deep"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    assert harness._tenant_root() == tmp_path.resolve()


def test_env_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    harness = _harness()
    monkeypatch.setenv("AGENTSMITH_TENANT_ROOT", str(tmp_path))
    assert harness._tenant_root() == tmp_path.resolve()


def test_framework_grading_itself_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The self-test path must keep working: run from the framework root, both
    roots agree, exactly as before."""
    harness = _harness()
    monkeypatch.delenv("AGENTSMITH_TENANT_ROOT", raising=False)
    monkeypatch.chdir(REPO)
    assert harness._tenant_root() == harness._install_root() == REPO
