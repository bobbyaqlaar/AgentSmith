"""
scripts/test/test_security_pack_seeding.py — post-checkout seeds the tenant
`.agent-rfc/security/` pack (TestbedFeedback-2026-07-21 G5).

The SEC-* harness has always looked for these four artifacts in a tenant
repo, but nothing put them there: a new tenant started with those controls
skipping/failing and had to discover `fixtures/security/templates/` by
reading the framework tree. The KYC Sentinel testbed hit this and ended up
hand-writing one file and shipping `|| true` in its security CI step.

Runs the real hook in a scratch repo with a fake $HOME, same approach as
test_hooks_behavior.py.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO / "hooks"
TEMPLATES_DIR = REPO / "fixtures" / "security" / "templates"

EXPECTED = {
    "agency_manifest.yaml",
    "nist_profile.yaml",
    "risk_register.yaml",
    "tool_allowlist.yaml",
}

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="git and bash required",
)


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    """An opted-in scratch repo with the framework's shared/ dir vendored
    into a fake $HOME — i.e. the state after install-ai-stack.sh ran."""
    home = tmp_path / "home"
    shared_security = home / ".agent-framework" / "shared" / "security"
    shared_security.mkdir(parents=True)
    for template in TEMPLATES_DIR.glob("*.yaml"):
        shutil.copy(template, shared_security)
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
    )


def _security_dir(repo: Path) -> Path:
    return repo / ".agent-rfc" / "security"


def test_seeds_all_four_artifacts(tenant):
    result = _run_post_checkout(tenant)
    assert result.returncode == 0, result.stderr
    seeded = {p.name for p in _security_dir(tenant).glob("*.yaml")}
    assert seeded == EXPECTED
    assert "Seeded 4 security artifact(s)" in result.stdout


def test_warns_that_seeded_files_are_placeholders(tenant):
    """A silently-seeded risk register would be worse than none — the
    tenant must be told these need real content."""
    result = _run_post_checkout(tenant)
    assert "PLACEHOLDERS" in result.stdout
    assert "run-security-checks.py" in result.stdout


def test_never_overwrites_tenant_edits(tenant):
    """The whole point: a filled-in risk register is the tenant's own
    document. A later checkout must not clobber it."""
    _run_post_checkout(tenant)
    register = _security_dir(tenant) / "risk_register.yaml"
    register.write_text("version: 1\nentries: [{id: REAL-001}]\n")

    result = _run_post_checkout(tenant)  # e.g. a branch switch

    assert register.read_text() == "version: 1\nentries: [{id: REAL-001}]\n"
    assert "Seeded" not in result.stdout  # nothing left to seed


def test_seeds_only_the_missing_files(tenant):
    _run_post_checkout(tenant)
    (_security_dir(tenant) / "tool_allowlist.yaml").unlink()

    result = _run_post_checkout(tenant)

    assert "Seeded 1 security artifact(s)" in result.stdout
    assert {p.name for p in _security_dir(tenant).glob("*.yaml")} == EXPECTED


def test_no_templates_installed_is_not_fatal(tmp_path, monkeypatch):
    """A machine whose install predates this step must still check out."""
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
    assert not (work / ".agent-rfc" / "security").exists()


def test_unopted_repo_is_not_seeded(tenant):
    """The opt-in gate still applies — an unrelated repo with history must
    not get security files written into it."""
    subprocess.run(["git", "-C", str(tenant), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(tenant), "-c", "user.email=t@e.com", "-c", "user.name=T",
         "commit", "-q", "-m", "initial"],
        check=True,
    )
    (tenant / ".agenticframework" / "enabled").unlink()
    shutil.rmtree(_security_dir(tenant), ignore_errors=True)

    result = _run_post_checkout(tenant)

    assert "not opted in" in result.stdout
    assert not _security_dir(tenant).exists()


def test_seeded_pack_satisfies_the_harness(tenant):
    """End-to-end: a freshly seeded tenant passes the artifact-presence
    controls instead of reporting them as gaps."""
    _run_post_checkout(tenant)
    for name in EXPECTED:
        content = (_security_dir(tenant) / name).read_text()
        assert "version: 1" in content
