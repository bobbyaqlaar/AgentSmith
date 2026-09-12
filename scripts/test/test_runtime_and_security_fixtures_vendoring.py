"""
scripts/test/test_runtime_and_security_fixtures_vendoring.py — post-checkout
vendors runtime/ and fixtures/security/ into a fresh tenant.

Same gap as scripts/ (test_scripts_vendoring.py), found in the same pass
while working through AqlaarTeleologyStudio's CI: `run-evals.py` and
`verify_system.py --check-redaction` import `runtime.*`, and
`run-security-checks.py --mode ci/--strict` crashes outright on a missing
`fixtures/security/control_registry.json` — `_install_root()` is
file-relative and never consults $AGENTSMITH_DIR, so once vendored into a
tenant it resolves against the TENANT's own root, not the framework's.
`pip install agentsmith-runtime` is not a substitute: confirmed against
PyPI's own API, no such project is published there.

Unlike scripts/test/ (excluded — tests the framework's own provisioning
mechanics), runtime/test/ is vendored WHOLE: those suites verify the
LIBRARY's own correctness, which is genuine evidence for any tenant
depending on it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO / "hooks"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="git and bash required",
)


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    """An opted-in scratch repo with a fake vendored ~/.agent-framework/
    runtime/ and fixtures/security/, including a runtime/test/ file that
    SHOULD be vendored (unlike scripts/test/)."""
    home = tmp_path / "home"
    fw = home / ".agent-framework"
    fw_runtime = fw / "runtime"
    fw_runtime.mkdir(parents=True)
    (fw_runtime / "judging.py").write_text("# runtime.judging\n")
    (fw_runtime / "test").mkdir()
    (fw_runtime / "test" / "test_hitl_gate.py").write_text("# hitl gate test\n")
    (fw_runtime / "__pycache__").mkdir()
    (fw_runtime / "__pycache__" / "judging.cpython-311.pyc").write_bytes(b"\x00")
    # Local HITL-gate test-run scratch data — gitignored in the framework's
    # own checkout, but a plain `cp -r` from a live working tree doesn't
    # know that. Committed once into a real tenant before this exclusion
    # existed (AqlaarTeleologyStudio 85c0d1e, cleaned up in d892dff).
    (fw_runtime / ".hitl_blobs" / "acme").mkdir(parents=True)
    (fw_runtime / ".hitl_blobs" / "acme" / "some-blob.json").write_text('{"ciphertext": "x"}\n')

    fw_fixtures_security = fw / "fixtures" / "security"
    fw_fixtures_security.mkdir(parents=True)
    (fw_fixtures_security / "control_registry.json").write_text("[]\n")
    (fw_fixtures_security / "templates").mkdir()
    (fw_fixtures_security / "templates" / "risk_register.yaml").write_text("entries: []\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)

    work = tmp_path / "repo"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / ".agenticframework").mkdir()
    (work / ".agenticframework" / "enabled").touch()
    return work


def _run_post_checkout(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOKS_DIR / "post-checkout")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_vendors_runtime_including_its_test_suite(tenant):
    result = _run_post_checkout(tenant)
    assert result.returncode == 0, result.stderr
    assert (tenant / "runtime" / "judging.py").exists()
    assert (tenant / "runtime" / "test" / "test_hitl_gate.py").exists(), (
        "runtime/test/ must be vendored, unlike scripts/test/ — these suites "
        "verify the library's own correctness"
    )
    assert not any((tenant / "runtime").rglob("__pycache__"))
    assert not (tenant / "runtime" / ".hitl_blobs").exists(), (
        "local HITL-gate test-run scratch data must never be vendored into a "
        "tenant — a plain `cp -r` doesn't respect the framework's own "
        ".gitignore, so this needs its own explicit exclusion"
    )
    assert "Vendored runtime/" in result.stdout


def test_vendors_fixtures_security(tenant):
    result = _run_post_checkout(tenant)
    assert result.returncode == 0, result.stderr
    assert (tenant / "fixtures" / "security" / "control_registry.json").exists()
    assert (tenant / "fixtures" / "security" / "templates" / "risk_register.yaml").exists()
    assert "Vendored fixtures/security/" in result.stdout


def test_never_overwrites_an_existing_runtime_dir(tenant):
    runtime_dir = tenant / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "judging.py").write_text("# tenant's own patched copy\n")

    result = _run_post_checkout(tenant)

    assert (runtime_dir / "judging.py").read_text() == "# tenant's own patched copy\n"
    assert "Vendored runtime/" not in result.stdout


def test_never_overwrites_an_existing_fixtures_security_dir(tenant):
    fixtures_dir = tenant / "fixtures" / "security"
    fixtures_dir.mkdir(parents=True)
    (fixtures_dir / "control_registry.json").write_text('{"tenant": true}\n')

    result = _run_post_checkout(tenant)

    assert (fixtures_dir / "control_registry.json").read_text() == '{"tenant": true}\n'
    assert "Vendored fixtures/security/" not in result.stdout


def test_no_framework_runtime_or_fixtures_installed_is_not_fatal(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".agent-framework").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    work = tmp_path / "repo"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / ".agenticframework").mkdir()
    (work / ".agenticframework" / "enabled").touch()

    result = _run_post_checkout(work)

    assert result.returncode == 0, result.stderr
    assert not (work / "runtime").exists()
    assert not (work / "fixtures").exists()
    assert "runtime/ not vendored" in result.stdout
    assert "fixtures/security/ not vendored" in result.stdout
