"""
scripts/test/test_tenant_adopt.py — an existing repository comes under the
gates without losing what it has (.agent-rfc/designs/tenant-adopt.md).

The repository here has history, code outside the scaffold layout, its own
hooks, CI, agent rules, Claude settings and design document — each of which
`tenant init` got wrong on a real one. Everything goes through the real CLI and
the real hooks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import REPO, needs_git

pytestmark = needs_git

sys.path.insert(0, str(REPO))

OWN_RULES = "# Our rules\n\nTabs, not spaces.\n"
OWN_DESIGN = "# Legacy design\n\nWe do things our way.\n"
OWN_CI = "name: ci\non: push\njobs: {}\n"
OWN_SETTINGS = {"permissions": {"allow": ["Bash(make *)"]}}


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                          capture_output=True, text=True, check=False)


def _write(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text)


@pytest.fixture()
def legacy(tmp_path, monkeypatch):
    """A Python repository two commits old, with its own hooks at `.hooks`."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    root = tmp_path / "legacy"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    _write(root, "pyproject.toml", '[project]\nname = "legacy"\nversion = "0.1.0"\n')
    _write(root, "mypkg/__init__.py", "")
    _write(root, "mypkg/core.py", "def add(a, b):\n    return a + b\n")
    _write(root, "tests/test_core.py", "from mypkg.core import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    _write(root, "manage.py", "print('hi')\n")
    _write(root, "CLAUDE.md", OWN_RULES)
    _write(root, "docs/DESIGN.md", OWN_DESIGN)
    _write(root, ".github/workflows/ci.yml", OWN_CI)
    _write(root, ".claude/settings.json", json.dumps(OWN_SETTINGS))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "first")
    _write(root, "mypkg/util.py", "X = 1\n")
    marks = tmp_path / "marks"
    _write(root, ".hooks/pre-commit", f'#!/usr/bin/env bash\necho pre-commit >> "{marks}"\n')
    (root / ".hooks" / "pre-commit").chmod(0o755)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "second")
    _git(root, "config", "core.hooksPath", ".hooks")
    return root


def _plan(root: Path, **kw):
    from runtime.adopt import plan_adoption

    return plan_adoption("legacy", root, **kw)


def _adopt(root: Path, **kw) -> list[str]:
    from runtime.adopt import adopt

    return adopt(_plan(root, architecture="clean", **kw))


def _status(root: Path) -> str:
    return _git(root, "status", "--porcelain", "--untracked-files=all").stdout


# ── Detect, report, write nothing ────────────────────────────────────────────


def test_the_plan_finds_the_repository_as_it_is(legacy):
    plan = _plan(legacy)

    assert plan.stack == "python-fastapi"
    assert {"mypkg/**", "tests/**", "*.py"} <= set(plan.gated)
    assert ".github/**" in plan.gated
    assert "app/**" not in plan.gated, "the scaffold layout is not this repository's"
    assert plan.prior_hooks == legacy / ".hooks"
    assert plan.source_root == "mypkg/"
    actions = dict(plan.actions)
    assert actions["CLAUDE.md"] == "merge"
    assert actions[".claude/settings.json"] == "merge"
    assert actions["docs/DESIGN.md"] == "append"
    assert actions[".github/workflows/ci.yml"] == "leave"
    assert actions[".github/workflows/agentsmith-gates.yml"] == "create"
    assert actions[".agent-history.log"] == "create"
    assert any(path.startswith(".agents/skills/") and act == "create" for path, act in plan.actions), \
        "every file adopt writes is in the plan"
    assert _status(legacy) == "", "planning writes nothing"


def test_a_given_glob_replaces_detection(legacy):
    plan = _plan(legacy, gate=["mypkg/**"])
    assert "tests/**" not in plan.gated and "mypkg/**" in plan.gated and ".github/**" in plan.gated


def test_without_yes_and_no_terminal_nothing_is_written(legacy):
    result = subprocess.run(
        [sys.executable, "-m", "runtime.cli", "tenant", "adopt", "legacy", "--root", str(legacy)],
        cwd=REPO, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
        env={**os.environ},
    )

    assert result.returncode == 2, result.stdout + result.stderr
    assert "--yes" in result.stderr
    assert "CLAUDE.md" in result.stdout and "merge" in result.stdout, "the plan is printed before refusing"
    assert _status(legacy) == ""


@pytest.mark.parametrize(("state", "says"), [
    ("no-commit", "tenant init"),
    ("adopted", "already under the gates"),
    ("unfinished", "did not finish"),
    ("own-adoption-design", "move yours"),
    ("malformed-settings", "not valid JSON"),
])
def test_a_repository_adopt_is_not_for_is_refused_before_anything_is_written(tmp_path, legacy, state, says):
    from runtime.adopt import AdoptError

    root = legacy
    if state == "no-commit":
        root = tmp_path / "empty"
        root.mkdir()
        subprocess.run(["git", "init", "-q", "--template=", str(root)], check=True)
    elif state == "adopted":
        assert _adoption_commit(legacy, _adopt(legacy)).returncode == 0
    elif state == "unfinished":
        _adopt(legacy)
    elif state == "own-adoption-design":
        _write(legacy, ".agent-rfc/designs/adoption.md", "# ours\n")
    else:
        _write(legacy, ".claude/settings.json", "{not json")
    before = _status(root)
    with pytest.raises(AdoptError, match=says):
        _plan(root)
    assert _status(root) == before


# ── Merge, never skip, never overwrite ───────────────────────────────────────


def test_what_the_repository_had_is_kept_and_extended(legacy):
    _adopt(legacy)

    claude = (legacy / "CLAUDE.md").read_text()
    assert claude.startswith(OWN_RULES)
    assert "<!-- agentsmith:rules:begin" in claude and "<!-- agentsmith:rules:end -->" in claude
    settings = json.loads((legacy / ".claude/settings.json").read_text())
    assert settings["permissions"] == OWN_SETTINGS["permissions"]
    assert "PreToolUse" in settings["hooks"]
    design = (legacy / "docs/DESIGN.md").read_text()
    assert design.startswith(OWN_DESIGN)
    assert "## Architecture (target)" in design and "`mypkg/domain/`" in design
    assert (legacy / ".github/workflows/ci.yml").read_text() == OWN_CI
    assert (legacy / ".github/workflows/agentsmith-gates.yml").is_file()
    assert not (legacy / ".github/workflows/ci-python-fastapi.yml").exists()
    assert not (legacy / "scripts").exists(), "an adopted repository is not vendored into"


def test_a_rule_file_agentsmith_generated_is_regenerated_not_merged_into(legacy):
    """The old opt-in path writes the rule files whole; appending the same
    rules to one of them would carry every rule twice."""
    _write(legacy, "AGENTS.md", "# AgentSmith\n\n<!-- Auto-generated from templates/agent-rules.yaml — do not "
                                "edit this file directly. -->\nold rules\n")
    _git(legacy, "add", "AGENTS.md")
    _git(legacy, "commit", "-q", "-m", "chore: generated rules")

    plan = _plan(legacy)
    assert dict(plan.actions)["AGENTS.md"] == "regenerate"
    from runtime.adopt import adopt

    adopt(plan)
    agents = (legacy / "AGENTS.md").read_text()
    assert "old rules" not in agents and "agentsmith:rules:begin" not in agents
    assert agents.count("Auto-generated from templates/agent-rules.yaml") == 1


def test_the_rules_block_is_replaced_not_repeated():
    from runtime.adopt import merge_rules_block

    once = merge_rules_block(OWN_RULES, "rules v1\n")
    twice = merge_rules_block(once, "rules v2\n")

    assert twice.count("agentsmith:rules:begin") == 1
    assert "rules v2" in twice and "rules v1" not in twice and twice.startswith(OWN_RULES)


def test_the_gates_are_armed_and_the_old_hooks_chained(legacy):
    _adopt(legacy)

    assert _git(legacy, "config", "--get", "core.hooksPath").stdout.strip() == ".githooks"
    assert _git(legacy, "config", "--get", "agentsmith.chainHooksPath").stdout.strip() == str(legacy / ".hooks")
    config = json.loads((legacy / ".agenticframework/process-gates.json").read_text())
    assert "mypkg/**" in config["gated"]
    assert config["pillars"] == "off"


def test_the_gates_workflow_runs_the_gate_from_a_framework_checkout(legacy):
    _adopt(legacy, framework_ref="v9.9.9")

    workflow = (legacy / ".github/workflows/agentsmith-gates.yml").read_text()
    assert 'ref: "v9.9.9"' in workflow
    assert "secrets.AGENTSMITH_READ_TOKEN" in workflow
    assert "process_gate.py ci" in workflow and "send_dev_record.py" in workflow
    assert "{{FRAMEWORK_REF}}" not in workflow


# ── The adoption commit, and after it ────────────────────────────────────────


def _adoption_commit(root: Path, written: list[str]) -> subprocess.CompletedProcess:
    from runtime.adopt import ADOPTION_DESIGN

    _git(root, "add", "--", *written)
    return _git(root, "commit", "-m", "chore: adopt AgentSmith gates",
                "-m", f"Design: {ADOPTION_DESIGN}", "-m", "Review: n/a: generated scaffold")


def test_the_adoption_commit_goes_in_though_it_is_not_the_first(legacy):
    written = _adopt(legacy)

    result = _adoption_commit(legacy, written)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "generated scaffold" in result.stdout + result.stderr
    assert "agentsmith tenant adopt" in result.stdout + result.stderr, "the note names what wrote the files"
    assert (legacy.parent / "marks").read_text() == "pre-commit\n", "the repository's own hook still ran"
    assert _status(legacy) == "", "every file adopt wrote was staged by name"


def test_the_printed_commit_stages_by_name(legacy):
    from runtime.adopt import commit_command

    command = commit_command(_adopt(legacy))

    assert "git add -A" not in command and "CLAUDE.md" in command and "Review: n/a: generated scaffold" in command


def test_after_adoption_existing_code_needs_a_design(legacy):
    assert _adoption_commit(legacy, _adopt(legacy)).returncode == 0
    _write(legacy, "mypkg/core.py", "def add(a, b):\n    return b + a\n")
    _git(legacy, "add", "mypkg/core.py")

    result = _git(legacy, "commit", "-m", "fix: commute")

    assert result.returncode != 0 and "Design" in result.stderr


def test_after_adoption_the_edit_gate_reaches_existing_code(legacy):
    assert _adoption_commit(legacy, _adopt(legacy)).returncode == 0
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(legacy / "mypkg/core.py")}, "cwd": str(legacy)}

    # `--ide claude` is what the generated .claude/settings.json passes: the
    # dialect the payload is in. The provider translates it and answers in it.
    result = subprocess.run(["bash", str(legacy / ".githooks/process-gate"), "pre-edit", "--ide", "claude"],
                            input=json.dumps(payload), capture_output=True, text=True, check=False, cwd=legacy)

    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_later_commit_cannot_claim_to_be_the_adoption(legacy):
    written = _adopt(legacy)
    assert _adoption_commit(legacy, written).returncode == 0
    workflow = legacy / ".github/workflows/agentsmith-gates.yml"
    workflow.write_text(workflow.read_text() + "\n")

    result = _adoption_commit(legacy, [".github/workflows/agentsmith-gates.yml"])

    assert result.returncode != 0
    assert "arms the gates" in result.stderr


def test_ci_lists_the_history_before_adoption_and_notes_the_adoption(legacy, tmp_path):
    assert _adoption_commit(legacy, _adopt(legacy)).returncode == 0
    first = _git(legacy, "rev-list", "--max-parents=0", "HEAD").stdout.strip()
    out = tmp_path / "record.json"

    result = subprocess.run([sys.executable, str(REPO / "scripts/process_gate.py"), "ci", "--base", first,
                             "--head", "HEAD", "--json", str(out)], cwd=legacy, capture_output=True, text=True,
                            check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    verdicts = [c["verdict"] for c in json.loads(out.read_text())["commits"]]
    assert verdicts == ["before_adoption", "passed_with_notes"]


def test_the_machines_provisioning_hooks_are_not_chained_into_an_adopted_repository(legacy):
    """Found adopting a scratch repository created on a machine with AgentSmith
    installed: `git init` had copied the machine's hooks into .git/hooks, where
    they did nothing until adopt's tenant.yaml opted the repository in. Chained,
    the first `git checkout -- <file>` vendored scripts/ and runtime/ and wrote
    seven CI workflows beside the repository's own, and every commit re-mapped
    the graph. The guardrail hooks are the repository's to keep; the
    provisioning ones are not."""
    import shutil

    from runtime.adopt import adopt

    machine = legacy / ".git" / "hooks"
    machine.mkdir(exist_ok=True)
    for name in ("post-checkout", "post-commit", "pre-commit"):
        shutil.copy(REPO / "hooks" / name, machine / name)
        (machine / name).chmod(0o755)
    _git(legacy, "config", "--unset", "core.hooksPath")

    plan = _plan(legacy)
    written = adopt(plan)

    assert plan.prior_hooks == machine
    assert any("post-checkout and post-commit" in w and "not chained" in w for w in plan.warnings)
    assert not {".githooks/post-checkout", ".githooks/post-commit"} & set(written)
    assert _git(legacy, "config", "--get", "agentsmith.autopush").stdout == "", \
        "no post-commit runs, so there is nothing to turn off"
    assert _adoption_commit(legacy, written).returncode == 0
    _git(legacy, "checkout", "-q", "--", "mypkg/core.py")
    assert not (legacy / "scripts").exists() and not (legacy / "runtime").exists()
    assert _status(legacy) == "", "nothing ran after the commit to leave the tree dirty"


def test_vendored_framework_code_is_not_gated(legacy):
    """A tenant provisioned the old way carries AgentSmith's own scripts/ and
    runtime/, copied in by hooks/post-checkout. Gating them would make the next
    re-vendoring need a design and a review of framework code
    (.agent-rfc/designs/installed-architectures.md). Found adopting a real
    scratch tenant, which the synthetic fixtures had no vendored code to show."""
    _write(legacy, "scripts/run-security-checks.py", "# vendored AgentSmith harness\n")
    _write(legacy, "scripts/agent_logger.py", "# vendored\n")
    _write(legacy, "runtime/llm_gateway.py", "# vendored AgentSmith runtime\n")
    _git(legacy, "add", "-A")
    _git(legacy, "commit", "-q", "-m", "chore: vendored")

    plan = _plan(legacy)

    assert "scripts/**" not in plan.gated and "runtime/**" not in plan.gated
    assert "mypkg/**" in plan.gated, "the repository's own code is still gated"
    assert any("vendored" in w and "scripts/" in w for w in plan.warnings), plan.warnings


def test_adopt_refuses_when_the_install_cannot_arm_the_gates(legacy, tmp_path, monkeypatch):
    """An install with no .githooks/ would leave the repository armed at an
    empty directory — no gates, and not its own hooks either, since a hooks path
    overrides .git/hooks. Refused in the plan, before anything is written
    (.agent-rfc/designs/installed-architectures.md)."""
    from runtime.adopt import AdoptError

    install = tmp_path / "install"
    (install / "scripts").mkdir(parents=True)
    (install / "scripts" / "process_gate.py").write_text("# the gate, without the hooks that run it\n")
    monkeypatch.setenv("AGENTSMITH_DIR", str(install))
    before = _status(legacy)

    with pytest.raises(AdoptError, match="cannot be armed"):
        _plan(legacy)

    assert _status(legacy) == before, "nothing written"


def test_adopt_declares_who_governs_the_repository(legacy):
    """The repository names its provider rather than implying AgentSmith's file
    layout (.agent-rfc/designs/provider-resolution.md)."""
    plan = _plan(legacy)
    assert dict(plan.actions)[".agenticframework/providers.json"] == "create"

    written = _adopt(legacy)

    assert ".agenticframework/providers.json" in written
    declared = json.loads((legacy / ".agenticframework/providers.json").read_text())
    assert declared["contract"] == 1
    assert declared["providers"]["gate"]["command"] == "agentsmith gate"
    assert declared["providers"]["gate"]["version"].startswith("^")
    assert _adoption_commit(legacy, written).returncode == 0, "it is part of the adoption commit"


def test_adopt_writes_the_sync_workflow_so_a_tenant_hears_about_upgrades(legacy):
    """A tenant only learns it is behind when someone thinks to check; the
    scheduled workflow is what removes that (.agent-rfc/designs/sync-pull-request.md)."""
    from runtime.adopt import SYNC_WORKFLOW

    plan = _plan(legacy)
    assert dict(plan.actions)[SYNC_WORKFLOW] == "create"

    written = _adopt(legacy)

    assert SYNC_WORKFLOW in written
    assert "gh pr create" in (legacy / SYNC_WORKFLOW).read_text()
    assert _adoption_commit(legacy, written).returncode == 0
