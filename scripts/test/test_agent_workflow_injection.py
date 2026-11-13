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


# ── The 4.1.0 release review: R9, R10 ──


@pytest.mark.parametrize("guard", [
    "github.event.comment.author_association == 'OWNER' || github.event_name == 'issue_comment'",
    "contains(github.event.comment.body, '@claude') || github.event.comment.author_association == 'MEMBER'",
    # Written inside ${{ }}: a bare `!` at the start of a YAML value is a tag, and is dropped.
    "${{ !contains(fromJSON('[\"OWNER\",\"MEMBER\"]'), github.event.comment.author_association) }}",
    "${{ ! contains(fromJSON('[\"OWNER\"]'), github.event.comment.author_association) }}",
    "${{ !(github.event.comment.author_association == 'OWNER') }}",
])
def test_a_guard_that_an_or_or_a_negation_undoes_does_not_count(tmp_path, guard):
    """R9: each of these runs for outsiders, and each was accepted."""
    assert _failed(_check(tmp_path, _job(_action(COMMENT), job_if=guard)))


def test_a_guard_joined_by_and_still_counts(tmp_path):
    guard = f"{COLLABORATOR} && contains(github.event.comment.body, '@claude')"
    assert not _failed(_check(tmp_path, _job(_action(COMMENT), job_if=guard)))


@pytest.mark.parametrize("field", [
    "${{ toJSON(github) }}",
    "${{ toJson( github ) }}",
    "${{ github.event.workflow_run.display_title }}",
    "${{ github.event.release.body }}",
    "${{ github.event.release.name }}",
    "${{ github.event.label.name }}",
    "${{ github.event.pull_request.labels[0].name }}",
])
def test_more_fields_an_outsider_writes_fail(tmp_path, field):
    """R10: each reached an agent and passed."""
    assert _failed(_check(tmp_path, _job(_action(field))))


@pytest.mark.parametrize("scope", ["job", "workflow"])
def test_an_action_receives_inherited_environment(tmp_path, scope):
    """R10: a job- or workflow-level variable reaches an action whether or not it is named."""
    env = "    env:\n      TITLE: ${{ github.event.issue.title }}\n" if scope == "job" else ""
    top = "env:\n  TITLE: ${{ github.event.issue.title }}\n" if scope == "workflow" else ""
    text = (f"on: issues\n{top}jobs:\n  a:\n    runs-on: ubuntu-latest\n{env}    steps:\n"
            f"      - uses: {CLAUDE}\n        with:\n          prompt: \"fix the issue\"\n")
    assert _failed(_check(tmp_path, text))


# ── The 4.1.0 review's second pass: P2-R5 (.agent-rfc/designs/review-pass2-majors.md) ──


@pytest.mark.parametrize("guard", [
    # R9's negation, written with `== false` instead of `!`: runs only for outsiders.
    "contains(fromJSON('[\"OWNER\",\"MEMBER\"]'), github.event.comment.author_association) == false",
    "(github.event.comment.author_association == 'OWNER') == false",
    # CONTRIBUTOR is anyone with one merged commit.
    "contains(fromJSON('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\",\"CONTRIBUTOR\"]'), "
    "github.event.comment.author_association)",
    # The role word is there, but not as the allowed value.
    "github.event.comment.author_association == 'NONE' && github.repository_owner == 'OWNER-co'",
    # `&&` binds tighter than `||`: this runs for anyone who mentions the agent.
    "contains(github.event.comment.body, '@claude') || github.event_name == 'x' && "
    "github.event.comment.author_association == 'OWNER'",
    # The issue's author is trusted; the comment's is not.
    "github.event.issue.author_association == 'OWNER'",
    # A negated group hides a positive term from the split.
    "${{ !(contains(github.event.comment.body, '@claude') && github.event.comment.author_association == 'OWNER') }}",
])
def test_a_guard_that_only_looks_like_a_restriction_does_not_count(tmp_path, guard):
    """P2-R5: each of these lets an outsider's comment reach the agent, and each was accepted."""
    assert _failed(_check(tmp_path, _job(_action(COMMENT), job_if=guard)))


@pytest.mark.parametrize("guard", [
    # The common shape: only on issues, and only for the owner. A negated term in a
    # conjunction can only narrow it.
    "github.event.comment.author_association == 'OWNER' && !github.event.issue.pull_request",
    "${{ github.event.comment.author_association == 'MEMBER' && contains(github.event.comment.body, '@claude') }}",
    # Inside ${{ }}: a YAML value that starts with a quote is a quoted string.
    "${{ 'COLLABORATOR' == github.event.comment.author_association }}",
    # GitHub compares strings without case.
    "github.event.comment.author_association == 'owner'",
    "(github.event.comment.author_association == 'OWNER')",
    # A list read as a string is a substring test, and no association outside OWNER and
    # MEMBER (nor an undefined one) is a substring of it: it restricts. It was refused by
    # spelling before; evaluated, it holds (P3-R1).
    "contains('OWNER,MEMBER', github.event.comment.author_association)",
])
def test_a_term_that_can_only_narrow_to_trusted_authors_counts(tmp_path, guard):
    assert not _failed(_check(tmp_path, _job(_action(COMMENT), job_if=guard)))


# ── The 4.1.0 review's second pass: P2-R6 (.agent-rfc/designs/db-tests-in-ci-and-event-objects.md) ──


@pytest.mark.parametrize("given", [
    "${{ github.event.pull_request }}",
    "${{ github.event.issue }}",
    "${{ format('{0}', github.event.issue) }}",
    "${{ github.event.comment }}",
    "${{ github.event.review }}",
    "${{ github.event.release }}",
    "${{ github.event.workflow_run }}",
    "${{ github.event.head_commit }}",
    "${{ github.event.commits }}",
    "${{ github.event.pull_request.head }}",
    "${{ github.event }}",
    "${{ github.event['issue'] }}",
])
def test_a_whole_event_object_is_untrusted_text(tmp_path, given):
    """P2-R6: GitHub renders an object as JSON, title and body included, and it passed."""
    assert _failed(_check(tmp_path, _job(_action(given))))


def test_an_author_guard_does_not_excuse_a_whole_object(tmp_path):
    """An object carries more than its author wrote: labels, branch names."""
    guard = "github.event.comment.author_association == 'OWNER'"
    assert _failed(_check(tmp_path, _job(_action("${{ github.event.comment }}"), job_if=guard)))


@pytest.mark.parametrize("given", ["${{ github.event.issue.number }}", "${{ github.event.pull_request.head.sha }}",
                                   "${{ github.event_name }}", "${{ github.event.action }}"])
def test_a_field_of_an_object_that_an_outsider_does_not_write_still_passes(tmp_path, given):
    assert not _failed(_check(tmp_path, _job(_action(given))))


# ── The 4.1.0 review's third pass: P3-R1 (.agent-rfc/designs/pass3-root-causes.md) ──
# The condition is evaluated, so these are the same guard spelled differently; every
# spelling that lets an outsider through is reported, without a rule for each.

A = "github.event.comment.author_association"


@pytest.mark.parametrize("guard", [
    f"({A} == 'OWNER' && github.event.issue.number > 0) == false",
    f"({A} == 'OWNER' && github.event.issue.number > 0) != true",
    f"${{{{ ({A} == 'OWNER' && github.event.issue.number > 0) == false }}}}",
    f"false == ({A} == 'OWNER' && x)",
    f"${{{{ !({A} == 'OWNER') }}}}",  # in ${{ }}: a YAML value that starts with ! is a tag
    f"${{{{ !!({A} != 'OWNER') }}}}",  # in ${{ }}: a YAML value that starts with ! is a tag
    f"{A} != 'OWNER' || {A} == 'OWNER'",
    f"{A} == 'OWNER' || always()",
    f"contains(fromJSON('[\"OWNER\",\"NONE\"]'), {A})",
    f"startsWith({A}, 'CONTRIB') || {A} == 'MEMBER'",
    f"{A} >= 'A'",
    f"{A} == 'OWNER' && false || true",
    "github.event.issue.author_association == 'OWNER'",  # another author's association
    f"{A} == github.event.comment.user.login",             # compared with a value an outsider sets
    f"{A} == 'OWNER' ${{{{ x }}}}",                         # text around an expression is a string: true
    f"{A} === 'OWNER'",                                     # does not parse: may be true
])
def test_every_spelling_that_lets_an_outsider_through_is_reported(tmp_path, guard):
    assert _failed(_check(tmp_path, _job(_action(COMMENT), job_if=guard)))


@pytest.mark.parametrize("guard", [
    f"${{{{ !({A} != 'OWNER') }}}}",  # in ${{ }}: a YAML value that starts with ! is a tag
    f"({A} == 'OWNER' && contains(github.event.comment.body, '@claude')) == true",
    f"${{{{ !!({A} == 'MEMBER') }}}}",
    f"{A} == 'OWNER' && (github.event.issue.pull_request || true)",
    f"contains(fromJSON('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\"]'), {A}) && !github.event.issue.pull_request",
    f"({A} == 'OWNER' || {A} == 'MEMBER') && success()",
])
def test_every_spelling_that_keeps_outsiders_out_counts(tmp_path, guard):
    assert not _failed(_check(tmp_path, _job(_action(COMMENT), job_if=guard)))


def test_the_job_and_the_step_conditions_hold_together(tmp_path):
    """A step condition that restricts is enough, whatever the job's says, and the reverse."""
    step = f"      - uses: {CLAUDE}\n        if: {A} == 'MEMBER'\n        with:\n          prompt: \"{COMMENT}\"\n"
    assert not _failed(_check(tmp_path, _job(step, job_if="github.event_name == 'issue_comment'")))
