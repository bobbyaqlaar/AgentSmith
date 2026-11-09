"""SEC-CIAGENT-001 — untrusted event text kept from coding agents
(.agent-rfc/designs/agent-workflow-injection.md)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from security.registry import load_control_registry
from security.runners import RUNNERS, agent_workflow

TITLE = "${{ github.event.pull_request.title }}"
CLAUDE = "anthropics/claude-code-action@v1"


def _control():
    return next(c for c in load_control_registry(REPO / "fixtures" / "security" / "control_registry.json")
                if c.id == "SEC-CIAGENT-001")


def _check(tmp_path: Path, *workflows: str):
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    for number, text in enumerate(workflows):
        (directory / f"w{number}.yml").write_text(text, encoding="utf-8")
    return agent_workflow.run(_control(), {"tenant_root": str(tmp_path)})


def _job(body: str, job_if: str = "") -> str:
    guard = f"    if: {job_if}\n" if job_if else ""
    return f"on: pull_request\njobs:\n  a:\n    runs-on: ubuntu-latest\n{guard}    steps:\n{body}"


def _action(prompt: str = TITLE, extra: str = "") -> str:
    return f"      - uses: {CLAUDE}\n{extra}        with:\n          prompt: \"{prompt}\"\n"


def _failed(result) -> bool:
    return result.status.value == "fail" if hasattr(result.status, "value") else result.status == "fail"


def test_the_runner_is_registered():
    assert RUNNERS["agent_workflow"] is agent_workflow.run


def test_a_repository_with_no_workflows_passes(tmp_path):
    assert not _failed(agent_workflow.run(_control(), {"tenant_root": str(tmp_path)}))


@pytest.mark.parametrize("field", [
    "github.event.pull_request.title", "github.event.pull_request.body", "github.event.issue.title",
    "github.event.issue.body", "github.event.comment.body", "github.event.review.body", "github.event.discussion.body",
    "github.event.head_commit.message", "github.event.commits[0].message", "github.event.pull_request.head.ref",
    "github.head_ref", "toJSON(github.event)", "github.event['pull_request']['title']",
])
def test_an_untrusted_field_in_an_agents_prompt_fails(tmp_path, field):
    assert _failed(_check(tmp_path, _job(_action("Review ${{ " + field + " }}"))))


@pytest.mark.parametrize("use", ["github.event.pull_request.number", "github.sha", "github.repository"])
def test_a_field_an_outsider_cannot_write_passes(tmp_path, use):
    assert not _failed(_check(tmp_path, _job(_action("Review ${{ " + use + " }}"))))


@pytest.mark.parametrize("uses", ["openai/codex-action@v1", "google-github-actions/run-gemini-cli@v0",
                                  "actions/ai-inference@v1", "anthropics/claude-code-base-action@beta"])
def test_each_agent_action_is_recognised(tmp_path, uses):
    assert _failed(_check(tmp_path, _job(f"      - uses: {uses}\n        with:\n          prompt: \"{TITLE}\"\n")))


@pytest.mark.parametrize("command", ["claude -p", "npx -y @anthropic-ai/claude-code -p", "codex exec", "gemini -p",
                                     "aider --message"])
def test_an_agent_started_from_a_shell_step_is_recognised(tmp_path, command):
    assert _failed(_check(tmp_path, _job(f"      - run: {command} \"{TITLE}\"\n")))


def test_a_step_that_is_not_an_agent_is_not_this_controls_business(tmp_path):
    assert not _failed(_check(tmp_path, _job(f"      - run: echo \"{TITLE}\"\n")))


_STEP_ENV = f"        env:\n          T: \"{TITLE}\"\n"
_JOB_ENV = f"    env:\n      T: \"{TITLE}\"\n"
_TOP_ENV = f"env:\n  T: \"{TITLE}\"\n"
_HEAD = "on: pull_request\n"
_RUNS = "jobs:\n  a:\n    runs-on: x\n"


@pytest.mark.parametrize("workflow", [
    # step level, named in the prompt
    _job(f"      - uses: {CLAUDE}\n{_STEP_ENV}        with:\n          prompt: \"${{{{ env.T }}}}\"\n"),
    # step level: an action receives its own environment
    _job(f"      - uses: {CLAUDE}\n{_STEP_ENV}"),
    # job level, in a shell
    f"{_HEAD}{_RUNS}{_JOB_ENV}    steps:\n      - run: claude -p \"$T\"\n",
    # workflow level, braces
    f"{_HEAD}{_TOP_ENV}{_RUNS}    steps:\n      - run: claude -p \"${{T}}\"\n",
])
def test_untrusted_text_through_the_environment_fails(tmp_path, workflow):
    assert _failed(_check(tmp_path, workflow))


def test_an_environment_variable_the_agent_does_not_use_passes(tmp_path):
    workflow = f"{_HEAD}{_TOP_ENV}{_RUNS}    steps:\n      - run: claude -p \"$OTHER\"\n"
    assert not _failed(_check(tmp_path, workflow))


def test_a_trusted_value_replacing_an_untrusted_one_passes(tmp_path):
    workflow = f"{_HEAD}{_TOP_ENV}{_RUNS}    env:\n      T: fixed\n    steps:\n      - run: claude -p \"$T\"\n"
    assert not _failed(_check(tmp_path, workflow))


def test_reading_the_event_file_in_an_agent_step_fails(tmp_path):
    assert _failed(_check(tmp_path, _job("      - run: claude -p \"$(cat $GITHUB_EVENT_PATH)\"\n")))


COMMENT = "${{ github.event.comment.body }}"
COLLABORATOR = ("contains(fromJson('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\"]'), "
                "github.event.comment.author_association)")


def test_a_comment_restricted_to_collaborators_passes(tmp_path):
    assert not _failed(_check(tmp_path, _job(_action(COMMENT), job_if=COLLABORATOR)))


def test_the_restriction_also_counts_on_the_step(tmp_path):
    step = f"      - uses: {CLAUDE}\n        if: {COLLABORATOR}\n        with:\n          prompt: \"{COMMENT}\"\n"
    assert not _failed(_check(tmp_path, _job(step)))


@pytest.mark.parametrize("guard", [
    "github.event.comment.author_association != 'NONE'",
    "github.event.comment.author_association != 'OWNER'",
    "github.event.comment.author_association == 'NONE'",
    "contains(github.event.comment.body, '@claude')",
    "contains(fromJson('[\"OWNER\"]'), github.event.issue.author_association)",
])
def test_a_restriction_that_does_not_hold_does_not_count(tmp_path, guard):
    assert _failed(_check(tmp_path, _job(_action(COMMENT), job_if=guard)))


def test_a_restriction_never_excuses_a_branch_name(tmp_path):
    guard = "contains(fromJson('[\"OWNER\"]'), github.event.pull_request.author_association)"
    assert _failed(_check(tmp_path, _job(_action("${{ github.event.pull_request.head.ref }}"), job_if=guard)))


def test_a_workflow_that_does_not_parse_fails(tmp_path):
    result = _check(tmp_path, "on: [unclosed\njobs: {")
    assert _failed(result)
    assert "could not be read" in result.message


def test_the_failure_says_what_to_do(tmp_path):
    result = _check(tmp_path, _job(_action()))
    assert "pull_request.title" in result.message and "fetch it as data" in result.message
