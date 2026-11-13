"""SEC-CIAGENT-001 — a workflow may not hand untrusted event text to a coding agent.

A pull-request title in an agent's prompt gives an outsider the agent's instructions
(.agent-rfc/designs/agent-workflow-injection.md). This reads what the workflows say.
It cannot see text laundered through a step output or a file, or an agent started
from a script: it is a floor.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator

import yaml

from security import gha_expression
from security.registry import ControlSpec
from security.report import ControlResult
from security.runners._shared import failed, passed

_AGENT_ACTIONS = ("anthropics/claude-code-action", "anthropics/claude-code-base-action", "openai/codex-action",
                  "google-github-actions/run-gemini-cli", "actions/ai-inference")
_AGENT_COMMAND = re.compile(
    r"(?:^|[\s;&|(`])(?:npx\s+(?:-y\s+)?@anthropic-ai/claude-code|claude|codex|gemini|copilot|cursor-agent|aider"
    r"|opencode|goose)(?=\s|$)", re.M)
_EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
_UNTRUSTED = re.compile(
    r"github\.event\.(?:(?:issue|pull_request|discussion)\.(?:title|body)"
    r"|(?:comment|review|review_comment)\.body"
    r"|pages\.[^.\s]+\.page_name"
    r"|workflow_run\.display_title|release\.(?:name|body)|label\.name"
    r"|(?:issue|pull_request|discussion)\.labels\.[^.\s]+\.name"
    r"|(?:commits\.[^.\s]+|head_commit|workflow_run\.head_commit)\.(?:message|author\.(?:email|name))"
    r"|pull_request\.head\.(?:ref|label|repo\.default_branch)"
    r"|workflow_run\.head_branch)\b"
    r"|github\.head_ref\b|tojson\(\s*github(?:\.event)?\s*[).]"
    # A whole object, rendered as JSON with the fields above inside it (the 4.1.0
    # review's second pass, P2-R6). A field of one (`…issue.number`) is not this.
    r"|github\.event(?:\.(?:pull_request\.head|issue|pull_request|discussion|comment|review_comment|review"
    r"|release|workflow_run|head_commit|commits|pages))?(?![\w.\[])", re.I)
_AUTHORED = ("issue", "pull_request", "discussion", "comment", "review", "review_comment")


def _normalised(expression: str) -> str:
    """`event['title']` and `commits[0]` are the same fields as their dotted forms."""
    expression = re.sub(r"\[\s*['\"]([\w-]+)['\"]\s*\]", r".\1", expression)
    return re.sub(r"\[\s*(?:\d+|\*)\s*\]", ".0", expression)


def _untrusted_fields(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    found: list[str] = []
    for expression in _EXPRESSION.findall(text):
        found += [match.group(0) for match in _UNTRUSTED.finditer(_normalised(expression))]
    return found


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _is_agent(step: dict) -> bool:
    uses = str(step.get("uses") or "").lower()
    if uses.startswith(_AGENT_ACTIONS):
        return True
    return bool(_AGENT_COMMAND.search(str(step.get("run") or "")))


def _tainted(*scopes: Any) -> dict[str, list[str]]:
    """The environment variables holding untrusted text, by name. A nearer scope
    replaces a further one, as it does on the runner."""
    env: dict[str, Any] = {}
    for scope in scopes:
        if isinstance(scope, dict):
            env.update(scope)
    return {str(name): fields for name, value in env.items() if (fields := _untrusted_fields(value))}


def _uses_variable(text: str, name: str) -> bool:
    escaped = re.escape(name)
    return re.search(rf"\$\{{?{escaped}\b|\$\{{\{{\s*env\.{escaped}\b", text) is not None


# Every author association GitHub defines that does not hold the repository, and one it
# does not define, so a future value is not trusted by default.
_UNTRUSTED_ROLES = ("CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "MANNEQUIN", "NONE",
                    "A_ROLE_GITHUB_HAS_NOT_DEFINED")


def _guarded(field: str, conditions: list[str]) -> bool:
    """Is this field's own author restricted to people who already hold the repository?
    Only an authored title or body: a branch name or commit message has no such author.

    The conditions (the job's and the step's `if:`) are evaluated, not read: for every
    association that is not OWNER, MEMBER or COLLABORATOR, they must be definitely false,
    with every other context unknown. Reading the spelling accepted `||`, `!`, `== false`
    and a negated group in turn, three rounds of one defect (R9, P2-R5, P3-R1)."""
    parts = field.lower().split(".")
    if len(parts) != 4 or parts[:2] != ["github", "event"] or parts[2] not in _AUTHORED or not conditions:
        return False
    association = ("github", "event", parts[2], "author_association")
    return not any(gha_expression.may_be_true(conditions, {association: role}) for role in _UNTRUSTED_ROLES)


def _step_problems(step: dict, inherited: tuple[Any, ...], conditions: list[str]) -> list[str]:
    if not _is_agent(step):
        return []
    run = str(step.get("run") or "")
    given = list(_strings(step.get("with"))) + ([run] if run else [])
    fields = [field for text in given for field in _untrusted_fields(text)]
    tainted = _tainted(*inherited, step.get("env"))
    for name, values in tainted.items():
        # An action receives the whole environment, its step's, its job's and its
        # workflow's, whether or not it names a variable (R10).
        if any(_uses_variable(text, name) for text in given) or step.get("uses"):
            fields += values
    problems = [field for field in dict.fromkeys(fields) if not _guarded(field, conditions)]
    if "GITHUB_EVENT_PATH" in run:
        problems.append("$GITHUB_EVENT_PATH")
    return problems


def _workflow_problems(name: str, workflow: dict) -> list[str]:
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return []
    problems: list[str] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for index, step in enumerate(job.get("steps") or [], start=1):
            if not isinstance(step, dict):
                continue
            conditions = [str(item) for item in (job.get("if"), step.get("if")) if item]
            for field in _step_problems(step, (workflow.get("env"), job.get("env")), conditions):
                label = step.get("name") or step.get("uses") or f"step {index}"
                problems.append(f"{name}: job {job_id}, {label}: {field} reaches a coding agent")
    return problems


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    directory = Path(ctx["tenant_root"]) / ".github" / "workflows"
    files = sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")]) if directory.is_dir() else []
    problems: list[str] = []
    for path in files:
        try:
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            problems.append(f"{path.name}: could not be read, so nothing can be said about it: {exc}")
            continue
        if isinstance(workflow, dict):
            problems += _workflow_problems(path.name, workflow)
    if problems:
        return failed(control, "untrusted event text reaches a coding agent. Pass an issue or pull-request number and "
                               "let the agent fetch it as data, or restrict the author: " + "; ".join(problems[:5]),
                      count=str(len(problems)))
    return passed(control, f"read {len(files)} workflow(s): no untrusted event text reaches a coding agent "
                           "(steps' outputs and scripts they call are not followed)", workflows=str(len(files)))
