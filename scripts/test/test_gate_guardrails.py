"""
scripts/test/test_gate_guardrails.py — what the machine-wide git hooks guarded at
a commit, judged by the gate instead (.agent-rfc/designs/vendoring-retired.md).

The hooks ran wherever init.templateDir put them; 3.0.0 stops arming them. These
hold that each check they made still blocks a commit, through the decision the
repository's own `.githooks/commit-msg` and gate contract 3's `commit` share.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gate_guardrails as gg
from test_process_gate import _commit, _write, needs_git


def _check(files: dict, message: str = "feat: x", vouched=(), enterprise=False, rfcs=()):
    return gg.check(list(files), files.get, message, vouched, enterprise, rfcs)


@pytest.mark.parametrize("line", ["# ponytail: fix later", "// TODO: agent finish this", "x = 1  # @agent-ignore"])
def test_an_unresolved_ai_marker_blocks(line):
    errors = _check({"app/a.py": f"x = 0\n{line}\n"})
    assert len(errors) == 1 and errors[0].startswith("app/a.py:2:") and "AI marker" in errors[0]


def test_an_ordinary_todo_does_not():
    assert _check({"app/a.py": "# TODO: tidy the names\nx = 1\n"}) == []


def test_an_empty_python_handler_blocks_by_its_syntax_tree():
    swallowed = "try:\n    f()\nexcept ValueError:\n    pass\n"
    handled = "try:\n    f()\nexcept ValueError:\n    raise\n"
    opted_out = "try:\n    f()\nexcept ValueError:  # fail-open: tracing must not break the call\n    pass\n"
    assert [e.split(":")[1] for e in _check({"a.py": swallowed})] == ["3"]
    assert _check({"a.py": handled}) == [] and _check({"a.py": opted_out}) == []


@pytest.mark.parametrize("path, text", [("web/a.ts", "try { f() } catch (e) {}\n"),
                                        ("web/b.jsx", "try { f() } catch (err) { }\n"),
                                        ("svc/main.go", "func f() {\n\t_, _ = g()\n}\n")])
def test_an_empty_catch_or_a_discarded_go_error_blocks(path, text):
    assert len(_check({path: text})) == 1


def test_a_vouched_file_a_deleted_file_and_a_binary_are_not_read():
    """The scaffold the gate wrote and still vouches for is not the tenant's to
    fix; a deletion has nothing to read; a binary is not code."""
    files = {"scripts/x.py": "# ponytail: theirs\n", "gone.py": None, "logo.png": "\x00PNG ponytail:"}
    assert _check(files, vouched=["scripts/x.py"]) == []


@needs_git
def test_a_vouched_file_stays_vouched_when_the_commit_is_amended(tmp_path):
    """An --amend is judged from HEAD^, so the commit's own files include ones
    already committed — not only what `git diff --cached` shows against HEAD.
    The vouch is asked of the files being judged."""
    import hashlib
    import subprocess

    from vouched_files import vouched

    body = b"# ponytail: the scaffold's, as written\n"
    manifest = {"files": {"scripts/x.py": hashlib.sha256(body).hexdigest()}}
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "scaffold.json").write_text(json.dumps(manifest))
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "x.py").write_bytes(body)
    def run(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                       check=True, capture_output=True)

    run("init", "-q", "--template=")
    run("add", "-A")
    run("commit", "-qm", "scaffold", "--no-verify")
    assert vouched(tmp_path) == []  # nothing staged against HEAD
    assert vouched(tmp_path, ["scripts/x.py"]) == ["scripts/x.py"]
    (tmp_path / "scripts" / "x.py").write_bytes(body + b"x = 1\n")
    run("add", "-A")
    assert vouched(tmp_path, ["scripts/x.py"]) == []  # edited: checked again


def test_enterprise_checks_apply_only_with_an_org_policy():
    files = {"runtime/worker.py": "import cost_router\n"}
    assert _check(files) == []
    errors = _check(files, enterprise=True)
    assert len(errors) == 3
    assert any("cost_router" in e for e in errors)
    assert any("at least one RFC" in e for e in errors)
    assert any("RFC-NNN" in e for e in errors)
    assert len(_check(files, message="feat: x (RFC-001)", enterprise=True, rfcs=[".agent-rfc/001-x.md"])) == 1


def test_the_org_policy_is_the_machines(tmp_path):
    assert gg.org_policy_present(tmp_path) is False
    (tmp_path / gg.ORG_POLICY).parent.mkdir(parents=True)
    (tmp_path / gg.ORG_POLICY).write_text("org: x\n")
    assert gg.org_policy_present(tmp_path) is True


# ── End to end: a commit in a governed tenant ─────────────────────────────────


@needs_git
def test_a_tenant_commit_carrying_a_marker_is_blocked_by_its_own_hook(installed_repo):
    """KYC-shaped: no gate script of its own, the framework found through
    $AGENTSMITH_DIR, `commit_guardrails` not declared — so on."""
    _write(installed_repo, "notes/plan.txt", "ponytail: decide the schema\n")
    done = _commit(installed_repo, "docs: plan")
    assert done.returncode != 0
    assert "notes/plan.txt:1: an unresolved AI marker" in done.stderr


@needs_git
def test_a_repository_that_turns_them_off_is_not_checked(installed_repo):
    config = json.loads((installed_repo / ".agenticframework/process-gates.json").read_text())
    _write(installed_repo, ".agenticframework/process-gates.json",
           json.dumps({**config, "commit_guardrails": "off"}))
    _write(installed_repo, "notes/plan.txt", "ponytail: decide the schema\n")
    # The config change itself is gated: commit it with the hook skipped, as a
    # repository's maintainer would through a reviewed change.
    from test_process_gate import _git
    _git(installed_repo, "add", "-A")
    _git(installed_repo, "commit", "-qm", "chore: config", "--no-verify")
    _write(installed_repo, "notes/plan.txt", "ponytail: and the other one\n")
    done = _commit(installed_repo, "docs: plan")
    assert done.returncode == 0, done.stderr


def test_a_mode_that_is_neither_on_nor_off_is_a_config_problem():
    import process_gate as pg

    _config, problems = pg.parse_config(json.dumps({"gated": ["**", ".agenticframework/process-gates.json"],
                                                   "commit_guardrails": "maybe"}))
    assert any("commit_guardrails" in p for p in problems)
