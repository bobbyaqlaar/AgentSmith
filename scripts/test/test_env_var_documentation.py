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

IT COVERS THE PORTAL TOO, since 2026-08-25. `_source_files` had listed
`portal/*.py` from the beginning — the intent was always there — and the portal
contains no Python at all, so eighteen TypeScript-side variables (every SSO
setting, the audit HMAC key, the OTLP endpoints) were outside every gate this
repo has. A glob that reaches for a directory written in another language is
not coverage.

Adding a variable is therefore a two-line change: read it, and say what it does
in docs/UserManual.md's "Runtime Flags" section.
"""

from __future__ import annotations

import re
import sys
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_READ = re.compile(
    r'os\.environ(?:\.get)?[\(\[]\s*["\']([A-Z][A-Z0-9_]{3,})["\']'
    r'|os\.getenv\(\s*["\']([A-Z][A-Z0-9_]{3,})["\']'
)

# The TypeScript half. `process.env.NAME` is the common form; `env.NAME` is the
# one the portal uses wherever a function takes an env object so it can be
# tested (lib/environment.ts, lib/ssoRevocationMode.ts, lib/spanIdentity.ts).
# `process.env[someVar]` — lib/bearerAuth's parameterised gate — cannot be
# resolved statically and is covered by the variables its CALLERS name.
_READ_TS = re.compile(r'(?:process\.env|\benv)\.([A-Z][A-Z0-9_]{3,})\b')

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
    # Set by the framework the portal runs on, not read as configuration.
    "NEXT_RUNTIME",
    "NODE_ENV",
}


def _source_files() -> list[Path]:
    """Every shipped Python file, recursively.

    The globs used to be `runtime/*.py scripts/*.py runtime/workflows/*.py
    portal/*.py` — one level deep, so `runtime/machine/`, `scripts/security/`,
    `scripts/security/runners/` and `examples/` were outside every gate this repo
    has, and `portal/*.py` matched nothing by construction (the portal is
    TypeScript; `_portal_source_files` covers it). Same defect as the one this
    file's docstring records for the portal, one directory level along.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files",
         "runtime/**/*.py", "runtime/*.py", "scripts/**/*.py", "scripts/*.py",
         "examples/**/*.py", "examples/*.py"],
        capture_output=True, text=True,
        check=False,
    ).stdout.split()
    return [REPO / p for p in dict.fromkeys(out) if "/test" not in p and "/test_" not in p]


# Shell reads the environment too, and no sweep here has ever looked at it:
# install-ai-stack.sh, hooks/*, .githooks/* and the on-prem scripts. The work is
# telling an INPUT from a LOCAL — a name assigned anywhere in the file is a local
# however it is later read, and a name read without ever being assigned is an
# input. A first version keyed on `${VAR:-default}` alone and called three
# obvious locals inputs (.agent-rfc/designs/audit-notes-resolved.md).
_SH_ASSIGN = re.compile(r"(?<![$\w}])\b([A-Z][A-Z0-9_]{2,})=")
_SH_FOR = re.compile(r"\bfor\s+([A-Z][A-Z0-9_]{2,})\b")
_SH_READ = re.compile(r"\bread\b[^\n]*?\s([A-Z][A-Z0-9_]{2,})\s*$", re.M)
_SH_USE = re.compile(r"\$\{?([A-Z][A-Z0-9_]{2,})\}?")
# Set by the shell or by the CI runner, not by this project.
_AMBIENT = {
    "BASH_SOURCE", "BASH_VERSION", "ZSH_VERSION", "FUNCNAME", "IFS", "OSTYPE", "PWD", "HOME",
    "PATH", "SHELL", "USER", "LANG", "LC_ALL", "TERM", "TMPDIR", "RANDOM", "SECONDS", "LINENO",
    "REPLY", "PS1", "PS4", "EDITOR", "VISUAL", "HOSTNAME", "UID", "EUID", "PPID", "OLDPWD",
    "SHLVL", "COLUMNS", "LINES", "GROUPS",
    "GITHUB_TOKEN", "GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_WORKSPACE", "GITHUB_SHA",
    "GITHUB_REF_NAME", "GITHUB_STEP_SUMMARY", "GITHUB_ACTIONS", "RUNNER_TEMP", "CI",
}


def _shell_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "*.sh", "hooks/*", ".githooks/*"],
        capture_output=True, text=True, check=False,
    ).stdout.split()
    return [REPO / p for p in out if (REPO / p).is_file() and "/test" not in p]


def _strip_shell_comments(text: str) -> str:
    """Comments decide nothing, in either direction.

    `hooks/post-checkout` opens with `# Requested by DISABLE_AI_STACK=true for one
    command` — prose about the variable, which the assignment pattern read as an
    assignment and so classified the most important input in the file as a local.
    A `#` starts a comment at a word boundary, the same rule
    `runtime/config._dotenv_value` uses.
    """
    return re.sub(r"(?<![\w$])#.*$", "", text, flags=re.M)


def _shell_inputs() -> dict[str, set[str]]:
    """{variable: files that read it as an input}."""
    found: dict[str, set[str]] = {}
    for path in _shell_files():
        text = _strip_shell_comments(path.read_text(encoding="utf-8", errors="ignore"))
        local = set(_SH_ASSIGN.findall(text)) | set(_SH_FOR.findall(text)) | set(_SH_READ.findall(text))
        for match in _SH_USE.finditer(text):
            name = match.group(1)
            if name in local or name in _AMBIENT:
                continue
            found.setdefault(name, set()).add(str(path.relative_to(REPO)))
    return found


def _portal_source_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "portal/*.ts", "portal/*.tsx",
         "portal/lib/*.ts", "portal/app/**/*.ts", "portal/app/**/*.tsx",
         "portal/components/**/*.tsx", "portal/scripts/*.ts"],
        capture_output=True, text=True,
        check=False,
    ).stdout.split()
    return [REPO / p for p in out if "/test/" not in p]


# What counts as DOCUMENTATION, for both directions of this control.
#
# `.agent-rfc/**` is excluded: designs and reviews are RECORDS of how work was
# done, not a reader's reference, and they legitimately discuss code identifiers.
# A review record naming `SEMVER_LOOP_GUARD` and then `CODE_SUFFIXES` tripped the
# reverse check twice — the second is a Python constant in a test file, not an
# environment variable at all, and neither test can tell the difference from an
# all-caps token. Excluding records rather than listing each one keeps the two
# directions symmetrical: `.agent-rfc` was already documentation to the forward
# check and would not have been to the reverse one
# (.agent-rfc/designs/sibling-sweep.md).
_RECORDS = (".agent-rfc/",)


def doc_files() -> list[str]:
    """Tracked markdown a reader would look in, records excluded. Shared with
    `test_documented_env_vars_exist.py`, so "documented" means one thing."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "*.md"], capture_output=True, text=True, check=False
    ).stdout.split()
    return [p for p in out if not p.startswith(_RECORDS)]


def _documented_text() -> str:
    return "".join((REPO / p).read_text(errors="ignore") for p in doc_files() if (REPO / p).exists())


def test_the_portal_sweep_actually_finds_portal_files() -> None:
    """A sweep that resolves to nothing passes over nothing.

    The reason this test exists is that the Python sweep it sits beside already
    globbed `portal/*.py` and matched zero files for months without anyone
    noticing — the failure mode is silence, not an error.
    """
    files = _portal_source_files()
    assert len(files) >= 20, f"expected the portal's TypeScript sources, found {len(files)}"
    names = {p.name for p in files}
    assert "middleware.ts" in names, "middleware.ts missing — the glob is wrong, not the repo"


def test_every_portal_env_var_is_documented() -> None:
    docs = _documented_text()
    undocumented: dict[str, str] = {}
    for path in _portal_source_files():
        if not path.exists():
            continue
        for match in _READ_TS.finditer(path.read_text(errors="ignore")):
            name = match.group(1)
            if name in _EXEMPT or name in docs:
                continue
            undocumented.setdefault(name, str(path.relative_to(REPO)))

    assert not undocumented, (
        "environment variables the PORTAL reads but documented in no .md file:\n"
        + "\n".join(f"  {k:28} {v}" for k, v in sorted(undocumented.items()))
        + "\n\nAdd them to portal/README.md or docs/UserManual.md's Ops Portal section, "
          "and to portal/.env.example — the file the setup steps tell you to copy."
    )


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
        + "\n\nAdd them to docs/UserManual.md's 'Runtime Flags (Environment "
          "Variables)' section — an undiscoverable knob is not configurable."
    )


def test_security_knobs_are_in_the_canonical_reference() -> None:
    """The controls that change what is ENFORCED get a higher bar than
    "mentioned somewhere": they belong in the manual operators actually read.

    `TOOL_ALLOWLIST_STRICT` is the cautionary case — a tenant CI was already
    depending on it while it appeared in no document at all.
    """
    manual = (REPO / "docs/UserManual.md").read_text(encoding="utf-8")
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
        assert name in manual, f"{name} missing from docs/UserManual.md's runtime flags"


def test_fail_closed_behaviour_is_stated_not_just_the_variable() -> None:
    """Naming `TOOL_ALLOWLIST_STRICT` without saying it denies everything when
    no allowlist is loaded would leave a reader with the opposite expectation —
    strict modes are usually read as "enforce what is listed", not "deny all"."""
    manual = (REPO / "docs/UserManual.md").read_text(encoding="utf-8")
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
    """docs/UserManual.md › Command Reference is designated the canonical command reference, so a
    command the CLI ships but the manual never lists is unreachable by anyone
    who has not read the parser.

    `ai-stack-required-models` was the cautionary case: it is the correct way
    to know which Ollama models to pull, and the manual meanwhile told users to
    pull three models the framework does not route to. The commands were shell
    functions then and are `agentsmith` subcommands now; the check reads the
    parser, which is what a user actually gets.
    """
    import argparse

    sys.path.insert(0, str(REPO))
    from runtime.cli import build_parser

    def leaves(parser: argparse.ArgumentParser, path: tuple[str, ...] = ()) -> list[str]:
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            return [" ".join(path)]
        return [leaf for a in subs for name, child in a.choices.items() for leaf in leaves(child, (*path, name))]

    shipped = {leaf for leaf in leaves(build_parser()) if not leaf.startswith("hooks ")}  # internal, for the hooks
    manual = (REPO / "docs/UserManual.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| `agentsmith ([a-z][a-z -]*?)(?: [<\[-][^`]*)?`", manual, re.M))

    assert len(shipped) >= 15, f"the parser walk found too few commands: {sorted(shipped)}"
    # A row may carry the command's positional choice (`agentsmith dashboard start`).
    missing = sorted(leaf for leaf in shipped if not any(row == leaf or row.startswith(leaf + " ") for row in listed))
    assert not missing, f"commands the CLI ships but docs/UserManual.md › Command Reference never lists: {missing}"


def test_the_shell_sweep_finds_shell_files() -> None:
    """A sweep that resolves to nothing passes over nothing — the failure this
    file's docstring records for the portal, asserted for shell before it can
    happen a third time."""
    files = _shell_files()
    assert len(files) > 10, f"the shell sweep found {len(files)} files"
    names = {p.name for p in files}
    assert "install-ai-stack.sh" in names and "post-checkout" in names, sorted(names)[:10]

    found = _shell_inputs()
    assert len(found) > 15, f"only {len(found)} shell inputs — the rule stopped working"
    # Names that are unambiguously environment inputs in shell, as a positive control.
    for expected in ("DISABLE_AI_STACK", "AGENTSMITH_DIR", "AGENTSMITH_PYTHON"):
        assert expected in found, f"{expected} is read from the environment by shell and was missed"


def test_a_shell_input_is_told_from_a_local() -> None:
    """The distinction the whole sweep rests on. A name assigned anywhere in the
    file is a local HOWEVER it is later read: a first version keyed on
    `${VAR:-default}` alone and reported `RFC_COUNT`, `VENV_VERSION` and
    `GITIGNORE_CHOICE` — each assigned on one line and read with a default on the
    next — as undocumented environment inputs.
    """
    found = _shell_inputs()
    for local in ("RFC_COUNT", "VENV_VERSION", "GITIGNORE_CHOICE", "GREEN", "RULES_STACK_KEY"):
        assert local not in found, (
            f"{local} is assigned in its own file and is a local, not an environment input"
        )


def test_every_shell_environment_input_is_documented() -> None:
    """Same rule the Python and TypeScript sweeps apply, for the third language.
    `install-ai-stack.sh`, `hooks/*` and `.githooks/*` read the environment and
    were outside every gate in this repository."""
    documented = _documented_text()
    missing = {
        name: sorted(files) for name, files in sorted(_shell_inputs().items())
        if not re.search(rf"\b{re.escape(name)}\b", documented)
    }
    assert not missing, (
        "these environment variables are read by shell and documented in no markdown file: "
        f"{missing}"
    )
