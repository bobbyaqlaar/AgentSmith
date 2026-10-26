"""
scripts/test/test_design_tree_drift.py — docs/DESIGN.md's repository tree
matches the repository.

`docs/DESIGN.md` › "GitHub Repository" holds the ONLY copy of the repository
tree; README links to it rather than repeating it. So the tree is documentation
that rots the moment a file is added, and it has rotted: the P12 security
additions drifted for months at second level while a top-level-only check
stayed green (ReviewFindings-2026-07-18 A2), and `workflow-templates/` was
missing the two workflows that carry the governance (2026-09-27).

This check used to be sixty lines of Python inlined in a `run:` block in
.github/workflows/self-test.yml, which meant no local command ran it, pytest
could not collect it, ruff and mypy never saw it, mutation_check could not
mutate it, and it had no test of its own. PR #66 is what that costs: the full
local suite passed, 2423 tests, and CI failed on
`['docs/agentic-42001-coverage.md']` missing from the tree. The logic is here
now and the workflow step invokes this file, so "pytest is green" covers it.

The parse is carried over unchanged, deliberately — same regex, same ` / `
splitting, same first-component rule, same DEEP_DIRS — so on any tree where the
step passed or failed, this file does the same; verified against the extracted
step on five trees. What is new: each drift direction is its own test rather
than four lists printed before one exit code, the parser is pinned against a
fixture tree instead of only against the repository it reads, paths resolve from
ROOT so the check no longer depends on being run from the repository root, and
a wildcard entry must now still match something — the step skipped wildcards in
its ghost direction, so `fixtures/*_judge_criteria_base.json` could have
described nothing and never been reported.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

TREE_BLOCK = re.compile(r"### Repository Structure\n\n```\n(.*?)\n```", re.S)
TREE_LINE = re.compile(r"^((?:(?:│   )|(?:    ))*)[├└]── (.+)$")

# Second-level entries are diffed for these directories only. The list is the
# set that has actually drifted: scripts/, runtime/, docs/ and fixtures/ from
# ReviewFindings-2026-07-18 A2, and workflow-templates/ added 2026-09-27 when
# agentsmith-gates.yml and agentsmith-sync.yml turned out to be absent from the
# tree's description of the directory holding them.
DEEP_DIRS = ["scripts", "runtime", "docs", "fixtures", "workflow-templates"]
# Tracked but not worth a tree line: package markers and per-directory ignore
# files say nothing about what a directory is for, and `.claude/` is this
# repository's own agent configuration rather than part of the product.
IGNORE_SECOND = {"__init__.py", ".gitignore"}
IGNORE_TOP = {".DS_Store", ".claude"}


def _tracked_paths() -> list[str]:
    """`git ls-files` — the index, which is what CI's checkout sees.

    The index and not the working tree: a staged file is checked before it is
    committed, and an untracked scratch file in the repository root does not
    turn the suite red. Note that the sibling sweep in
    test_ts_runner_invocations.py deliberately adds `--others
    --exclude-standard`; it has to see a call site at push time whatever git
    thinks. This check instead has to return the same verdict as the CI step it
    replaced, and `--others` would report every untracked file as tree drift.
    """
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line]


def _entries(tree: str) -> list[tuple[int, str]]:
    """(depth, name) per tree line.

    `│   ├── foo.py  # comment` is depth 1, name `foo.py`. A line may carry
    several names (`embeddings.py / vector_store.py`) or a path
    (`k8s/dedicated-tenant/`, which contributes `k8s`).
    """
    entries: list[tuple[int, str]] = []
    for line in tree.splitlines():
        match = TREE_LINE.match(line)
        if not match:
            continue
        depth = len(match.group(1)) // 4
        body = match.group(2).split("#", 1)[0].strip()
        for name in (n.strip() for n in body.split(" / ")):
            if name:
                entries.append((depth, name.rstrip("/").split("/")[0]))
    return entries


def _second_level(entries: list[tuple[int, str]]) -> dict[str, set[str]]:
    """DEEP_DIRS -> the second-level names the tree lists under each."""
    second: dict[str, set[str]] = {directory: set() for directory in DEEP_DIRS}
    current_top = None
    for depth, name in entries:
        if depth == 0:
            current_top = name
        elif depth == 1 and current_top in second:
            second[current_top].add(name)
    return second


def _tree_of(document: str) -> str:
    match = TREE_BLOCK.search(document)
    assert match, (
        "### Repository Structure block missing from docs/DESIGN.md — the tree "
        "this file checks is gone, which would otherwise make every sweep below "
        "pass over an empty set"
    )
    return match.group(1)


def _design_entries() -> list[tuple[int, str]]:
    return _entries(_tree_of((ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")))


def _tracked_second(directory: str, tracked: list[str]) -> set[str]:
    """The second-level names tracked under `directory`, worth-a-tree-line ones
    only.

    One place, because the rule was written twice — once here and once inlined
    into the wildcard sweep's `any(...)`, where the `IGNORE_SECOND` subtraction
    was missing. Nothing in IGNORE_SECOND can change a wildcard verdict today,
    so that was a divergence rather than a defect; it is the divergence that
    gets fixed.
    """
    return {
        path.split("/")[1]
        for path in tracked
        if path.startswith(directory + "/") and path.count("/") >= 1
    } - IGNORE_SECOND


@pytest.fixture(scope="module")
def tracked() -> list[str]:
    """`git ls-files` once per module, not once per test.

    Read-only and shared, the same reason test_gate_steps.py uses a fixture for
    its workflow tree: four tests wanted this and spawned four subprocesses.
    """
    return _tracked_paths()


@pytest.fixture(scope="module")
def entries() -> list[tuple[int, str]]:
    """docs/DESIGN.md parsed once per module. Seven tests wanted it."""
    return _design_entries()


# ── the parser, against a fixture rather than against the repository ─────────

FIXTURE_TREE = """\
├── README.md                   # a trailing comment is not a name
├── scripts/
│   ├── map_codebase.py
│   ├── embeddings.py / vector_store.py
│   ├── test/
│   │   └── test_thing.py
│   └── *_judge_criteria_base.json
├── runtime/
│   └── k8s/dedicated-tenant/   # a path contributes its first component
└── pyproject.toml
"""

FIXTURE_ENTRIES = [
    (0, "README.md"),
    (0, "scripts"),
    (1, "map_codebase.py"),
    (1, "embeddings.py"),
    (1, "vector_store.py"),
    (1, "test"),
    (2, "test_thing.py"),
    (1, "*_judge_criteria_base.json"),
    (0, "runtime"),
    (1, "k8s"),
    (0, "pyproject.toml"),
]


def test_the_parser_reads_every_shape_of_tree_line() -> None:
    """Pins the parse form by form: depth from the indent, the comment stripped,
    a ` / ` pair as two names, a path as its first component, a wildcard kept as
    written so fnmatch can use it later."""
    assert _entries(FIXTURE_TREE) == FIXTURE_ENTRIES


def test_the_parser_ignores_lines_that_are_not_entries() -> None:
    assert _entries("just prose\n\n   │\n") == []


def test_second_level_is_collected_per_directory() -> None:
    second = _second_level(FIXTURE_ENTRIES)
    assert second["scripts"] == {
        "map_codebase.py",
        "embeddings.py",
        "vector_store.py",
        "test",
        "*_judge_criteria_base.json",
    }
    assert second["runtime"] == {"k8s"}
    assert second["docs"] == set(), "a DEEP_DIR absent from the tree collects nothing"
    assert "pyproject.toml" not in second["scripts"], "depth 0 is not second level"


def test_tracked_second_keeps_the_directory_and_drops_the_noise() -> None:
    """Both sweeps that need second-level names now go through here, so the
    `IGNORE_SECOND` subtraction is asserted directly rather than inferred from
    whatever the repository happens to contain — which is how the wildcard
    sweep came to be missing it."""
    tracked = [
        "scripts/map_codebase.py",
        "scripts/__init__.py",
        "scripts/test/test_thing.py",
        "scripts/.gitignore",
        "scripts",
        "runtime/cli.py",
    ]
    assert _tracked_second("scripts", tracked) == {"map_codebase.py", "test"}
    assert _tracked_second("runtime", tracked) == {"cli.py"}
    assert _tracked_second("docs", tracked) == set()


def test_a_missing_tree_block_is_an_error_not_an_empty_sweep() -> None:
    """The way this check could stop checking: no block, nothing parsed, four
    sweeps over empty sets, all green."""
    with pytest.raises(AssertionError, match="Repository Structure"):
        _tree_of("# docs/DESIGN.md\n\nno tree here\n")


# ── the repository, in the four directions it can drift ──────────────────────


def test_the_tree_parse_found_the_repository(entries) -> None:
    """Guards the guard. If the parse returned nothing — a renamed heading, a
    reformatted tree — the four tests below would compare the repository against
    empty sets and report nothing missing."""
    top = {name for depth, name in entries if depth == 0}
    assert len(top) >= 20, f"only {len(top)} top-level entries parsed: {sorted(top)}"
    second = _second_level(entries)
    assert all(second[directory] for directory in DEEP_DIRS), {
        directory: len(names) for directory, names in second.items()
    }


def test_every_tracked_top_level_entry_is_in_the_tree(entries, tracked) -> None:
    top = {name for depth, name in entries if depth == 0}
    tracked_top = {path.split("/")[0] for path in tracked}
    missing = sorted(tracked_top - top - IGNORE_TOP)
    assert not missing, (
        f"missing from docs/DESIGN.md's tree (top level): {missing} — add each "
        "to the ### Repository Structure block, which is the only copy of the "
        "repository tree"
    )


def test_no_top_level_tree_entry_is_absent_on_disk(entries) -> None:
    top = {name for depth, name in entries if depth == 0}
    ghost = sorted(name for name in top if not (ROOT / name).exists())
    assert not ghost, (
        f"in docs/DESIGN.md's tree but absent on disk (top level): {ghost} — "
        "delete the entry, or restore what it describes"
    )


def test_every_tracked_second_level_entry_is_in_the_tree(entries, tracked) -> None:
    second = _second_level(entries)
    missing = []
    for directory in DEEP_DIRS:
        listed = second[directory]
        missing += [
            f"{directory}/{name}"
            for name in sorted(_tracked_second(directory, tracked))
            if not any(fnmatch.fnmatch(name, pattern) for pattern in listed)
        ]
    assert not missing, (
        f"missing from docs/DESIGN.md's tree (second level): {missing} — these "
        f"directories are diffed one level deep because they have drifted there "
        f"before: {', '.join(DEEP_DIRS)}"
    )


def test_no_second_level_tree_entry_is_absent_on_disk(entries) -> None:
    second = _second_level(entries)
    ghost = []
    for directory in DEEP_DIRS:
        ghost += [
            f"{directory}/{name}"
            for name in sorted(second[directory])
            # A wildcard entry stands for a set of files, so there is no one
            # path to check for; the missing-side test above matches through it
            # with fnmatch instead.
            if "*" not in name and not (ROOT / directory / name).exists()
        ]
    assert not ghost, (
        f"in docs/DESIGN.md's tree but absent on disk (second level): {ghost} — "
        "delete the entry, or restore what it describes"
    )


def test_every_wildcard_tree_entry_still_matches_something(entries, tracked) -> None:
    """The gap the ghost sweep above leaves open.

    A wildcard entry stands for a set of files, so there is no single path to
    test for existence and the sweep above skips it. That makes it the one kind
    of tree line that can describe nothing at all and never be reported: delete
    every `fixtures/*_judge_criteria_base.json` and the entry sits there
    claiming they exist. Matched forward instead — a pattern must still select
    at least one tracked path.
    """
    second = _second_level(entries)
    empty = []
    for directory in DEEP_DIRS:
        names = _tracked_second(directory, tracked)
        for pattern in sorted(name for name in second[directory] if "*" in name):
            if not any(fnmatch.fnmatch(name, pattern) for name in names):
                empty.append(f"{directory}/{pattern}")
    assert not empty, (
        f"these wildcard entries in docs/DESIGN.md's tree match no tracked "
        f"file: {empty} — delete the entry, or restore what it describes"
    )
