"""
scripts/test/test_gate_shell.py — G2b: the shell surface.

The edit gate watches an IDE's edit tools. The same agent can open a terminal
and run `git commit --no-verify`, and until now nothing said no until the sweep
found it afterwards. This refuses the obvious bypasses where they are typed.

What it can and cannot do is the point: it reads the command an IDE is about to
run, not what that command does. `bash -c "$(printf …)"`, a script file, an
alias or a Makefile target all reach git without passing it. That is why the
sweep exists, and why these tests pin the limit as carefully as the rule.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from test_process_gate import REPO, needs_git

sys.path.insert(0, str(REPO / "scripts"))
import gate_shell as gs


def _refused(command: str):
    return gs.refusal(command, hooks_path=".githooks")


# ── skipping the commit gate ─────────────────────────────────────────────────


@pytest.mark.parametrize("command", [
    "git commit --no-verify -m 'x'",
    "git commit -m 'x' --no-verify",
    "git commit -n -m 'x'",
    "git push --no-verify",
    "cd subdir && git commit --no-verify -m x",
    "true; git commit --no-verify -m x",
    "git -c core.hooksPath=/dev/null commit -m x",
    "git -c core.hooksPath=/tmp/empty push",
    "git config core.hooksPath /tmp/nothing",
    "git config --local core.hooksPath ''",
])
def test_a_command_that_skips_the_gate_is_refused(command) -> None:
    reason = _refused(command)
    assert reason, command
    assert "docs/process-gates.md" in reason


@pytest.mark.parametrize("command", [
    "git commit -m 'a normal commit'",
    "git push",
    "git push -n",                       # --dry-run for push, not --no-verify
    "git config core.hooksPath .githooks",
    "grep -rn -- --no-verify docs/",
    "echo 'never use git commit --no-verify'",
    "python3 -m pytest -q",
    "git log --oneline -5",
])
def test_ordinary_work_is_not_refused(command) -> None:
    assert _refused(command) is None, command


def test_a_bypass_inside_quotes_is_an_argument_not_a_command() -> None:
    """Writing a test or a document ABOUT the bypass is not running it. This
    rule refused the repo's own tests for itself until the line was tokenised
    the way a shell tokenises it, which is how the case was found."""
    quoted = "python3 -c " + repr("print('git commit --" + "no-verify')")
    assert _refused(quoted) is None, quoted
    assert _refused("grep -F 'git commit --no-verify' docs/") is None


def test_push_dash_n_is_a_dry_run_not_a_bypass() -> None:
    """Refusing the wrong thing is how a gate gets turned off."""
    assert _refused("git push -n") is None
    assert _refused("git commit -n -m x") is not None


def test_the_hooks_path_this_repo_uses_is_allowed_to_be_set() -> None:
    """Re-arming is what the sweep tells you to do."""
    assert _refused("git config core.hooksPath .githooks") is None
    assert _refused("git config core.hooksPath ../elsewhere") is not None


# ── writing to what the gate is made of ──────────────────────────────────────


@pytest.mark.parametrize("command", [
    "echo x > .githooks/commit-msg",
    "echo x >> .agenticframework/approvals.jsonl",
    "rm .githooks/pre-push",
    "sed -i '' 's/a/b/' .githooks/process-gate",
    "cp /tmp/x .claude/settings.json",
    "mv /tmp/x .cursor/hooks.json",
    "chmod -x .githooks/commit-msg",
    "tee .agenticframework/approvals.jsonl < /tmp/row",
])
def test_writing_to_the_gate_itself_is_refused(command) -> None:
    assert _refused(command), command


def test_reading_those_files_is_fine() -> None:
    assert _refused("cat .githooks/commit-msg") is None
    assert _refused("grep -n approve .agenticframework/approvals.jsonl") is None


def test_recording_an_approval_from_a_shell_is_refused() -> None:
    """The command asks at a terminal and an agent has none, so this only makes
    the refusal early and legible instead of a confusing failure."""
    reason = _refused("agentsmith approve .agent-rfc/designs/x.md D1")
    assert reason and "terminal" in reason


def test_other_agentsmith_commands_are_fine() -> None:
    assert _refused("agentsmith gates run") is None
    assert _refused("agentsmith design new retry-ladder") is None


# ── the limit, stated and pinned ─────────────────────────────────────────────


@pytest.mark.parametrize("command", [
    "bash -c \"$(printf 'git commit --no-verify')\"",
    "./scripts/release.sh",
    "make deploy",
])
def test_what_it_cannot_see_is_not_pretended_otherwise(command) -> None:
    """It reads the command, not what the command does. The sweep is what
    catches these, and claiming otherwise would be the worse failure."""
    assert _refused(command) is None


def test_the_reason_names_the_layer_that_still_holds() -> None:
    reason = _refused("git commit --no-verify -m x")
    assert "sweep" in reason or "commit gate" in reason


# ── through the gate, in every IDE ───────────────────────────────────────────


@needs_git
@pytest.mark.parametrize("ide", ("claude", "cursor"))
def test_the_gate_refuses_a_bypass_in_the_shell(gated_repo, ide) -> None:
    payload = ({"cwd": str(gated_repo), "tool_name": "Bash",
                "tool_input": {"command": "git commit --no-verify -m x"}} if ide == "claude"
               else {"workspace_roots": [str(gated_repo)], "cwd": str(gated_repo),
                     "command": "git commit --no-verify -m x", "sandbox": False})

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts" / "process_gate.py"), "pre-edit", "--ide", ide],
        cwd=gated_repo, input=json.dumps(payload), capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--no-verify" in result.stdout
    answer = json.loads(result.stdout)
    assert answer.get("permission") == "deny" or \
        answer["hookSpecificOutput"]["permissionDecision"] == "deny"


@needs_git
def test_an_ordinary_shell_command_is_allowed_through(gated_repo) -> None:
    payload = {"cwd": str(gated_repo), "tool_name": "Bash", "tool_input": {"command": "python3 -m pytest -q"}}

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts" / "process_gate.py"), "pre-edit", "--ide", "claude"],
        cwd=gated_repo, input=json.dumps(payload), capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "", "an allowed command says nothing"


# ── the hook configs carry the shell surface ─────────────────────────────────


def test_cursor_wires_the_shell_hook() -> None:
    import gate_ides as gi

    config = gi.render_config("cursor")
    assert "beforeShellExecution" in config["hooks"]
    assert config["hooks"]["beforeShellExecution"][0]["failClosed"] is True


def test_claude_matches_the_shell_tool() -> None:
    import gate_ides as gi

    matchers = [entry["matcher"] for entry in gi.render_config("claude", {})["hooks"]["PreToolUse"]]
    assert any("Bash" in matcher for matcher in matchers)
