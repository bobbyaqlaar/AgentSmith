"""
scripts/test/test_verify_system_modes.py — `verify_system.py --help` must list
every mode it dispatches.

THE FAILURE THIS EXISTS FOR. `verify_system.py` dispatches on `sys.argv` — nine
`if "--check-x" in sys.argv` tests — rather than argparse. `--help` matched none
of them, fell through to `run_checks()`, and printed a multi-second full system
scan. Exit 0, no usage. The nine modes were documented across five .md files and
discoverable from the tool itself nowhere.

A hand-written usage string then has the obvious failure mode: someone adds a
tenth `--check-*` branch to `__main__` and does not add it to MODES, and it is
invisible again. So the check here is not "does --help print something" but
"does the printed set equal the dispatched set", read out of the source with
`ast` rather than trusted.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "verify_system.py"


def _dispatched_flags() -> set[str]:
    """Every `--check-*` literal compared against sys.argv in `__main__`.

    Parsed rather than imported: importing this module runs its top-level
    dependency probing, which is slow and touches the environment.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    main = [
        n for n in tree.body
        if isinstance(n, ast.If) and ast.dump(n.test).find("__main__") != -1
    ]
    assert main, "no `if __name__ == '__main__':` block found"
    found = set()
    for node in ast.walk(main[0]):
        if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.In):
            left = node.left
            if isinstance(left, ast.Constant) and isinstance(left.value, str):
                if left.value.startswith("--check-"):
                    found.add(left.value)
    return found


def _declared_flags() -> set[str]:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "MODES" for t in node.targets
        ):
            return {flag for flag, _ in ast.literal_eval(node.value)}
    raise AssertionError("MODES not found in verify_system.py")


def test_the_parse_finds_something() -> None:
    """Guard the guard. Both helpers read the source with ast; if the file is
    restructured so neither matches, every assertion below compares two empty
    sets and passes while proving nothing."""
    assert len(_dispatched_flags()) >= 5
    assert len(_declared_flags()) >= 5


def test_every_dispatched_mode_is_documented_in_help() -> None:
    missing = _dispatched_flags() - _declared_flags()
    assert not missing, (
        f"`verify_system.py` dispatches {sorted(missing)} but --help does not "
        f"list them. Add them to MODES — an undiscoverable mode is why this "
        f"test exists."
    )


def test_help_does_not_advertise_a_mode_that_does_not_exist() -> None:
    extra = _declared_flags() - _dispatched_flags()
    assert not extra, (
        f"--help advertises {sorted(extra)}, which `__main__` does not "
        f"dispatch. Those would fall through to the full verification run."
    )


def test_help_exits_zero_and_prints_usage_rather_than_running_the_scan() -> None:
    """The original defect, end to end. `--help` must be fast and must not be
    the full system scan — checking only for exit 0 would pass on the bug,
    since the scan exited 0 too."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("usage:"), proc.stdout[:200]
    # The scan's banner. Its presence means --help fell through again.
    assert "System Verification" not in proc.stdout, (
        "--help ran the full verification instead of printing usage"
    )
    for flag in _declared_flags():
        assert flag in proc.stdout, f"{flag} missing from --help output"


def test_docs_do_not_reference_an_unknown_check_mode() -> None:
    """The reverse direction: a doc telling a reader to run a mode the script
    does not have.

    Each flag is attributed to the nearest PRECEDING script name, because
    `--check-*` is not a namespace and a doc line routinely names two tools:

        `generate-ide-config.py --check-only` ... and `verify_system.py --check-kg`

    Matching every `--check-` token in the repo flagged `--check-only` in five
    files; scoping to lines mentioning verify_system still flagged it in two,
    since both scripts appear on the same line. `--check-` alone appears in
    prose as a bare prefix and is excluded.
    """
    dispatched = _dispatched_flags()
    docs = subprocess.check_output(
        ["git", "-C", str(REPO), "ls-files", "*.md"], text=True
    ).split()
    token = re.compile(r"([A-Za-z0-9_-]+\.py|--check-[a-z0-9-]+)")
    bad = {}
    for d in docs:
        text = (REPO / d).read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            owner = None
            for tok in token.findall(line):
                if tok.endswith(".py"):
                    owner = tok
                elif owner == "verify_system.py" and tok != "--check-":
                    if tok not in dispatched:
                        bad.setdefault(tok, []).append(d)
    assert not bad, f"docs reference non-existent verify_system modes: {bad}"
