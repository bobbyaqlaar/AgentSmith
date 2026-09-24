"""
scripts/test/test_framework_sync.py — one command keeps a tenant current, and
its own gates accept the result (.agent-rfc/designs/framework-sync.md).

A tenant holds copies of the framework's hooks, IDE configs and rule files, and
nothing refreshed them: the gate hooks changed six times in 90 days and no
tenant saw any of it. `agentsmith sync` refreshes what this framework owns, and
the commit it prints passes the tenant's own gates because every gated file in
it matches the manifest — hash-verified, as the generated scaffold already is.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import REPO, needs_git

pytestmark = needs_git

sys.path.insert(0, str(REPO))

SYNC_COMMIT = ["-m", "chore(framework): sync AgentSmith", "-m", "Design: .agent-rfc/designs/adoption.md",
               "-m", "Review: n/a: framework sync"]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                          capture_output=True, text=True, check=False)


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    """An adopted repository, one commit old, as `tenant adopt` leaves it."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    root = tmp_path / "tenant"
    (root / "mypkg").mkdir(parents=True)
    (root / "mypkg" / "core.py").write_text("VALUE = 1\n")
    (root / "pyproject.toml").write_text('[project]\nname = "t"\nversion = "0.1.0"\n')
    # A repository that already uses Claude Code, with its own permissions: the
    # framework owns the hooks in this file and the tenant owns the rest.
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(make *)"]}}, indent=2) + "\n")
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "feat: the tenant's own code")

    from runtime.adopt import adopt, plan_adoption

    written = adopt(plan_adoption("t", root, architecture="layered"))
    _git(root, "add", "--", *written)
    assert _git(root, "commit", "-m", "chore: adopt AgentSmith gates",
                "-m", "Design: .agent-rfc/designs/adoption.md",
                "-m", "Review: n/a: generated scaffold").returncode == 0
    return root


@pytest.fixture()
def moved_on(tmp_path):
    """A framework that has moved on since this tenant was adopted: its
    `.githooks/chain` differs. That is what drift is — not an uncommitted edit
    in the tenant, which git would show anyway."""
    import shutil

    fw = tmp_path / "framework"
    shutil.copytree(REPO / ".githooks", fw / ".githooks")
    (fw / "templates").mkdir()
    shutil.copy(REPO / "templates" / "governance.json", fw / "templates" / "governance.json")
    # Big enough that the gate's small-change escape (20 gated lines) cannot
    # explain the commit passing: only the hash-verified sync rule can.
    added = "".join(f"# a line this framework added since, {n}\n" for n in range(30))
    (fw / ".githooks" / "chain").write_text((REPO / ".githooks" / "chain").read_text() + added)
    (fw / ".githooks" / "pre-push").write_text((REPO / ".githooks" / "pre-push").read_text() + added)
    return fw


def _sync(root: Path, **kw):
    from runtime.sync import plan_sync, sync

    return sync(plan_sync(root, **kw))


def test_a_tenant_whose_hooks_drifted_is_brought_current(tenant, moved_on):
    """The case this exists for: a hook the framework changed since the tenant
    was adopted, and nothing to notice it."""
    written = _sync(tenant, framework=moved_on)

    assert {".githooks/chain", ".githooks/pre-push"} <= set(written)
    assert (tenant / ".githooks" / "chain").read_text() == (moved_on / ".githooks" / "chain").read_text()


def test_the_sync_commit_passes_the_tenants_own_gates(tenant, moved_on):
    written = _sync(tenant, framework=moved_on)
    _git(tenant, "add", "--", *written)

    result = _git(tenant, "commit", *SYNC_COMMIT)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "framework sync" in result.stdout + result.stderr, "accepted as a visible note"


def test_a_file_the_tenant_edited_is_not_vouched_for(tenant, moved_on):
    """The escape covers what the framework wrote, and nothing else: a tenant's
    own change riding along in a sync commit still needs a review."""
    _sync(tenant, framework=moved_on)
    (tenant / "mypkg" / "core.py").write_text("VALUE = 2\n")
    _git(tenant, "add", "-A")

    result = _git(tenant, "commit", *SYNC_COMMIT)

    assert result.returncode != 0
    # The refusal must be the sync rule's own, naming the file. Asserting only
    # "it was refused" would pass on the design-scope error alone, and a rule
    # that accepted anything would survive — it did, until this line.
    assert "framework sync — mypkg/core.py is not part of what" in result.stderr, result.stderr


def test_a_sync_lists_only_what_moved(tenant, moved_on):
    """`install_gate_hooks` rewrites every hook; a commit listing files whose
    bytes did not change is noise, and a manifest entry nobody needed."""
    written = _sync(tenant, framework=moved_on)

    assert ".githooks/commit-msg" not in written, "this hook did not drift"
    assert {".githooks/chain", ".githooks/pre-push"} <= set(written)


def test_restoring_a_hand_edited_hook_leaves_nothing_to_commit(tenant):
    """Someone edited a gate hook in the working tree. Sync puts the
    framework's copy back — which is what the repository already committed — so
    there is nothing to commit and nothing to list."""
    (tenant / ".githooks" / "chain").write_text("#!/usr/bin/env bash\n# edited by hand\nexit 0\n")

    written = _sync(tenant)

    assert written == []
    assert (tenant / ".githooks" / "chain").read_text() == (REPO / ".githooks" / "chain").read_text()
    assert _git(tenant, "status", "--porcelain").stdout.strip() == ""


def test_a_second_sync_writes_nothing(tenant, moved_on):
    _sync(tenant, framework=moved_on)
    _git(tenant, "add", "-A")
    _git(tenant, "commit", *SYNC_COMMIT)

    assert _sync(tenant, framework=moved_on) == [], "a sync with nothing to do says so"


def test_an_adopted_repository_is_never_vendored_into(tenant):
    _sync(tenant)

    assert not (tenant / "scripts").exists(), "adoption promised no vendored framework code"
    assert not (tenant / "runtime").exists()


def test_the_manifest_records_what_this_sync_wrote(tenant, moved_on):
    _sync(tenant, framework=moved_on)

    manifest = json.loads((tenant / ".agenticframework" / "scaffold.json").read_text())
    assert manifest["generated_by"] == "agentsmith sync"
    assert ".githooks/chain" in manifest["files"]
    assert manifest["files"][".githooks/chain"], "the hash of what it wrote"


def test_upgrade_refuses_to_vendor_into_an_adopted_repository(tenant, capsys):
    """`agentsmith upgrade` checked for a package pin and not for the adoption
    manifest, so it would have vendored into a repository adoption promised not
    to touch (.agent-rfc/designs/framework-sync.md)."""
    from runtime.machine.upgrade import upgrade

    said: list[str] = []
    code = upgrade(tenant, "9.9.9", out=said.append)

    assert code == 0
    assert not (tenant / "scripts").exists()
    said_all = " ".join(said)
    assert "tenant adopt" in said_all and "agentsmith sync" in said_all, said


# ── The files a tenant shares with the framework (.agent-rfc/designs/sync-merged-files.md) ──


def _as_an_older_framework_left_it(tenant: Path, *rels: str) -> None:
    """Commit the files as they are, with the manifest vouching for them — which
    is exactly what an older framework's own sync commit looked like. Staging it
    with `--no-verify` instead would be a bypass, and the sweep rightly refuses
    to let the next commit through until it is repaired."""
    import hashlib

    path = tenant / ".agenticframework" / "scaffold.json"
    manifest = json.loads(path.read_text())
    for rel in rels:
        manifest["files"][rel] = hashlib.sha256((tenant / rel).read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    _git(tenant, "add", "-A")
    assert _git(tenant, "commit", *SYNC_COMMIT).returncode == 0


def _stale_rules(tenant: Path) -> None:
    """The tenant as an older framework left it: an old rules block inside the
    tenant's own CLAUDE.md, and an old hook command in its Claude settings."""
    claude = tenant / "CLAUDE.md"
    claude.write_text("# Our rules\n\nTabs, not spaces.\n\n"
                      "<!-- agentsmith:rules:begin — generated by an older AgentSmith -->\n"
                      "Old rules nobody refreshed.\n<!-- agentsmith:rules:end -->\n")
    settings = json.loads((tenant / ".claude" / "settings.json").read_text())
    settings["hooks"]["SessionStart"] = [{"hooks": [{"type": "command", "command": "old-gate session-start"}]}]
    (tenant / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    _as_an_older_framework_left_it(tenant, "CLAUDE.md", ".claude/settings.json")


def test_a_stale_rules_block_is_refreshed_and_the_tenants_prose_survives(tenant):
    _stale_rules(tenant)

    written = _sync(tenant)

    claude = (tenant / "CLAUDE.md").read_text()
    assert "CLAUDE.md" in written
    assert claude.startswith("# Our rules\n\nTabs, not spaces.\n"), "the tenant's own text is untouched"
    assert "Old rules nobody refreshed." not in claude
    assert claude.count("agentsmith:rules:begin") == 1
    assert "Compliance" in claude, "the framework's current rules are in the block"


def test_the_ide_hook_wiring_is_refreshed_and_the_tenants_settings_survive(tenant):
    _stale_rules(tenant)

    _sync(tenant)

    settings = json.loads((tenant / ".claude" / "settings.json").read_text())
    assert "old-gate" not in json.dumps(settings["hooks"]), "the stale hook command is gone"
    assert "process-gate" in json.dumps(settings["hooks"])
    assert settings["permissions"]["allow"] == ["Bash(make *)"], "the tenant's own settings survive"


def test_a_tenants_own_settings_do_not_freeze_their_gate_wiring(tenant):
    """They edited their permissions, so the file no longer matches the
    manifest — but the hooks in it are the framework's, and a stale gate is
    exactly what this command exists to fix. Their keys survive."""
    settings = json.loads((tenant / ".claude" / "settings.json").read_text())
    settings["permissions"]["allow"].append("Bash(npm *)")
    settings["hooks"]["SessionStart"] = [{"hooks": [{"type": "command", "command": "old-gate session-start"}]}]
    (tenant / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    _git(tenant, "add", "-A")
    assert _git(tenant, "commit", "-m", "chore: our own permissions",
                "-m", "Design: .agent-rfc/designs/adoption.md",
                "-m", "Review: n/a: our own permissions").returncode == 0

    written = _sync(tenant)

    after = json.loads((tenant / ".claude" / "settings.json").read_text())
    assert ".claude/settings.json" in written
    assert "old-gate" not in json.dumps(after["hooks"]), "the gate wiring was refreshed"
    assert after["permissions"]["allow"] == ["Bash(make *)", "Bash(npm *)"], "their permissions survived"


def test_a_file_the_tenant_edited_is_left_alone_and_named(tenant):
    """The manifest vouches for `.cursor/hooks.json`, but the tenant has since
    changed it: a sync that clobbered it would lose their work."""
    from runtime.sync import plan_sync

    config = json.loads((tenant / ".cursor" / "hooks.json").read_text())
    config["hooks"]["stop"][0]["timeout"] = 120  # one line: their tuning, their file now
    theirs = json.dumps(config, indent=2) + "\n"
    (tenant / ".cursor" / "hooks.json").write_text(theirs)
    # Committed WITHOUT the manifest being updated: the tenant changed a file
    # the framework wrote, which is not the same as an older framework writing it.
    _git(tenant, "add", "-A")
    assert _git(tenant, "commit", "-m", "chore: our own cursor wiring",
                "-m", "Design: .agent-rfc/designs/adoption.md",
                "-m", "Review: n/a: our own IDE wiring").returncode == 0

    plan = plan_sync(tenant)
    written = _sync(tenant)

    assert ".cursor/hooks.json" not in written
    assert (tenant / ".cursor" / "hooks.json").read_text() == theirs, "their tuning survived"
    assert any(".cursor/hooks.json" in note and "edited" in note for note in plan.notes), plan.notes


def test_the_gates_workflow_follows_the_framework_it_runs(tenant):
    """A tenant that upgrades should run the new provider in CI, not the release
    it was adopted from."""
    workflow = tenant / ".github" / "workflows" / "agentsmith-gates.yml"
    workflow.write_text(workflow.read_text().replace('ref: "v2.0.0"', 'ref: "v1.9.0"'))
    _as_an_older_framework_left_it(tenant, ".github/workflows/agentsmith-gates.yml")

    written = _sync(tenant)

    assert ".github/workflows/agentsmith-gates.yml" in written
    assert 'ref: "v1.9.0"' not in workflow.read_text()
    assert "{{" not in workflow.read_text().replace("${{", "")


def test_everything_a_sync_refreshed_goes_in_one_commit_the_gates_accept(tenant):
    _stale_rules(tenant)

    written = _sync(tenant)
    _git(tenant, "add", "--", *written)
    result = _git(tenant, "commit", *SYNC_COMMIT)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "framework sync" in result.stdout + result.stderr
