"""
scripts/test/test_env_var_documentation.py — an environment variable the code
reads must appear in the docs.

A knob nobody can find is not configurable. Twenty-one variables were readable
only from the source, five of them security controls with no mention in ANY
markdown file — including `TOOL_ALLOWLIST_STRICT`, which KYC Sentinel's CI
already sets, and which fails CLOSED (strict with no allowlist loaded denies
every tool). Getting that wrong is the difference between an enforced allowlist
and an advisory one.

The check is deliberately loose about WHERE: any tracked .md counts, so a
variable documented in a design note or a template README is fine. It only
fails on variables documented nowhere at all.

Adding a variable is therefore a two-line change: read it, and say what it does
in UserManual.md's "Runtime Flags" section.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_READ = re.compile(
    r'os\.environ(?:\.get)?[\(\[]\s*["\']([A-Z][A-Z0-9_]{3,})["\']'
    r'|os\.getenv\(\s*["\']([A-Z][A-Z0-9_]{3,})["\']'
)

# Variables set BY the platform rather than read as configuration — documenting
# them would be documenting someone else's contract.
_EXEMPT = {
    "GITHUB_TOKEN",       # injected into every GitHub Actions run
    "GITHUB_REPOSITORY",
    "GITHUB_RUN_ID",
    "GITHUB_SHA",
    "GITHUB_REF_NAME",
    "GITHUB_ACTIONS",
    "GITHUB_EVENT_NAME",
    "GITHUB_OUTPUT",
    "GITHUB_STEP_SUMMARY",
    "HOME",
    "PATH",
    "PWD",
    "USER",
    "SHELL",
    "TERM",
    "CI",
    "VIRTUAL_ENV",
    "PYTHONPATH",
    "TMPDIR",
}


def _source_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "runtime/*.py", "scripts/*.py",
         "runtime/workflows/*.py", "portal/*.py"],
        capture_output=True, text=True,
    ).stdout.split()
    return [REPO / p for p in out if "/test" not in p and "/test_" not in p]


def _documented_text() -> str:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "*.md"], capture_output=True, text=True
    ).stdout.split()
    return "".join((REPO / p).read_text(errors="ignore") for p in out if (REPO / p).exists())


def test_every_env_var_the_code_reads_is_documented() -> None:
    docs = _documented_text()
    undocumented: dict[str, str] = {}
    for path in _source_files():
        if not path.exists():
            continue
        for match in _READ.finditer(path.read_text(errors="ignore")):
            name = match.group(1) or match.group(2)
            if name in _EXEMPT or name in docs:
                continue
            undocumented.setdefault(name, str(path.relative_to(REPO)))

    assert not undocumented, (
        "environment variables read by the code but documented in no .md file:\n"
        + "\n".join(f"  {k:28} {v}" for k, v in sorted(undocumented.items()))
        + "\n\nAdd them to UserManual.md's 'Runtime Flags (Environment "
          "Variables)' section — an undiscoverable knob is not configurable."
    )


def test_security_knobs_are_in_the_canonical_reference() -> None:
    """The controls that change what is ENFORCED get a higher bar than
    "mentioned somewhere": they belong in the manual operators actually read.

    `TOOL_ALLOWLIST_STRICT` is the cautionary case — a tenant CI was already
    depending on it while it appeared in no document at all.
    """
    manual = (REPO / "UserManual.md").read_text(encoding="utf-8")
    for name in (
        "PROMPT_GUARD",
        "PROMPT_DENYLIST_PATH",
        "TOOL_ALLOWLIST_STRICT",
        "TOOL_ALLOWLIST_PATH",
        "MODERATION_HOOK",
        "INPUT_GUARDRAIL",
        "ENABLE_IP_REDACTION",
        "SECURITY_STRICT",
    ):
        assert name in manual, f"{name} missing from UserManual.md's runtime flags"


def test_fail_closed_behaviour_is_stated_not_just_the_variable() -> None:
    """Naming `TOOL_ALLOWLIST_STRICT` without saying it denies everything when
    no allowlist is loaded would leave a reader with the opposite expectation —
    strict modes are usually read as "enforce what is listed", not "deny all"."""
    manual = (REPO / "UserManual.md").read_text(encoding="utf-8")
    # The TABLE ROW, not the first mention — the section's own prose names the
    # variable too, and matching that would pass without the behaviour stated.
    row = next(
        (
            line for line in manual.splitlines()
            if line.startswith("|") and "`TOOL_ALLOWLIST_STRICT`" in line
        ),
        "",
    )
    assert "closed" in row.lower() or "every tool is denied" in row.lower(), (
        "the TOOL_ALLOWLIST_STRICT row must state that it fails closed"
    )


# ── Command reference completeness ───────────────────────────────────────────


def test_every_shipped_command_is_in_the_canonical_reference() -> None:
    """UserManual.md §17 is designated the canonical command reference, so a
    shell function the installer defines but the manual never lists is
    unreachable by anyone who has not read the installer.

    `ai-stack-required-models` was the cautionary case: it is the correct way
    to know which Ollama models to pull, `ai-stack-check` uses the same lookup
    internally, and the manual meanwhile told users to pull three models the
    framework does not route to.
    """
    installer = (REPO / "install-ai-stack.sh").read_text(encoding="utf-8")
    manual = (REPO / "UserManual.md").read_text(encoding="utf-8")

    defined = set(re.findall(r"^function (ai-[a-z-]+)\(\)", installer, re.M))
    listed = set(re.findall(r"^\| `(ai-[a-z-]+)`", manual, re.M))

    assert defined, "no ai-* functions found — the extraction pattern broke"
    missing = sorted(defined - listed)
    assert not missing, (
        f"commands the installer defines but UserManual.md's tables never list: "
        f"{missing}"
    )
