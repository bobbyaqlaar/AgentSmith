"""
scripts/test/test_documented_env_vars_exist.py — every environment variable the
docs name must be read by something.

THE FAILURE THIS EXISTS FOR. Two were not, found 2026-09-01:

  AGENT_SHARED_RFC_DIR    UserManual.md gave two copy-pasteable `export` lines
                          and said "agents and run-evals.py also read from this
                          directory". SPECS.md specified a security boundary for
                          it. Nothing has ever read it.
  AI_STACK_SLACK_WEBHOOK  Listed in SPECS.md's environment table as the Slack
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

# Tokens that look like environment variables but are not ours to implement.
ALLOWED = {
    # Documented as NOT IMPLEMENTED, tracked in FIXES_AND_CLEANUP.md. Listed
    # here so the test stays green while the docs stay honest — remove this
    # entry when the feature is built, and the test starts guarding it.
    "AGENT_SHARED_RFC_DIR",
    # Temporal's own workflow-execution status, quoted in prose.
    "EXECUTION_SUCCEEDED",
    # Node/OpenSSL error string quoted from a real incident.
    "UNABLE_TO_VERIFY_LEAF_SIGNATURE",
}

# Placeholders a reader is meant to substitute (YOUR_GCP_PROJECT_ID, ...).
PLACEHOLDER = re.compile(r"^YOUR_")

# Backticked UPPER_SNAKE with at least one underscore — enough to exclude prose
# words in caps (CASCADE, LICENSE) without hand-listing them.
CANDIDATE = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")


def _docs() -> list[str]:
    return subprocess.check_output(
        ["git", "-C", str(REPO), "ls-files", "*.md"], text=True
    ).split()


def _code_blob() -> str:
    files = subprocess.check_output(
        ["git", "-C", str(REPO), "ls-files"], text=True
    ).split()
    parts = []
    for f in files:
        if f.endswith(CODE_SUFFIXES):
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
