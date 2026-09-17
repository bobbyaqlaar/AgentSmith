"""
scripts/gate_pillars.py — the pillars a script can check by itself, and the
policy that says whether this repo is held to them (G6a,
.agent-rfc/designs/governance-enforcement.md).

    parse_policy            `pillars` in .agenticframework/process-gates.json
    transition_problems     the ratchet: the mode only strengthens, and an
                            allowlist entry needs the owner's approval to appear
    mechanical_problems     the checks, over the files one commit touches
    repo_problems           the same checks over everything the repo tracks
    evidence_resolver       does this token name anything? (pillar answers)

Which checks exist is the registry's to say: a check runs only while its pillar
is marked `mechanical` in governance.json. Which repo is held to them is the
repo's, in a file that is read at the commit being checked — a requirement
added to the shared registry would judge every commit ever made by it.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

import gate_models as gm

MODES = ("off", "report", "enforce")
_STRENGTH = {mode: rank for rank, mode in enumerate(MODES)}

Resolver = Callable[[str], bool]


# ── the policy ───────────────────────────────────────────────────────────────


def parse_policy(value: object) -> Tuple[gm.PillarPolicy, List[str]]:
    """-> (policy, problems). A bare string is the mode: a repo with nothing to
    allowlist should not have to write an object to say `enforce`."""
    if value is None:
        return gm.PillarPolicy(), []
    data = {"mode": value} if isinstance(value, str) else value
    try:
        return gm.PillarPolicy.model_validate(data), []
    except gm.ValidationError as exc:
        error = exc.errors()[0]
        where = ".".join(str(part) for part in error["loc"]) or "pillars"
        # The value it was given, not only the rule it broke: "mode: Input
        # should be 'off', 'report' or 'enforce'" does not say what is there.
        given = repr(error.get("input"))
        return gm.PillarPolicy(), [f"`pillars` is invalid: {where}: {error['msg']} (got {given})"]


def transition_problems(
    old: Optional[gm.PillarPolicy],
    new: gm.PillarPolicy,
    approvals: Sequence[gm.Approval],
) -> List[str]:
    """What this commit does to the policy it inherited.

    A repo declaring one for the first time is seeding it — there is nothing to
    weaken yet. After that the mode only strengthens and the allowlist only
    shrinks, which is also why dropping the key is a weakening: without that,
    the allowlist could be widened by switching the policy off and on again.

    Stated limit: `old` is None when the parent commit carried no policy AND
    when its config could not be parsed at all, so a broken config in between
    reads as a seed. That commit is itself refused by every gate, and the sweep
    finds it if it was made with --no-verify — but it is the one seam here.
    """
    if old is None:
        return []
    problems: List[str] = []
    if _STRENGTH[new.mode] < _STRENGTH[old.mode]:
        problems.append(
            f"`pillars` would weaken from {old.mode!r} to {new.mode!r} — a gate is not turned down to "
            "pass a change (P13); the owner decides that, not the change that fails"
        )
    known = {approval.id for approval in approvals}
    before = {(entry.check, entry.path) for entry in old.allow}
    for entry in new.allow:
        if (entry.check, entry.path) in before:
            continue
        if entry.approval is None:
            problems.append(
                f"`pillars.allow` adds {entry.check} for {entry.path} — an allowlist only shrinks; "
                "the owner records the exception in a terminal (`agentsmith approve`) and the entry "
                "carries `\"approval\": \"A-xxxxxxxx\"`"
            )
        elif entry.approval not in known:
            problems.append(
                f"`pillars.allow` cites {entry.approval} for {entry.check} {entry.path}, which is not in "
                f"{gm.APPROVALS_FILE}"
            )
    return problems


# ── what counts as first-party code ──────────────────────────────────────────


def first_party(path: str) -> bool:
    """A fixture is not a model and a test double is not a route: flagging test
    files would teach every repo to allowlist its test directory."""
    if not path.endswith(".py"):
        return False
    parts = path.split("/")
    name = parts[-1]
    return not (name.startswith("test_") or name == "conftest.py"
                or {"test", "tests"} & set(parts[:-1]))


# ── the checks ───────────────────────────────────────────────────────────────


def _decorator_name(node: ast.expr) -> str:
    """`@app.get("/x")` -> "app.get"; `@traced` -> "traced"."""
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Attribute):
        return f"{_decorator_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _p7_pydantic(path: str, tree: ast.AST) -> List[str]:
    """P7: models are Pydantic V2.

    Stated limit: the tree cannot tell an internal value object from a model
    built out of unvalidated input, so this flags both. The allowlist carries
    the difference, in a sentence a person wrote.
    """
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            _decorator_name(d).rsplit(".", 1)[-1] == "dataclass" for d in node.decorator_list
        ):
            problems.append(f"`class {node.name}` is a dataclass (line {node.lineno}) — "
                            "models are Pydantic V2 (BaseModel), which validates on the receiving side")
    if problems:
        return problems
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "dataclasses":
            return [f"imports dataclasses (line {node.lineno}) — models are Pydantic V2 (BaseModel)"]
        if isinstance(node, ast.Import) and any(alias.name == "dataclasses" for alias in node.names):
            return [f"imports dataclasses (line {node.lineno}) — models are Pydantic V2 (BaseModel)"]
    return []


_ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
_COMMAND_DECORATORS = {"command"}
_TRACING_DECORATORS = {"traced", "trace", "instrument", "agent_span"}
_SPAN_CALLS = {"agent_span", "gate_span", "start_as_current_span", "start_span"}


def _opens_span(node: ast.AST) -> bool:
    return any(
        isinstance(inner, ast.Call)
        and _decorator_name(inner.func).rsplit(".", 1)[-1] in _SPAN_CALLS
        for inner in ast.walk(node)
    )


def _p3_tracing(path: str, tree: ast.AST) -> List[str]:
    """P3: an entrypoint emits a span.

    Stated limit: an entrypoint that is not declared by a decorator is not
    found, and a handler that delegates to a helper which traces reads as
    untraced. The design-time question covers both; this covers the shape a
    script can see.
    """
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        kind = None
        for decorator in node.decorator_list:
            name = _decorator_name(decorator)
            last = name.rsplit(".", 1)[-1]
            if last in _TRACING_DECORATORS:
                kind = None
                break
            if "." in name and last in _ROUTE_METHODS:
                kind = "route"
            elif "." in name and last in _COMMAND_DECORATORS:
                kind = "CLI command"
        if kind and not _opens_span(node):
            problems.append(
                f"`{node.name}` is a {kind} (line {node.lineno}) that opens no span — "
                "wrap it in `agent_span(...)`, or every call through it is invisible"
            )
    return problems


class Check(NamedTuple):
    pillar: int
    run: Callable[[str, ast.AST], List[str]]


CHECKS: Dict[str, Check] = {
    "P3-tracing": Check(3, _p3_tracing),
    "P7-pydantic": Check(7, _p7_pydantic),
}


def active_checks(registry: "gm.Registry") -> Dict[str, Check]:
    """The checks this registry turns on. Empty is a real answer: a repo whose
    registry marks no pillar `mechanical` was not checked, which is not the same
    as passing (`ambiguous-signals`)."""
    mechanical = {p.id for p in registry.pillars if "mechanical" in p.check}
    return {name: check for name, check in CHECKS.items() if check.pillar in mechanical}


def _file_problems(path: str, text: str, checks: Dict[str, Check], allowed: Set[Tuple[str, str]]) -> List[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []  # not this gate's job to report; ruff and the test run both fail on it
    problems = []
    for name, check in checks.items():
        if (name, path) in allowed:
            continue
        problems.extend(f"{name}: {path} {problem}" for problem in check.run(path, tree))
    return problems


def mechanical_problems(
    files: Sequence[str],
    read: Callable[[str], Optional[str]],
    registry: "gm.Registry",
    policy: gm.PillarPolicy,
) -> List[str]:
    """The checks over the files one commit touches — whole-file, not the added
    lines: how a module is built is not answerable line by line. A repo adopts
    without fixing what it already owns, and pays when it next edits a file."""
    checks = active_checks(registry)
    if not checks:
        return []
    allowed = {(entry.check, entry.path) for entry in policy.allow}
    problems: List[str] = []
    for path in sorted(files):
        if not first_party(path):
            continue
        text = read(path)
        if text is None:
            continue  # deleted in this commit
        problems.extend(_file_problems(path, text, checks, allowed))
    return problems


def repo_problems(root: Path, registry: "gm.Registry", policy: gm.PillarPolicy) -> List[str]:
    """The same checks over everything the repo tracks: what it would have to
    fix or allowlist, which is what someone asking about the repo means."""
    tracked = [f for f in _git(root, "ls-files", "*.py").splitlines() if f]
    def read(path: str) -> Optional[str]:
        full = root / path
        try:
            return full.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
    return mechanical_problems(tracked, read, registry, policy)


# ── evidence tokens ──────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False).stdout


def evidence_resolver(root: Path, rev: str) -> Resolver:
    """Does this token name anything? A tracked path or glob, or text a tracked
    source file holds — one rule covering a path, a test id and a span name.

    Markdown is searched for paths but not for content: the records are
    markdown, and a design that could resolve its own token would be certifying
    itself. `rev` "" is the index, what the commit being made will contain.
    """
    from fnmatch import fnmatch

    listing = ["ls-files"] if not rev else ["ls-tree", "-r", "--name-only", rev]
    tracked = [f for f in _git(root, *listing).splitlines() if f]
    known = set(tracked)
    seen: Dict[str, bool] = {}

    def resolve(token: str) -> bool:
        if token in seen:
            return seen[token]
        found = token in known or any(fnmatch(path, token) for path in tracked)
        if not found:
            grep = ["grep", "-q", "-F", "-e", token] + ([rev] if rev else ["--cached"]) + ["--", ":!*.md"]
            found = subprocess.run(["git", *grep], cwd=root, capture_output=True, check=False).returncode == 0
        seen[token] = found
        return found

    return resolve
