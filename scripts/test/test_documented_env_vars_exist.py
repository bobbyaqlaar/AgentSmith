"""
scripts/test/test_documented_env_vars_exist.py — every environment variable the
docs name must be read by something.

THE FAILURE THIS EXISTS FOR. Two were not, found 2026-09-01:

  AGENT_SHARED_RFC_DIR    docs/UserManual.md gave two copy-pasteable `export` lines
                          and said "agents and run-evals.py also read from this
                          directory". docs/DESIGN.md specified a security boundary for
                          it. Nothing has ever read it.
  AI_STACK_SLACK_WEBHOOK  Listed in docs/DESIGN.md's environment table as the Slack
                          alert webhook, directly above AGENT_NOTIFY_WEBHOOK,
                          which is the one scripts/notifier.py actually reads. A
                          reader wiring up Slack had even odds of picking the
                          one with nothing behind it.

This class fails silently by construction. A misspelled flag gets you an
argparse error; a wrong path gets you ENOENT. An unread environment variable
produces no error at any layer — `os.environ.get` on a name nobody queries is
just absent — so the only thing between a user and a false belief is whether
the documentation happens to be true. That makes it worth a test rather than a
one-time sweep.

Deliberately a weak check: "appears somewhere in a source file", not "is read
with the right precedence". Anything stronger would need to model how each
variable is consumed, and a test that has to be rewritten whenever config
plumbing moves gets deleted rather than fixed. This catches the failure that
actually happened — a name with nothing behind it at all.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CODE_SUFFIXES = (
    ".py", ".ts", ".tsx", ".js", ".mjs", ".yml", ".yaml",
    ".sh", ".json", ".txt", ".toml", ".cfg",
)

# Shell with no extension: every git hook. `.sh` was in the list from the start,
# so this looked covered — but `hooks/post-commit`, `.githooks/process-gate` and
# their siblings carry no suffix, and they are where SEMVER_LOOP_GUARD,
# DISABLE_AI_STACK, AGENT_KG_DEFER and AGENTSMITH_AUTOPUSH are read. Documenting
# SEMVER_LOOP_GUARD in a review record was enough to make this test call it
# "read by nothing" (.agent-rfc/designs/audit-notes-resolved.md).
EXTENSIONLESS_SOURCE_DIRS = ("hooks/", ".githooks/")


def _is_source(rel: str) -> bool:
    if rel.endswith(CODE_SUFFIXES):
        return True
    return rel.startswith(EXTENSIONLESS_SOURCE_DIRS) and "." not in Path(rel).name

# Tokens that look like environment variables but are not ours to implement.
ALLOWED = {
    # Documented as NOT IMPLEMENTED, tracked in docs/PRODUCT_BACKLOG.md. Listed
    # here so the test stays green while the docs stay honest — remove this
    # entry when the feature is built, and the test starts guarding it.
    "AGENT_SHARED_RFC_DIR",
    # Temporal's own workflow-execution status, quoted in prose.
    "EXECUTION_SUCCEEDED",
    # Node/OpenSSL error string quoted from a real incident.
    "UNABLE_TO_VERIFY_LEAF_SIGNATURE",
    # Removed from docs/DESIGN.md's env table (never implemented — see CHANGELOG).
    # CHANGELOG.md narrates it as history, same as any other removed
    # identifier a changelog legitimately names; that citation is not a
    # documentation claim that the variable works.
    "AI_STACK_SLACK_WEBHOOK",
    # Exported by the installer's shell-function block and read by nothing;
    # removed with it on 2026-09-14. The design note and CHANGELOG name them as
    # what was removed, which is not a claim that they work.
    "OS_LLM_BASE_URL",
    "OS_LLM_API_KEY",
    # The portal's two trusted request headers before phase 1 (2026-09-18), replaced
    # by one, x-af-grants (portal/lib/authz.ts GRANTS_HEADER). The archive names
    # them in the history of an earlier refactor, which is not a claim they exist.
    "ROLE_HEADER",
    "TENANT_SCOPE_HEADER",
}

# Placeholders a reader is meant to substitute (YOUR_GCP_PROJECT_ID, ...).
PLACEHOLDER = re.compile(r"^YOUR_")

# Backticked UPPER_SNAKE with at least one underscore — enough to exclude prose
# words in caps (CASCADE, LICENSE) without hand-listing them.
CANDIDATE = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")


def _docs() -> list[str]:
    """The same markdown the forward check treats as documentation.

    Both directions used to glob every tracked `*.md`, which made design and
    review records under `.agent-rfc/` count as documentation offering a knob.
    They are records of how work was done and they discuss code identifiers: a
    review naming `SEMVER_LOOP_GUARD`, and later `CODE_SUFFIXES` — a Python
    constant, not an environment variable — each made this check report a
    variable as implemented by nothing. Neither test can tell an environment
    variable from any other all-caps token, so the fix is to agree on where a
    reader looks, in ONE place (.agent-rfc/designs/sibling-sweep.md).
    """
    from test_env_var_documentation import doc_files

    return doc_files()


def _code_blob() -> str:
    """Every tracked source file EXCEPT this one.

    This file names AGENT_SHARED_RFC_DIR and the removed Slack variable — in
    ALLOWED and in the docstring — so including it would make every orphan
    "appear in code" and both checks below vacuous. It found that out the
    embarrassing way: the suite passed locally, where this file was still
    untracked and therefore invisible to `git ls-files`, and failed on the
    first CI run after it was committed.

    Which is the same lesson as `test_standalone_without_runtime.py`: a check
    whose result depends on the state of the checkout is not checking what it
    claims to.
    """
    self_path = str(Path(__file__).resolve().relative_to(REPO))
    files = subprocess.check_output(
        ["git", "-C", str(REPO), "ls-files"], text=True
    ).split()
    parts = []
    for f in files:
        if f == self_path or not _is_source(f):
            continue
        try:
            parts.append((REPO / f).read_text(errors="replace"))
        except OSError:
            pass
    return "\n".join(parts)


def test_the_scan_finds_candidates() -> None:
    """Guard the guard: if the regex or the doc list breaks, the real test
    below iterates over nothing and passes while checking nothing."""
    found = set()
    for d in _docs():
        found |= set(CANDIDATE.findall((REPO / d).read_text(errors="replace")))
    assert len(found) > 40, f"only {len(found)} candidates — has the scan broken?"
    assert "AGENT_NOTIFY_WEBHOOK" in found


def test_every_documented_env_var_is_read_somewhere() -> None:
    blob = _code_blob()
    orphans: dict[str, list[str]] = {}
    for d in _docs():
        for name in set(CANDIDATE.findall((REPO / d).read_text(errors="replace"))):
            if name in ALLOWED or PLACEHOLDER.match(name):
                continue
            if name in blob:
                continue
            orphans.setdefault(name, []).append(d)
    assert not orphans, (
        "documented but read by nothing — either implement it, or say in the "
        "doc that it is not implemented and add it to ALLOWED with the reason:\n"
        + "\n".join(f"  {k}  ({', '.join(sorted(v))})" for k, v in sorted(orphans.items()))
    )


def test_allowlist_entries_are_still_orphans() -> None:
    """An ALLOWED entry that HAS been implemented should leave the allowlist,
    or it silently stops being checked. This is the direction allowlists
    normally rot in."""
    blob = _code_blob()
    implemented = [n for n in ALLOWED if n in blob]
    assert not implemented, (
        f"{implemented} are now referenced in code — remove them from ALLOWED "
        f"so they are covered by the test again."
    )


def test_the_sweep_reaches_extensionless_shell() -> None:
    """`.sh` was in CODE_SUFFIXES from the start, which made shell look covered
    while every git hook — extensionless — was invisible. A sweep that misses the
    files a variable is actually read in reports it as implemented by nothing.
    """
    blob = _code_blob()
    assert "SEMVER_LOOP_GUARD" in blob, (
        "hooks/post-commit reads SEMVER_LOOP_GUARD and the sweep cannot see it"
    )
    for name in ("DISABLE_AI_STACK", "AGENTSMITH_AUTOPUSH"):
        assert name in blob, f"{name} is read by an extensionless hook and was missed"
