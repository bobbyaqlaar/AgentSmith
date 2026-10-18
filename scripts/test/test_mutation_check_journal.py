"""
scripts/test/test_mutation_check_journal.py — a killed mutation run undoes
itself (.agent-rfc/designs/mutation-check-journal.md).

This harness rewrites the files it mutates. SIGINT and SIGTERM are handled and
an exception is handled, but a SIGKILL leaves the mutant on disk, and the old
backstop — refusing to start when a catalogue file is dirty — is skipped by
`--allow-dirty`, which is exactly what you pass while your own work is
uncommitted. On 2026-10-16 that left `_ours(...)` dropped from
`scripts/rules_port.py` for hours, through two later runs.

The journal is what lets the tool recognise its own writes: a file whose
contents are byte-for-byte the mutant it recorded is restored; anything else is
handed to a human.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import mutation_check as mc

PRISTINE = "def placement(existing):\n    return 'whole' if _ours(existing) else 'block'\n"
MUTANT = "def placement(existing):\n    return 'whole'\n"
TARGET = "scripts/rules_port.py"          # the file today's residue was found in


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture()
def repo(monkeypatch, tmp_path):
    """A repo-shaped tmp dir, with mutation_check pointed at it."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "scripts").mkdir()
    monkeypatch.setattr(mc, "REPO", tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _journal(repo: Path, *, on_disk: str, pristine: str = PRISTINE, mutant: str = MUTANT,
             copy: bool = True) -> Path:
    """Leave behind exactly what a killed run leaves behind."""
    target = repo / TARGET
    target.write_text(on_disk, encoding="utf-8")
    if copy:
        mc._write_journal(TARGET, pristine, mutant, "rules_port: placement ignores _ours")
    else:
        path = mc._journal_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "path": TARGET, "pristine_sha256": _sha(pristine), "mutant_sha256": _sha(mutant),
            "pristine_copy": str(repo / ".git" / "gone.txt"), "label": "rules_port: placement",
            "pid": 1, "started_at": "2026-10-16T12:00:00Z",
        }), encoding="utf-8")
    target.write_text(on_disk, encoding="utf-8")   # _write_journal does not touch the file
    return target


def test_a_killed_run_is_undone_on_the_next_start(repo) -> None:
    """The file still holds exactly what this tool wrote, so it is ours to put
    back without asking."""
    target = _journal(repo, on_disk=MUTANT)

    assert mc._recover_journal() == 0
    assert target.read_text(encoding="utf-8") == PRISTINE
    assert not mc._journal_path().exists()


def test_an_edited_file_is_never_silently_overwritten(repo) -> None:
    """Neither the mutant nor the pristine text: someone has worked on it since
    the kill. Refuse and hand both versions over; never guess."""
    edited = MUTANT + "\n# a human kept working here\n"
    target = _journal(repo, on_disk=edited)

    assert mc._recover_journal() == 1
    assert target.read_text(encoding="utf-8") == edited, "the file must not be touched"
    assert mc._journal_path().exists(), "the journal stays for the human to act on"


def test_a_file_already_put_back_only_clears_the_journal(repo) -> None:
    """Killed after the restore, before the cleanup: nothing to repair."""
    target = _journal(repo, on_disk=PRISTINE)

    assert mc._recover_journal() == 0
    assert target.read_text(encoding="utf-8") == PRISTINE
    assert not mc._journal_path().exists()


def test_a_missing_pristine_copy_refuses_rather_than_guessing(repo) -> None:
    target = _journal(repo, on_disk=MUTANT, copy=False)

    assert mc._recover_journal() == 1
    assert target.read_text(encoding="utf-8") == MUTANT


def test_a_corrupt_journal_refuses_rather_than_acting(repo) -> None:
    """A journal is a file read back from disk: unreadable means refuse, not
    'carry on as if there were none'."""
    path = mc._journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    assert mc._recover_journal() == 1


def test_no_journal_is_the_normal_case(repo) -> None:
    assert mc._recover_journal() == 0


def test_a_journal_naming_a_path_outside_the_repo_refuses(repo) -> None:
    """The journal is this tool's own file, but it is read as data: a path that
    escapes the repository is never written to.

    The file outside the repo must EXIST and hold the mutant text, or the
    refusal happens for the wrong reason — "that path is not there now" — and a
    mutant deleting the escape check survives, which is how this test first
    passed.
    """
    outsider = repo.parent / "outside-the-repo.py"
    outsider.write_text(MUTANT, encoding="utf-8")
    copy = repo / ".git" / "copy.txt"
    copy.write_text(PRISTINE, encoding="utf-8")
    path = mc._journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "path": f"../{outsider.name}", "pristine_sha256": _sha(PRISTINE),
        "mutant_sha256": _sha(MUTANT), "pristine_copy": str(copy),
        "label": "x", "pid": 1, "started_at": "2026-10-16T12:00:00Z",
    }), encoding="utf-8")

    assert mc._recover_journal() == 1
    assert outsider.read_text(encoding="utf-8") == MUTANT, "nothing outside the repo is written"


def test_the_record_exists_while_the_mutant_is_on_disk(repo, monkeypatch) -> None:
    """The record has to be written BEFORE the mutant, or it does not cover the
    run that dies between the two writes — the only run it exists for.

    Asserted from inside the suite run, at the one moment it matters: while the
    mutated file is on disk and the tests are about to run. Without this, a
    mutant deleting the whole `_write_journal` call survives every other test
    here, because they all check the journal is ABSENT afterwards.
    """
    target = repo / TARGET
    target.write_text(PRISTINE, encoding="utf-8")
    seen: dict[str, object] = {}

    def _spy(*_a, **_k):
        # `run_suite` runs a BASELINE first and abandons the suite if it fails,
        # so the baseline must pass or nothing is ever mutated — which is why
        # the first version of this test saw no journal at all.
        seen["calls"] = seen.get("calls", 0) + 1
        if seen["calls"] == 1:
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        journal = mc._journal_path()
        seen["journal_existed"] = journal.exists()
        if journal.exists():
            entry = json.loads(journal.read_text(encoding="utf-8"))
            seen["path"] = entry["path"]
            seen["mutant_sha_matches"] = entry["mutant_sha256"] == _sha(
                target.read_text(encoding="utf-8"))
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(mc, "_pytest", _spy)
    mc.run_suite(mc.Suite(
        name="rules_port_probe",
        tests=("scripts/test/test_nothing.py",),
        mutations=(mc.Mutation("placement ignores _ours", TARGET,
                               "if _ours(existing) else 'block'", ""),),
    ))

    assert seen.get("journal_existed") is True, "no record while the mutant was on disk"
    assert seen.get("path") == TARGET
    assert seen.get("mutant_sha_matches") is True, "the record must name what was actually written"


def test_main_stops_when_recovery_refuses(repo, monkeypatch) -> None:
    """Wiring again: `main` must RETURN the refusal, not merely call recovery.
    A mutant that dropped the return value survived until this existed."""
    edited = MUTANT + "\n# a human kept working here\n"
    target = _journal(repo, on_disk=edited)
    monkeypatch.setattr(sys, "argv", ["mutation_check.py", "--list"])

    assert mc.main() == 1
    assert target.read_text(encoding="utf-8") == edited


def test_allow_dirty_does_not_skip_the_residue_check(repo, capsys) -> None:
    """The hole that let today's mutation through: --allow-dirty exists for the
    author's uncommitted work, and it waved a previous run's residue through
    with it. Recovery is about this tool's own writes, so the flag must not
    reach it."""
    target = _journal(repo, on_disk=MUTANT)

    assert mc._recover_journal(allow_dirty=True) == 0
    assert target.read_text(encoding="utf-8") == PRISTINE
    assert "rules_port" in capsys.readouterr().err


def test_even_listing_the_suites_repairs_residue(repo, monkeypatch) -> None:
    """Wiring, not logic — and the unit tests above could not see it.

    `_recover_journal` was called just before the dirty-file check, which sits
    AFTER `--list` returns, so `mutation_check.py --list` walked straight past a
    mutation it had left in the tree. Found by killing a real run with -9 and
    listing afterwards, not by any test of the function itself. Repairing its own
    residue is the inverse of the damage, so every invocation does it.
    """
    target = _journal(repo, on_disk=MUTANT)
    monkeypatch.setattr(sys, "argv", ["mutation_check.py", "--list"])

    assert mc.main() == 0
    assert target.read_text(encoding="utf-8") == PRISTINE
    assert not mc._journal_path().exists()


def test_a_completed_run_leaves_no_journal(repo, monkeypatch) -> None:
    """The record exists only while a mutant is on disk."""
    target = repo / TARGET
    target.write_text(PRISTINE, encoding="utf-8")
    suite = mc.Suite(
        name="rules_port_probe",
        tests=("scripts/test/test_nothing.py",),
        mutations=(mc.Mutation("placement ignores _ours", TARGET,
                               "if _ours(existing) else 'block'", ""),),
    )
    calls = {"n": 0}

    def _fake_pytest(*_a, **_k):
        calls["n"] += 1
        code = 0 if calls["n"] == 1 else 1      # baseline passes, then the mutant dies
        return type("R", (), {"returncode": code, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(mc, "_pytest", _fake_pytest)

    mc.run_suite(suite)
    assert calls["n"] >= 2, "the mutation must actually have been run"

    assert not mc._journal_path().exists()
    assert target.read_text(encoding="utf-8") == PRISTINE
