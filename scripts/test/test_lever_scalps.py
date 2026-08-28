"""
scripts/test/test_lever_scalps.py — the checklist and its evidence must agree.

`docs/review-levers.md` holds the rules and `docs/review-lever-scalps.md` holds
the defect each one earned its place with. Splitting them keeps the checklist
short enough to use, and creates exactly the problem lever 1.7 is about: two
files sharing one numbering scheme, with nothing to stop them drifting.

So this parses both and compares. Neither side is restated here — a test that
hardcodes the mapping is a third copy of it.

WHAT COUNTS AS DRIFT:
  * a scalp for a lever number that does not exist (an item was renumbered or
    deleted and its evidence was orphaned);
  * a dated or `(+)`-marked lever with no scalp — the document's own standard is
    that such an item is decoration;
  * a title in the scalps file that no longer matches the lever's, which is the
    renumbering failure that already happened once to a code citation.

`(legacy)` items are exempt by design: the original standing list, kept as a
hygiene checklist rather than as evidence-backed findings.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEVERS = ROOT / "docs" / "review-levers.md"
SCALPS = ROOT / "docs" / "review-lever-scalps.md"


def _levers() -> dict[str, tuple[str, bool]]:
    """{"6.7": (title, is_legacy)} from the checklist."""
    out: dict[str, tuple[str, bool]] = {}
    group = 0
    for line in LEVERS.read_text(encoding="utf-8").splitlines():
        g = re.match(r"^## (\d+) · ", line)
        if g:
            group = int(g.group(1))
            continue
        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if not (m and group):
            continue
        rest = m.group(2)
        legacy = "(legacy)" in rest
        t = re.match(r"\*\*(?:\([^)]*\)\s*)?(.+?)\*\*", rest)
        title = (t.group(1) if t else rest[:70]).rstrip(".")
        out[f"{group}.{m.group(1)}"] = (title, legacy)
    return out


def _scalps() -> dict[str, str]:
    """{"6.7": title} from the evidence file's headings."""
    return {
        m.group(1): m.group(2).strip()
        for m in re.finditer(
            r"^### (\d+\.\d+) — (.+)$", SCALPS.read_text(encoding="utf-8"), re.M
        )
    }


def test_both_files_parse_to_something() -> None:
    """Either side coming back empty makes every assertion below vacuous."""
    levers, scalps = _levers(), _scalps()
    assert len(levers) > 30, f"parsed only {len(levers)} levers"
    assert len(scalps) > 20, f"parsed only {len(scalps)} scalps"


def test_no_scalp_is_orphaned() -> None:
    levers = _levers()
    orphans = [k for k in _scalps() if k not in levers]
    assert not orphans, (
        "these scalps cite a lever number that no longer exists — an item was "
        f"renumbered or removed and its evidence was left behind: {orphans}"
    )


def test_every_non_legacy_lever_has_a_scalp() -> None:
    scalps = _scalps()
    missing = [
        f"{k} ({title})"
        for k, (title, legacy) in _levers().items()
        if not legacy and k not in scalps
    ]
    assert not missing, (
        "these levers have no recorded evidence, and the document's own standard "
        "is that a lever with no scalp is decoration. Add the defect it caught, "
        f"or mark it (legacy): {missing}"
    )


def test_the_two_files_agree_on_every_title() -> None:
    """The renumbering failure, caught before it reaches a reader. A scalp filed
    under a number that has come to mean something else is worse than no scalp:
    it lends evidence to the wrong rule."""
    levers = _levers()
    wrong = [
        f"{k}: scalps say {st!r}, levers say {levers[k][0]!r}"
        for k, st in _scalps().items()
        if k in levers and st.lower() != levers[k][0].lower()
    ]
    assert not wrong, "\n  " + "\n  ".join(wrong)
