"""
scripts/test/test_lever_references.py — a lever cited from code must exist.

Citations used to carry a NUMBER, and numbers move. `scripts/notifier.py` cited
`review-levers 2.7` for "validation belongs on the receiving side"; a later pass
inserted a lever at 2.7 and pushed validation to 2.8, so the comment went on
naming a number that had come to mean something else. Nothing failed — the
citation just quietly started lying, which is the stale-doc defect the levers are
about, committed inside the levers.

The first fix required citations to carry a short name as well as the number, and
compared the two by word overlap. That worked and was fiddly. Levers are keyed by
SLUG now, which is a stable identifier rather than a position, so the whole
question disappears: a slug either exists or it does not, and reordering or
regrouping the checklist cannot invalidate a single citation.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEVERS = ROOT / "docs" / "review-levers.md"

_CITATION = re.compile(r"review-levers:\s*([a-z][a-z0-9-]*)")


def _defined_slugs() -> set[str]:
    return set(re.findall(r"^- `([a-z][a-z0-9-]*)` — ", LEVERS.read_text(encoding="utf-8"), re.M))


def _citations() -> list[tuple[Path, str]]:
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
        out += [(path, m.group(1)) for m in _CITATION.finditer(text)]
    return out


def test_the_sweep_reads_both_sides() -> None:
    """Either side empty would make the assertion below vacuous."""
    assert len(_defined_slugs()) > 30, "parsed almost no levers from the checklist"
    assert len(_citations()) >= 5, "found almost no citations to check"


def test_every_cited_slug_exists() -> None:
    defined = _defined_slugs()
    unknown = [
        f"{p.relative_to(ROOT)} cites `{slug}`, which is not a lever"
        for p, slug in _citations() if slug not in defined
    ]
    assert not unknown, (
        "a citation names a lever that does not exist — it was renamed, or the "
        "slug is a typo:\n  " + "\n  ".join(unknown)
    )
