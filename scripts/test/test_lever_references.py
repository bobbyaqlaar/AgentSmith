"""
scripts/test/test_lever_references.py — a `review-levers N.M` citation must
still point at the lever it meant.

THE DRIFT THIS CATCHES, which happened here. `scripts/notifier.py` cited
`review-levers 2.7` for "validation belongs on the receiving side of a trust
boundary". A later pass inserted a new lever at 2.7 and pushed validation to
2.8, so the comment went on naming a number that had come to mean something
else. Nothing failed; the citation just quietly started lying — which is the
same shape as the stale-doc defects the levers themselves are about.

An existence check would not have caught it: 2.7 existed the whole time. So a
citation carries a short NAME as well as a number, and this reads both sides
and compares them. Neither the name nor the number is restated here — a test
that hardcodes the mapping is just a third copy of it (lever 1.7).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEVERS = ROOT / "docs" / "review-levers.md"

# `review-levers 2.8: some name` or `(review-levers 1.7: some name)` or
# `... 3.4 (declared vs enforced)`. The name may wrap onto the next line.
_CITATION = re.compile(
    r"review-levers?\s+(\d+)\.(\d+)\s*[:(]\s*([^)\n]*(?:\n[^)\n]*)?)", re.I
)
_STOP = {"a", "an", "the", "is", "of", "on", "to", "not", "must", "that", "and", "as", "for"}


def _lever_titles() -> dict[tuple[int, int], str]:
    """{(group, item): title} parsed from the document."""
    titles: dict[tuple[int, int], str] = {}
    group = 0
    for line in LEVERS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (\d+) · ", line)
        if m:
            group = int(m.group(1))
            continue
        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m and group:
            titles[(group, int(m.group(1)))] = m.group(2)
    return titles


def _cited() -> list[tuple[Path, int, int, str]]:
    files = subprocess.run(
        ["git", "ls-files", "*.py", "*.ts", "*.tsx"], cwd=ROOT,
        capture_output=True, text=True, check=False,
    ).stdout.split()
    out = []
    for rel in files:
        path = ROOT / rel
        if path == Path(__file__):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _CITATION.finditer(text):
            out.append((path, int(m.group(1)), int(m.group(2)), m.group(3)))
    return out


def test_the_sweep_reads_the_document_and_the_citations() -> None:
    """Either side coming back empty would make every assertion below vacuous."""
    titles = _lever_titles()
    assert len(titles) > 30, f"parsed only {len(titles)} levers from the document"
    assert len(_cited()) >= 5, "found almost no lever citations to check"


def test_every_cited_lever_number_exists() -> None:
    titles = _lever_titles()
    missing = [
        f"{p.relative_to(ROOT)} cites {g}.{i}, which does not exist"
        for p, g, i, _ in _cited() if (g, i) not in titles
    ]
    assert not missing, "\n  " + "\n  ".join(missing)


def test_every_citation_names_the_lever_it_points_at() -> None:
    """The half an existence check cannot do. A number that still resolves but
    now means something else is the failure that actually happened."""
    titles = _lever_titles()
    wrong = []
    for path, group, item, name in _cited():
        title = titles.get((group, item), "")
        cited_words = {w for w in re.findall(r"[a-z]+", name.lower()) if w not in _STOP}
        title_words = {w for w in re.findall(r"[a-z]+", title.lower()) if w not in _STOP}
        if not cited_words:
            continue  # a bare number, covered by the test above
        overlap = cited_words & title_words
        if len(overlap) < max(2, len(cited_words) // 3):
            wrong.append(
                f"{path.relative_to(ROOT)} cites {group}.{item} as "
                f"{name.strip()!r}, but {group}.{item} is {title[:70]!r}"
            )
    assert not wrong, (
        "these citations name a lever other than the one at that number — a "
        "lever was probably inserted above it:\n  " + "\n  ".join(wrong)
    )
