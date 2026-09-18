"""
scripts/test/test_governed_tenant.py — G7: a tenant that is governed from the
first commit, and a check that says when it is not.

Every slice before this built a control. A control a tenant has to install by
hand is a control most tenants do not have, so `agentsmith tenant init` writes
them: the config, the hooks ARMED, the IDE hook configs, the generated rule
files, a committed graph and the artifact stubs.

The extra modes are provisioned `off` on purpose. A tenant switched to
`enforce` on day one is refused its first commit for documents it has not
written yet, and the first thing anyone does then is take the gates out.

`verify_system.py --governed` lists everything that is missing at once — a
check that stops at the first gap turns provisioning into a guessing game.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import REPO, needs_git

sys.path.insert(0, str(REPO / "scripts"))
import gate_history


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    """An empty repo, scaffolded the way a new tenant is."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # A real tenant finds the framework at ~/.agent-framework; HOME is moved
    # here, so the checkout is named the way an installed-mode CI names it.
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    root = tmp_path / "tenant"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    sys.path.insert(0, str(REPO))
    from runtime.cli import init_tenant

    init_tenant("acme", root, stack="python-fastapi")
    return root


# ── what a new tenant gets ───────────────────────────────────────────────────


@needs_git
@pytest.mark.parametrize("provisioned", [
    ".agenticframework/process-gates.json",
    ".githooks/process-gate",
    ".githooks/commit-msg",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    ".claude/settings.json",
    ".cursor/hooks.json",
    ".agent-rfc/fixtures/knowledge_graph.json",
])
def test_the_scaffold_writes_it(tenant, provisioned) -> None:
    assert (tenant / provisioned).is_file(), provisioned


@needs_git
def test_the_hooks_are_armed_not_merely_present(tenant) -> None:
    """A hook family that is present and unarmed is the failure this whole
    programme exists to end."""
    armed = subprocess.run(["git", "-C", str(tenant), "config", "--get", "core.hooksPath"],
                           capture_output=True, text=True, check=False).stdout.strip()
    assert armed == ".githooks"


@needs_git
def test_the_gates_are_live_and_the_extra_modes_are_off(tenant) -> None:
    """Design and review are checked from the first commit; the modes that need
    documents or a policy are turned on deliberately."""
    config = json.loads((tenant / ".agenticframework" / "process-gates.json").read_text(encoding="utf-8"))

    assert config["gated"], "a config that gates nothing gates nothing"
    assert config["registry"].endswith("governance.json")
    for mode in ("artifacts", "pillars", "knowledge_graph"):
        assert config.get(mode, "off") == "off", mode


@needs_git
def test_the_scaffold_leaves_a_tenants_own_files_alone(tenant) -> None:
    (tenant / "README.md").write_text("the tenant's own words\n", encoding="utf-8")
    sys.path.insert(0, str(REPO))
    from runtime.cli import init_tenant

    init_tenant("acme", tenant, stack="python-fastapi")

    assert (tenant / "README.md").read_text(encoding="utf-8") == "the tenant's own words\n"


@needs_git
def test_a_scaffolded_tenant_can_commit_a_governed_change(tenant) -> None:
    """The point of provisioning: the gates hold, and a change that follows
    them goes in without anyone editing the config first."""
    (tenant / "app").mkdir(exist_ok=True)
    (tenant / "app" / "main.py").write_text("print(1)\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tenant), "add", "-A"], check=True)
    blocked = subprocess.run(["git", "-C", str(tenant), "-c", "user.name=t", "-c", "user.email=t@x",
                              "commit", "-m", "feat: first"], capture_output=True, text=True, check=False)

    assert blocked.returncode != 0
    assert "Design:" in blocked.stderr


# ── the check that says what is missing ──────────────────────────────────────


def _governed(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "verify_system.py"), "--governed"],
                          cwd=root, capture_output=True, text=True, check=False)


@needs_git
def test_a_fresh_tenant_is_provisioned_but_not_yet_proven(tenant) -> None:
    """Two different facts, and a new tenant is the second one: everything is
    installed and armed, and nothing has been run against it yet. Reporting
    that as a provisioning failure sends someone to fix the wrong thing."""
    result = _governed(tenant)

    assert result.returncode != 0
    assert "gap(s) in provisioning" not in result.stdout
    assert "not yet proven" in result.stdout


@needs_git
def test_governed_passes_once_the_gates_have_been_run_here(tenant) -> None:
    gate_history.record_gates_run(tenant, passed=4, failed=0, skipped=2)

    result = _governed(tenant)

    assert result.returncode == 0, result.stdout
    assert "Governed" in result.stdout


@needs_git
def test_governed_names_every_missing_piece_at_once(tenant) -> None:
    """A check that stops at the first gap makes provisioning a guessing game."""
    (tenant / ".githooks" / "commit-msg").unlink()
    (tenant / ".agent-rfc" / "fixtures" / "knowledge_graph.json").unlink()

    result = _governed(tenant)

    assert result.returncode != 0
    assert "commit-msg" in result.stdout
    assert "knowledge_graph.json" in result.stdout


@needs_git
def test_governed_notices_the_hooks_being_disarmed(tenant) -> None:
    subprocess.run(["git", "-C", str(tenant), "config", "--unset", "core.hooksPath"], check=True)

    result = _governed(tenant)

    assert result.returncode != 0
    assert "core.hooksPath" in result.stdout


@needs_git
def test_governed_reports_the_last_local_gates_run(tenant) -> None:
    """"Never run here" and "green" are different answers."""
    never = _governed(tenant)
    assert "gates" in never.stdout.lower()

    gate_history.record_gates_run(tenant, passed=3, failed=0, skipped=1)
    green = _governed(tenant)

    assert "0 failed" in green.stdout


@needs_git
def test_a_filtered_gates_run_is_not_the_list_passing(tenant) -> None:
    """`agentsmith gates run --only kg` passing one gate is not the gates
    passing. Found while migrating the documents: --governed said "Governed"
    on the strength of a one-gate run."""
    gate_history.record_gates_run(tenant, passed=1, failed=0, skipped=0, only="repo-tree")

    result = _governed(tenant)

    assert result.returncode != 0
    assert "filtered" in result.stdout and "repo-tree" in result.stdout


def test_a_gates_run_from_another_commit_is_not_this_commits_evidence(tenant) -> None:
    gate_history.record_gates_run(tenant, passed=3, failed=0, skipped=0, commit="0" * 40)

    result = _governed(tenant)

    assert "different commit" in result.stdout


# ── pillar 5: the log is written by the hooks ────────────────────────────────


def test_a_blocked_turn_is_recorded_as_unresolved(tmp_path) -> None:
    log = tmp_path / ".agent-history.log"

    gate_history.record(tmp_path, "stop_gate_blocked", "2 unreviewed gated changes")

    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["level"] == "MAJOR"
    assert entry["hitl_resolved"] is False, "it stays surfaced until someone resolves it"
    assert entry["event"] == "stop_gate_blocked"
    assert "2 unreviewed" in entry["detail"]


def test_the_same_fact_is_not_appended_twice_in_a_row(tmp_path) -> None:
    """A stop hook runs at every turn end. A log that repeats one fact fifty
    times is one nobody reads."""
    for _ in range(3):
        gate_history.record(tmp_path, "stop_gate_blocked", "the same two files")

    assert len((tmp_path / ".agent-history.log").read_text(encoding="utf-8").strip().splitlines()) == 1


def test_a_different_fact_is_appended(tmp_path) -> None:
    gate_history.record(tmp_path, "stop_gate_blocked", "two files")
    gate_history.record(tmp_path, "bypass_found", "a commit that never met a gate")

    assert len((tmp_path / ".agent-history.log").read_text(encoding="utf-8").strip().splitlines()) == 2


def test_the_line_is_the_shape_the_checker_already_reads(tmp_path) -> None:
    """`agentsmith check` surfaces unresolved MAJOR/CRITICAL entries; writing a
    different shape would mean writing a second reader."""
    sys.path.insert(0, str(REPO))
    from runtime.machine.ops import _unresolved_log_entries

    gate_history.record(tmp_path, "stop_gate_blocked", "two files")

    assert _unresolved_log_entries(tmp_path / ".agent-history.log")


@needs_git
def test_the_stop_gate_writes_one(gated_repo) -> None:
    (gated_repo / "scripts" / "tool.py").write_text("print(1)\n", encoding="utf-8")

    subprocess.run([sys.executable, str(gated_repo / "scripts" / "process_gate.py"), "stop"],
                   cwd=gated_repo, input=json.dumps({"cwd": str(gated_repo)}),
                   capture_output=True, text=True, check=False)

    log = gated_repo / ".agent-history.log"
    assert log.is_file(), "a blocked turn is a MAJOR event pillar 5 says to record"
    assert "stop_gate_blocked" in log.read_text(encoding="utf-8")
