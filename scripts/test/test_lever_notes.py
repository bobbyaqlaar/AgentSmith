"""
scripts/test/test_lever_notes.py — the checklist and its notes must stay in step.

`docs/review-levers.md` holds the rules, one line each so the list can actually
be worked down. `docs/review-lever-notes.md` holds why each exists and the defect
it earned its place with. The split is what lets the checklist be short without
anything in it having to be taken on trust.

Two files sharing one set of identifiers is `pin-unremovable-duplicates`, so this
parses both and compares. Slugs removed the renumbering hazard; they do not
remove this one — a lever can still be renamed, or added with no notes.

There is deliberately no title comparison. The checklist carries a RULE and the
notes carry a title; they are different sentences by design, and an earlier
version of this test compared them and started failing the moment the checklist
was compressed. The slug is the link, and it is checked in both directions.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEVERS = ROOT / "docs" / "review-levers.md"
NOTES = ROOT / "docs" / "review-lever-notes.md"


def _levers() -> dict[str, bool]:
    """{slug: is_legacy} from the checklist."""
    return {
        m.group(1): "(legacy)" in m.group(2)
        for m in re.finditer(
            r"^- `([a-z][a-z0-9-]*)` — (.*)$", LEVERS.read_text(encoding="utf-8"), re.M
        )
    }


def _noted() -> set[str]:
    return set(
        re.findall(
            r"^### `([a-z][a-z0-9-]*)` — ", NOTES.read_text(encoding="utf-8"), re.M
        )
    )


def test_both_files_parse_to_something() -> None:
    """Either side coming back empty makes every assertion below vacuous."""
    assert len(_levers()) > 30, f"parsed only {len(_levers())} levers"
    assert len(_noted()) > 20, f"parsed only {len(_noted())} notes"


def test_no_note_is_orphaned() -> None:
    levers = _levers()
    orphans = sorted(_noted() - set(levers))
    assert not orphans, (
        "these notes cite a slug that is not a lever — it was renamed or removed "
        f"and its reasoning was left behind: {orphans}"
    )


def test_every_non_legacy_lever_has_notes() -> None:
    """The document's own standard: a lever nobody can trace to a real failure
    gets followed with the same conviction as one that has caught things."""
    noted = _noted()
    missing = sorted(s for s, legacy in _levers().items() if not legacy and s not in noted)
    assert not missing, (
        "these levers have no entry in the notes. Add why it exists and what it "
        f"caught, or mark it (legacy): {missing}"
    )


def test_legacy_levers_stay_out_of_the_notes() -> None:
    """The exemption is deliberate and should stay visible. A legacy item that
    acquires notes has become an evidence-backed lever and should lose the mark
    rather than hold both."""
    both = sorted(s for s, legacy in _levers().items() if legacy and s in _noted())
    assert not both, f"these are marked (legacy) but carry notes: {both}"
