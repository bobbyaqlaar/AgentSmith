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
import re
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

# Invocations that CANNOT pass the loader, by the exact `where` string the sweep
# emits — not a pattern over script names, the same choice EXEMPT above makes
# and for the same reason.
#
# portal/Dockerfile's `runner` stage copies scripts/, db/ and package.json and
# not test/, so a `db:migrate` naming ./test/ts-extension-loader.mjs fails in
# the one place the command is documented for. That was the defect 510aaf7
# fixed; portal/test/runtimeImageScripts.test.ts guards it from the other side.
#
# The exemption is sound only while the entry point has nothing for the loader
# to resolve, which is NOT self-evident from this list —
# test_the_exempt_invocations_import_nothing_needing_resolution below is that
# premise, pinned, so the exemption cannot outlive its reason.
EXEMPT_INVOCATIONS = {
    "portal/package.json scripts.db:migrate (scripts/migrate.ts)",
}

# A relative specifier is what the loader exists to resolve. An aliased one
# (`@/lib/authz`, from portal/tsconfig.json compilerOptions.paths) the bare
# runner does not resolve either — tsc and the bundler do — so for an entry
# point that must run under plain `node` it is the same defect wearing a
# different prefix, and both belong in the premise check.
_IMPORT_SPECIFIER = re.compile(
    r"""(?:^|[\s;}])(?:import|export)\b[^'"\n]*?from\s*['"]([^'"]+)['"]"""
    r"""|\bimport\s*\(\s*['"]([^'"]+)['"]"""
    r"""|(?:^|[\s;}])import\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_ENTRY_POINT = re.compile(r"(\S+\.ts)\b")


def _alias_prefixes() -> set[str]:
    """`{"@/"}` for portal/tsconfig.json as it stands.

    Read rather than hardcoded: a second alias would otherwise be outside the
    premise check with nothing saying so. json.loads is deliberately left to
    raise on a tsconfig that grows comments — a swallowed read here would make
    the premise test examine nothing and still pass, which is the shape this
    repo keeps finding.
    """
    tsconfig = json.loads((ROOT / "portal" / "tsconfig.json").read_text())
    paths = tsconfig.get("compilerOptions", {}).get("paths", {})
    return {key.split("*", 1)[0] for key in paths}


def _specifiers(text: str) -> list[str]:
    return [g for match in _IMPORT_SPECIFIER.finditer(text) for g in match.groups() if g]


def _shell_invocations(script: str) -> list[str]:
    """Each `node --experimental-strip-types …` call in a package.json script,
    separately.

    `scripts.test` is a twenty-link `&&` chain. Checked as ONE string, a loader
    dropped from a single link is invisible, because the other nineteen still
    mention the flag and the assertion is a substring test over the whole
    script. That is not hypothetical either: deleting the flag from the first
    link alone left this file green, which is how the hole was found.
    """
    return [part for part in re.split(r"&&|\|\||;", script) if RUNNER in part]


def _invocations() -> list[tuple[str, str]]:
    """(where, evidence) for every place that spawns the runner.

    Deliberately a text sweep over tracked files rather than a list of known
    call sites — a hand-kept list of call sites is the thing that was wrong.
    """
    found: list[tuple[str, str]] = []

    package_json = ROOT / "portal" / "package.json"
    for name, script in json.loads(package_json.read_text())["scripts"].items():
        for part in _shell_invocations(script):
            entry = _ENTRY_POINT.search(part)
            label = f" ({entry.group(1)})" if entry else ""
            found.append((f"portal/package.json scripts.{name}{label}", part))

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
    labels = [w for w, _ in _invocations()]
    where = set(labels)
    assert any("package.json scripts.test" in w for w in where), where
    assert any("package.json scripts.db:migrate" in w for w in where), where
    assert any("runners/_shared.py" in w for w in where), where

    # One entry per LINK of the `&&` chain, not one per script. The split is the
    # whole point — a sweep that stopped splitting would report 1 here and go on
    # passing while nineteen call sites went unchecked — so it is counted
    # against the script text rather than against a number written here, which
    # would need editing every time a portal test suite is added.
    script = json.loads((ROOT / "portal" / "package.json").read_text())["scripts"]["test"]
    links = script.count(RUNNER)
    swept = [w for w in where if w.startswith("portal/package.json scripts.test (")]
    assert links > 1, f"scripts.test is no longer a chain ({links} link) — rewrite this guard"
    assert len(swept) == links, (
        f"scripts.test spawns the runner {links} times but the sweep yielded "
        f"{len(swept)} invocation(s) for it: {sorted(swept)}"
    )

    # `where` is a key, not a caption: test_the_exempt_invocations_… looks
    # exemptions up by it. Two invocations sharing one label (two links of a
    # script with no .ts entry to name them apart) would check only one of them
    # and report nothing — which is why `labels` is kept as a list above and
    # `where` derived from it, rather than sweeping the tree twice.
    duplicates = sorted({w for w in labels if labels.count(w) > 1})
    assert not duplicates, f"two invocations share one `where`: {duplicates}"


def _missing_loader(where: str, text: str) -> bool:
    """True for an invocation that must pass the loader and does not."""
    return LOADER not in text and where not in EXEMPT_INVOCATIONS


def test_the_loader_rule_reports_a_missing_flag() -> None:
    """Positive control for test_every_runner_invocation_passes_the_loader.

    When that test passes, the tree it scanned was clean — so replacing its
    condition with `False` leaves it green and proves nothing about the rule.
    Two synthetic invocations, one each way, are what make the rule itself
    falsifiable, in the same spirit as test_the_sweep_finds_the_known_invocations
    guarding the sweep.
    """
    where = "portal/package.json scripts.made-up (test/x.test.ts)"
    assert _missing_loader(where, f"node {RUNNER} test/x.test.ts")
    assert not _missing_loader(
        where,
        f"node {RUNNER} --experimental-loader=./test/ts-extension-loader.mjs test/x.test.ts",
    )
    for exempt in EXEMPT_INVOCATIONS:
        assert not _missing_loader(exempt, f"node {RUNNER} scripts/migrate.ts"), exempt


def test_every_runner_invocation_passes_the_loader() -> None:
    missing = [
        (where, text)
        for where, text in _invocations()
        if _missing_loader(where, text)
    ]
    assert not missing, (
        "these run TypeScript without ts-extension-loader.mjs, so an "
        "extensionless relative import in portal/lib will fail there only:\n"
        + "\n".join(f"  {where}" for where, _ in missing)
    )


# Every way portal TypeScript names a module, each paired with what the premise
# check must conclude. `_specifiers` returning a non-empty list is not enough:
# if only the dynamic-import alternative broke, migrate.ts's four static imports
# would still parse, the emptiness guard would pass, and `await import("./x")`
# would walk straight through the one check that exists to stop it.
SPECIFIER_SAMPLE = """
import { readFileSync } from "node:fs";
import path from "node:path";
import { Pool } from "pg";
import { a } from "./relative";
import { b } from "../up/one";
import "./side-effect-only";
import type { T } from "@/lib/types";
export { c } from "@/lib/authz";
export * from "./star";
const d = await import("./dynamic");
const e = await import("pg");
// import { lie } from "./commented-out";  <- prose, not a call site
"""
EXPECTED_SPECIFIERS = {
    "node:fs",
    "node:path",
    "pg",
    "./relative",
    "../up/one",
    "./side-effect-only",
    "@/lib/types",
    "@/lib/authz",
    "./star",
    "./dynamic",
}


def _needs_resolution(specifier: str, aliases: tuple[str, ...]) -> bool:
    """True for a specifier plain `node --experimental-strip-types` cannot resolve.

    Named and tested separately because the alias half of it is unreachable from
    the repository as it stands — portal/scripts/migrate.ts imports nothing
    aliased, so deleting `aliases` from this predicate changed no test result.
    A branch no input reaches is not a guard; test_what_counts_as_needing_resolution
    supplies the input.
    """
    return specifier.startswith((".", "/")) or specifier.startswith(aliases)


def test_what_counts_as_needing_resolution() -> None:
    aliases = tuple(_alias_prefixes())
    assert aliases, "portal/tsconfig.json declares no path alias — the premise changed"

    for specifier in ["./constantTime", "../lib/authz", "/abs/path", *(a + "lib/db" for a in aliases)]:
        assert _needs_resolution(specifier, aliases), f"{specifier} resolves without the loader?"
    for specifier in ["pg", "node:fs", "node:path", "next/server", "@opentelemetry/api"]:
        assert not _needs_resolution(specifier, aliases), f"{specifier} flagged, but node resolves it"


def test_the_specifier_sweep_recognises_every_import_form() -> None:
    """Pins `_IMPORT_SPECIFIER` form by form against a literal sample.

    The commented-out line is in the sample on purpose: this sweep does not
    parse comments either (see EXEMPT's note about that), so it is recorded as a
    known false positive rather than left for someone to rediscover. It is
    harmless in the only place it is used — a commented-out relative import in
    an exempt entry point fails the premise test, which is the safe direction.
    """
    found = set(_specifiers(SPECIFIER_SAMPLE))
    assert EXPECTED_SPECIFIERS <= found, (
        "these import forms are no longer recognised: "
        f"{sorted(EXPECTED_SPECIFIERS - found)}"
    )
    assert found - EXPECTED_SPECIFIERS == {"./commented-out"}, sorted(found)


def test_the_exempt_invocations_import_nothing_needing_resolution() -> None:
    """The premise EXEMPT_INVOCATIONS rests on, as a test rather than a comment.

    An entry point is exempt from the loader because there is nothing for the
    loader to do: portal/scripts/migrate.ts imports node:fs, node:url, node:path
    and pg, all of which plain `node --experimental-strip-types` resolves. The
    day it imports `./something`, the exemption is wrong and `npm run db:migrate`
    breaks inside the image with an ERR_MODULE_NOT_FOUND that looks nothing like
    the cause — the failure mode this whole file was written about. So the
    reason is checked, not asserted once in prose.

    Checking the entry point alone is sufficient, not a shortcut: every path
    from it into portal/lib must start with an edge out of it, and that edge is
    relative or aliased. Bare specifiers reach node_modules and `node:` ones the
    runtime, neither of which the loader is involved in.
    """
    swept = {where: text for where, text in _invocations()}
    stale = EXEMPT_INVOCATIONS - set(swept)
    assert not stale, (
        f"these exemptions name invocations the sweep no longer finds: {stale} — "
        "an exemption whose invocation moved stops exempting anything and "
        "silently stops being checked here too"
    )

    aliases = tuple(_alias_prefixes())
    assert aliases, "portal/tsconfig.json declares no path alias — the premise changed"

    checked = []
    for where in sorted(EXEMPT_INVOCATIONS):
        entry = _ENTRY_POINT.search(swept[where])
        assert entry, f"{where} runs no .ts entry point: {swept[where]!r}"
        source = ROOT / "portal" / entry.group(1)
        assert source.is_file(), f"{where} names {source}, which is missing"
        specifiers = _specifiers(source.read_text(encoding="utf-8"))
        assert specifiers, (
            f"{source.relative_to(ROOT)} parsed to NO imports at all — either "
            "the file stopped importing anything or _IMPORT_SPECIFIER stopped "
            "matching, and in the second case the check below examines nothing "
            "and passes"
        )
        offenders = [s for s in specifiers if _needs_resolution(s, aliases)]
        assert not offenders, (
            f"{source.relative_to(ROOT)} is exempt from {LOADER} but imports "
            f"{offenders} — plain `node {RUNNER}` cannot resolve those, so "
            f"{where} is now the ERR_MODULE_NOT_FOUND this file exists to "
            "prevent. Either resolve the import at build time, or carry the "
            "loader into portal/Dockerfile's runner stage and drop the exemption."
        )
        checked.append(str(source.relative_to(ROOT)))

    # Written out rather than counted: a new exemption must be read by a human
    # here, and the diff that adds one is the diff that says which entry point
    # it lets off. `assert checked` alone would accept any exemption at all.
    assert checked == ["portal/scripts/migrate.ts"], (
        f"the exempt entry points changed to {checked} — confirm each one still "
        "has nothing for the loader to resolve, then update this list"
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
