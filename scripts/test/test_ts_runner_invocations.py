"""
scripts/test/test_ts_runner_invocations.py — every way this repo runs TypeScript
under Node passes the extension loader.

portal/lib modules import each other with EXTENSIONLESS relative specifiers
(`./constantTime`). tsc resolves those; bare `node --experimental-strip-types`
does not. `test/ts-extension-loader.mjs` closes the gap, and an invocation
missing it fails only at runtime, only once a lib/ module gains its first
relative import, with an ERR_MODULE_NOT_FOUND that looks nothing like the cause.

That is not hypothetical. The loader was added to package.json's `test` and
`test:db` and missed on `scripts/security/runners/_shared.py`'s `node_suite`,
which is a THIRD invocation path. SEC-RBAC-001 then went red the moment
lib/authz.ts gained its first relative import, and main stayed red for three
commits. A `git grep experimental-strip-types` would have shown all of them on
one screen — so this test is that grep, run every time.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RUNNER = "--experimental-strip-types"
LOADER = "--experimental-loader"


def _candidate_files() -> list[Path]:
    """Tracked files PLUS untracked-but-not-ignored ones.

    `git ls-files` alone lists only what is committed, which made this sweep's
    coverage depend on git state: a new call site — or this very file — was
    invisible until it was committed, so the check passed locally and failed in
    CI on the same working tree. `--others --exclude-standard` adds the files
    that are about to be committed, which is exactly the set a pre-push check
    should be looking at.
    """
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [ROOT / line for line in out.stdout.split() if line]


# How far from the runner flag the loader may appear and still count. Python
# and shell call sites build argv across several lines:
#
#     cmd = ["node", "--experimental-strip-types"]
#     if loader.exists():
#         cmd.append("--experimental-loader=./test/ts-extension-loader.mjs")
#
# A line-granularity check calls that a violation and also trips on docstrings
# explaining the flag. A window is the honest granularity for "does this call
# site pass the loader" — and it is still tight enough that a file spawning the
# runner with no loader anywhere near it fails, which is the actual defect.
PROXIMITY_LINES = 12

# The loader itself, whose header explains the flag it exists to complement. It
# cannot pass itself. The only exemption, named explicitly rather than as a
# pattern — a wildcard here is how a real call site slips out of scope.
EXEMPT = {
    "portal/test/ts-extension-loader.mjs",
    # This file. Its docstring necessarily quotes the flag it polices, and the
    # sweep cannot tell prose from a call site — it flagged itself the moment it
    # became tracked. Exempting the checker is narrower than teaching the sweep
    # to parse comments, which is the thing that produced false positives in the
    # portal's edge-safety scan twice in one afternoon.
    "scripts/test/test_ts_runner_invocations.py",
}


def _invocations() -> list[tuple[str, str]]:
    """(where, evidence) for every place that spawns the runner.

    Deliberately a text sweep over tracked files rather than a list of known
    call sites — a hand-kept list of call sites is the thing that was wrong.
    """
    found: list[tuple[str, str]] = []

    package_json = ROOT / "portal" / "package.json"
    for name, script in json.loads(package_json.read_text())["scripts"].items():
        if RUNNER in script:
            found.append((f"portal/package.json scripts.{name}", script))

    for path in _candidate_files():
        if path.suffix not in {".py", ".sh", ".mjs"} or not path.is_file():
            continue
        if str(path.relative_to(ROOT)) in EXEMPT:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for index, line in enumerate(lines):
            if RUNNER not in line:
                continue
            lo = max(0, index - PROXIMITY_LINES)
            hi = min(len(lines), index + PROXIMITY_LINES + 1)
            window = "\n".join(lines[lo:hi])
            found.append((f"{path.relative_to(ROOT)}:{index + 1}", window))
    return found


def test_the_sweep_finds_the_known_invocations() -> None:
    """Guards the guard. If the sweep silently matched nothing, every assertion
    below would pass over an empty list — a green test that examined no code,
    which is the shape this repo keeps finding."""
    where = {w for w, _ in _invocations()}
    assert any("package.json scripts.test" in w for w in where), where
    assert any("package.json scripts.db:migrate" in w for w in where), where
    assert any("runners/_shared.py" in w for w in where), where


def test_every_runner_invocation_passes_the_loader() -> None:
    missing = [
        (where, text)
        for where, text in _invocations()
        if LOADER not in text
    ]
    assert not missing, (
        "these run TypeScript without ts-extension-loader.mjs, so an "
        "extensionless relative import in portal/lib will fail there only:\n"
        + "\n".join(f"  {where}" for where, _ in missing)
    )


def test_shared_root_matches_runtime_root(tmp_path) -> None:
    """`scripts/_shared._repo_root` deliberately mirrors
    `runtime.config.repo_root` rather than importing it: scripts/ is
    machine-installed and runtime/ is a pip package, they are not guaranteed
    co-located, and these scripts run standalone before anything has put the
    install root on sys.path.

    Importing it instead passed the entire local suite — pytest puts the repo
    root on the path — and failed in CI on the first standalone invocation with
    ModuleNotFoundError. So: mirrored, and pinned here, the same arrangement as
    _FALLBACK_EXHAUSTION_MARKERS.
    """
    import os
    import sys as _sys

    _sys.path.insert(0, str(ROOT))
    _sys.path.insert(0, str(ROOT / "scripts"))
    from _shared import _repo_root as shared_root
    from runtime.config import repo_root as runtime_root

    outer = tmp_path / "outer"
    (outer / ".git").mkdir(parents=True)
    tenant = outer / "tenant"
    (tenant / ".agenticframework").mkdir(parents=True)

    cwd = Path.cwd()
    for where in (outer, tenant, tmp_path):
        try:
            os.chdir(where)
            assert shared_root() == runtime_root(), f"disagree at {where}"
        finally:
            os.chdir(cwd)


DOTENV_CASES = [
    "plain",
    "  spaced  ",
    '"quoted value"',
    "'single'",
    "bare # comment",
    "http://h:1#frag",          # a fragment is not a comment
    '"quoted # hash"',          # quotes keep everything between them
    "no-comment#nospace",
    "",
    '"unbalanced',              # the case where the two used to differ
    "value # a # b",
    "tabbed\t# note",
    "# leading",
    "KEY=has=equals",
]


def test_dotenv_parsers_agree() -> None:
    """`runtime.config._dotenv_value` deliberately mirrors
    `scripts/_shared._dotenv_value` — neither module can import the other.
    `runtime/` ships as a pip package that must not depend on machine-installed
    scripts, and scripts run standalone before anything puts runtime on
    sys.path; importing across that boundary the other way broke CI on every
    standalone script.

    The mirror is why this test exists: the second implementation was written
    without checking whether one already existed, and the two disagreed on an
    unterminated quote within a day.
    """
    import sys as _sys

    _sys.path.insert(0, str(ROOT))
    _sys.path.insert(0, str(ROOT / "scripts"))
    from _shared import _dotenv_value as scripts_parse
    from runtime.config import _dotenv_value as runtime_parse

    for case in DOTENV_CASES:
        assert runtime_parse(case) == scripts_parse(case), (
            f"parsers disagree on {case!r}: "
            f"runtime={runtime_parse(case)!r} scripts={scripts_parse(case)!r}"
        )
