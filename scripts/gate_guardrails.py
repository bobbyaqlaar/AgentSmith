"""
scripts/gate_guardrails.py — the commit checks the machine-wide git hooks made,
made by the gate instead (.agent-rfc/designs/vendoring-retired.md).

The installer used to arm four hooks in every repository on a machine through
git's `init.templateDir`; 3.0.0 stops arming them, and a repository is governed
only by the gate it declares. What their pre-commit and commit-msg guarded is
judged here, in `process_gate.commit_verdict` — the one decision behind both
`.githooks/commit-msg` and gate contract 3's `commit` answer:

  - an unresolved AI marker (`MARKERS` below);
  - an empty handler: Python by its syntax tree (check_bare_except.py), an
    empty JS/TS `catch {}`, a Go assignment that discards both values;
  - with an org policy on the machine: no direct `cost_router` import under
    runtime/, at least one RFC at .agent-rfc/*.md, an RFC-NNN in the message.

Over the files the commit stages and the tenant wrote: a file
.agenticframework/scaffold.json vouches for, unchanged since, is skipped, as
the hook skipped it. `process-gates.json` `commit_guardrails: "off"` turns them
off — AgentSmith's own, whose tests carry these markers as fixtures and whose
suite runs the same rules over its tree.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from check_bare_except import find_violations

# Split literals, joined by the compiler: this file ships to every tenant, and a
# marker spelled out here would be one (scripts/test/test_vendored_markers.py).
MARKERS = ("ponytail" ":", "TODO" ": agent", "@agent" "-ignore")
MARKER = re.compile("|".join(re.escape(m) for m in MARKERS))
EMPTY_CATCH = re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}")
GO_DISCARDS_BOTH = re.compile(r"^[ \t]*_\s*,\s*_\s*:?=")
COST_ROUTER_IMPORT = re.compile(
    r"^[ \t]*(import[ \t]+cost_router|from[ \t]+(scripts\.)?cost_router[ \t]+import"
    r"|from[ \t]+scripts[ \t]+import[ \t]+cost_router)")
RFC_REFERENCE = re.compile(r"RFC-[0-9]+")
ORG_POLICY = ".agent-framework/agenticframework-org.yaml"
_JS = (".ts", ".tsx", ".js", ".jsx")


def org_policy_present(home: Optional[Path] = None) -> bool:
    """Enterprise mode, as the hooks decided it: an org policy installed on the machine."""
    return ((home or Path.home()) / ORG_POLICY).is_file()


def _lines(text: str, pattern: re.Pattern) -> List[int]:
    return [n for n, line in enumerate(text.splitlines(), 1) if pattern.search(line)]


def check(files: Iterable[str], read: Callable[[str], Optional[str]], message: str,
          vouched: Iterable[str], enterprise: bool, rfcs: Iterable[str]) -> List[str]:
    """The errors this commit's own staged files and message earn. `read` gives a
    staged file's content (None once deleted); `rfcs` the .agent-rfc/*.md the
    commit leaves at depth 1."""
    skip = set(vouched)
    errors: List[str] = []
    for path in files:
        if path in skip:
            continue
        text = read(path)
        if text is None or "\x00" in text:  # deleted, or binary
            continue
        for n in _lines(text, MARKER):
            errors.append(f"{path}:{n}: an unresolved AI marker ({' / '.join(MARKERS)}) — "
                          "resolve it before committing")
        if path.endswith(".py"):
            for _, n in find_violations(text, path):
                errors.append(f"{path}:{n}: an empty except handler — log or re-raise "
                              "(or mark a deliberate one `# fail-open: <reason>`)")
        elif path.endswith(_JS):
            for n in _lines(text, EMPTY_CATCH):
                errors.append(f"{path}:{n}: an empty catch block — swallowing an error is a safety violation")
        elif path.endswith(".go"):
            for n in _lines(text, GO_DISCARDS_BOTH):
                errors.append(f"{path}:{n}: both return values discarded (`_, _ =`) — handle the error")
        if enterprise and path.startswith("runtime/") and path.endswith(".py"):
            for n in _lines(text, COST_ROUTER_IMPORT):
                errors.append(f"{path}:{n}: a direct cost_router import in runtime/ — go through "
                              "runtime/llm_gateway.py, or budget, degrade ladder and audit are bypassed")
    if enterprise:
        if not any(True for _ in rfcs):
            errors.append("the org policy requires at least one RFC under .agent-rfc/ (.agent-rfc/NNN-name.md)")
        if not RFC_REFERENCE.search(message):
            errors.append("the org policy requires an RFC-NNN reference in the commit message, "
                          "e.g. `feat(auth): add JWT middleware (RFC-001)`")
    return errors
