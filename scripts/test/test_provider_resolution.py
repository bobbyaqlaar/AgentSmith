"""
scripts/test/test_provider_resolution.py — a tenant names its provider
(.agent-rfc/designs/provider-resolution.md).

The launcher asks, in order: $GOVERNANCE_PROVIDER, the `gate` command in
`.agenticframework/providers.json`, then AgentSmith's own paths. A provider that
exits 3 ("cannot run here") falls through to the next, which is what makes a
declaration safe on a machine that does not have it. These tests drive the real
`.githooks/process-gate` with stub providers.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / ".githooks" / "process-gate"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None,
                               reason="git and bash required")

EDIT = {"kind": "edit", "paths": ["src/thing.py"]}


@pytest.fixture()
def repo(tmp_path):
    """A repository with the launcher armed and no gate of its own."""
    root = tmp_path / "tenant"
    (root / ".githooks").mkdir(parents=True)
    shutil.copy(LAUNCHER, root / ".githooks" / "process-gate")
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    return root


def _declare(root: Path, gate) -> None:
    (root / ".agenticframework").mkdir(exist_ok=True)
    (root / ".agenticframework" / "providers.json").write_text(
        json.dumps({"contract": 1, "providers": {"gate": gate}}, indent=2) + "\n")


def _provider(tmp_path: Path, body: str, name: str = "p") -> str:
    script = tmp_path / f"{name}.py"
    script.write_text("import json, sys\n" + body)
    return f"{sys.executable} {script}"


SAYS_DENY = """
json.load(sys.stdin)
print(json.dumps({"decision": "deny", "text": "the declared provider says no"}))
"""
CANNOT_RUN = """
sys.stderr.write("not installed here\\n")
sys.exit(3)
"""
RECORDS_ARGV = """
json.load(sys.stdin)
open(ARGV_LOG, "w").write(" ".join(sys.argv[1:]))
print(json.dumps({"decision": "allow", "text": ""}))
"""


def _ask(root: Path, event: str = "pre-edit", payload: dict | None = None, **env) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(root / ".githooks" / "process-gate"), event],
                          input=json.dumps(payload if payload is not None else EDIT),
                          capture_output=True, text=True, cwd=root, check=False,
                          env={**os.environ, "HOME": str(root.parent), **env})


def test_the_declared_provider_answers(repo, tmp_path):
    _declare(repo, {"command": _provider(tmp_path, SAYS_DENY), "version": "^1"})

    result = _ask(repo)

    assert json.loads(result.stdout)["decision"] == "deny"
    assert "declared provider" in result.stdout


def test_the_operator_escape_wins_over_the_declaration(repo, tmp_path):
    _declare(repo, {"command": _provider(tmp_path, SAYS_DENY)})
    escape = _provider(tmp_path, """
json.load(sys.stdin)
print(json.dumps({"decision": "allow", "text": "the escape answered"}))
""", name="escape")

    result = _ask(repo, GOVERNANCE_PROVIDER=escape)

    assert json.loads(result.stdout) == {"decision": "allow", "text": "the escape answered"}


def _gates_src(root: Path) -> None:
    (root / ".agenticframework").mkdir(exist_ok=True)
    (root / ".agenticframework" / "process-gates.json").write_text(json.dumps({
        "gated": ["src/**", ".agenticframework/process-gates.json"], "not_gated": ["**.md"],
        "registry": "@framework/templates/governance.json", "artifacts": "off", "pillars": "off",
        "knowledge_graph": "off"}) + "\n")


def _claude_edit(root: Path) -> dict:
    """What an IDE actually sends: its own dialect, which the framework's gate
    reads and a provider that serves that IDE translates."""
    return {"tool_name": "Edit", "tool_input": {"file_path": str(root / "src" / "thing.py")}, "cwd": str(root)}


TOO_OLD = """
sys.stdin.read()
sys.stderr.write("agentsmith: error: argument command: invalid choice: 'gate'\n")
sys.exit(2)
"""


@pytest.mark.parametrize(("why", "command"), [
    ("exits 3 — the contract's 'cannot run here'", CANNOT_RUN),
    ("is not on this machine at all", "/nonexistent/provider gate"),
    ("is installed but too old to know this event", TOO_OLD),
])
def test_a_provider_that_cannot_run_falls_through_to_the_framework(repo, tmp_path, why, command):
    """A tenant naming a provider this machine does not have still gets its
    gates from an installed or vendored AgentSmith — the declaration is
    additive, never a migration."""
    _declare(repo, {"command": command if command.startswith("/non") else _provider(tmp_path, command)})
    _gates_src(repo)

    result = subprocess.run(["bash", str(repo / ".githooks" / "process-gate"), "pre-edit", "--ide", "claude"],
                            input=json.dumps(_claude_edit(repo)), capture_output=True, text=True, cwd=repo,
                            check=False, env={**os.environ, "HOME": str(repo.parent),
                                              "AGENTSMITH_DIR": str(REPO), "AGENTSMITH_PYTHON": sys.executable})

    assert result.returncode == 0
    assert "permissionDecision" in result.stdout, f"the framework answered though the provider {why}"
    assert "deny" in result.stdout, "src/thing.py is gated and no design covers it"


def test_declaring_none_governs_nothing_and_says_so_rather_than_falling_back(repo):
    """The repository is configured so that the framework's own gate WOULD
    refuse this edit: silence here means `none` was honoured, not that there
    was nothing to say."""
    _gates_src(repo)
    _declare(repo, "none")

    result = subprocess.run(["bash", str(repo / ".githooks" / "process-gate"), "pre-edit", "--ide", "claude"],
                            input=json.dumps(_claude_edit(repo)), capture_output=True, text=True, cwd=repo,
                            check=False, env={**os.environ, "HOME": str(repo.parent),
                                              "AGENTSMITH_DIR": str(REPO), "AGENTSMITH_PYTHON": sys.executable})

    assert result.returncode == 0
    assert result.stdout.strip() == "", "a repository that declared no gate provider is not gated"


def test_no_declaration_behaves_exactly_as_before(repo):
    result = _ask(repo, AGENTSMITH_DIR=str(REPO), AGENTSMITH_PYTHON=sys.executable)

    assert result.returncode == 0
    assert result.stdout.strip() == "", "no gate config in this repo: the gate has nothing to say"


def test_the_arguments_reach_the_provider_unchanged(repo, tmp_path):
    log = tmp_path / "argv.txt"
    _declare(repo, {"command": _provider(tmp_path, f'ARGV_LOG = {str(log)!r}\n' + RECORDS_ARGV)})

    subprocess.run(["bash", str(repo / ".githooks" / "process-gate"), "pre-edit", "--ide", "claude"],
                   input=json.dumps(EDIT), capture_output=True, text=True, cwd=repo, check=False,
                   env={**os.environ, "HOME": str(repo.parent)})

    assert log.read_text() == "pre-edit --ide claude"


@pytest.mark.parametrize("formatting", ["indented", "compact"])
def test_the_declaration_is_read_whichever_way_it_is_written(repo, tmp_path, formatting):
    """A person edits this file; the launcher must not depend on the exact
    whitespace `tenant adopt` happened to write."""
    command = _provider(tmp_path, SAYS_DENY)
    body = {"contract": 1, "providers": {"gate": {"command": command, "version": "^2"}}}
    (repo / ".agenticframework").mkdir(exist_ok=True)
    (repo / ".agenticframework" / "providers.json").write_text(
        json.dumps(body, indent=2) if formatting == "indented" else json.dumps(body, separators=(",", ":")))

    assert json.loads(_ask(repo).stdout)["decision"] == "deny"


def test_commit_msg_is_not_a_contract_event_and_keeps_the_frameworks_own_path(repo, tmp_path):
    """Contract v1 covers the three hook events. A provider is not asked about a
    commit message, so a repository that declares one still commits through the
    framework's gate."""
    _declare(repo, {"command": _provider(tmp_path, SAYS_DENY)})
    message = repo / "msg.txt"
    message.write_text("chore: something\n")

    result = subprocess.run(["bash", str(repo / ".githooks" / "process-gate"), "commit-msg", str(message)],
                            capture_output=True, text=True, cwd=repo, check=False,
                            env={**os.environ, "HOME": str(repo.parent), "AGENTSMITH_DIR": str(REPO),
                                 "AGENTSMITH_PYTHON": sys.executable})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "declared provider" not in result.stdout + result.stderr
