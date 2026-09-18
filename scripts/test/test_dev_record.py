"""
scripts/test/test_dev_record.py — `process_gate.py ci --json FILE` (portal phase 1, S1).

The portal's Dev workspace shows what the gate decided about each commit. It is
sent that decision by the run that made it, so it never re-derives a verdict
and cannot disagree with the gate (.agent-rfc/designs/portal-phase1.md).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from test_process_gate import (
    DESIGN,
    MESSAGE,
    REPO,
    REVIEW_CLEAN,
    _commit,
    _git,
    _write,
    needs_git,
    pg,
)

import gate_models as gm

pytestmark = needs_git


def _ci_json(repo: Path, base: str, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "scripts/process_gate.py"), "ci", "--base", base, "--head", "HEAD",
         "--json", str(out)],
        cwd=repo, capture_output=True, text=True, check=False,
    )


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _compliant_commit(repo: Path) -> None:
    _write(repo, "scripts/tool.py", "print(1)\n")
    _write(repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(repo, "CHANGELOG.md", "# Changelog\n\n- tool\n")
    assert _commit(repo, MESSAGE).returncode == 0


def test_a_compliant_commit_is_recorded_as_passed_with_its_design_and_review(gated_repo, tmp_path):
    base = _head(gated_repo)
    _compliant_commit(gated_repo)
    out = tmp_path / "record.json"

    result = _ci_json(gated_repo, base, out)

    assert result.returncode == 0, result.stdout
    document = json.loads(out.read_text())
    assert document["schema"] == 1 and document["head"] == _head(gated_repo)
    [record] = document["commits"]
    assert record["commit"] == _head(gated_repo) and record["verdict"] == "passed"
    assert record["gated"] is True and record["adopted"] is True and record["errors"] == []
    assert record["subject"] == "feat: x" and record["author_email"]
    design = record["design"]
    assert design["resolved"] is True and design["path"] == ".agent-rfc/designs/change.md"
    assert design["title"] == "A change" and design["status"] == "active"
    assert design["scope"] == ["scripts/lib/**", "scripts/tool.py"]
    assert design["pillars"] and set(design["pillars"].values()) == {"applies"}
    assert design["deviations"] == []
    review = record["review"]
    assert review["resolved"] is True
    assert review["passes"] == [{"n": 1, "findings": 2}, {"n": 2, "findings": 0}]
    assert review["signed_off"] is True


def test_a_commit_that_skipped_the_gate_is_recorded_as_failed_and_the_file_still_written(gated_repo, tmp_path):
    base = _head(gated_repo)
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "feat: sneak", "--no-verify")
    out = tmp_path / "record.json"

    result = _ci_json(gated_repo, base, out)

    assert result.returncode == 1
    [record] = json.loads(out.read_text())["commits"]
    assert record["verdict"] == "failed" and record["errors"]
    assert record["design"] is None and record["review"] is None


def test_a_design_that_does_not_resolve_says_why_rather_than_vanishing(gated_repo, tmp_path):
    base = _head(gated_repo)
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", MESSAGE, "--no-verify")
    out = tmp_path / "record.json"

    _ci_json(gated_repo, base, out)

    [record] = json.loads(out.read_text())["commits"]
    assert record["design"]["resolved"] is False
    assert "does not exist" in record["design"]["reason"]


def test_an_ungated_commit_is_recorded_as_not_gated(gated_repo, tmp_path):
    base = _head(gated_repo)
    _write(gated_repo, "docs/notes.md", "# Notes\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "docs: notes", "--no-verify")
    out = tmp_path / "record.json"

    _ci_json(gated_repo, base, out)

    [record] = json.loads(out.read_text())["commits"]
    assert record["verdict"] == "not_gated" and record["gated"] is False


def test_findings_on_an_ungated_commit_are_not_recorded_as_nothing(gated_repo, tmp_path):
    """The fixture runs `artifacts: report`, so a dead pointer in a document is
    a note, not an error — and the only fact worth showing about that commit."""
    base = _head(gated_repo)
    _write(gated_repo, "docs/notes.md", "# Notes\n\nSee docs/DESIGN.md#L120.\n")  # <!-- xref: example -->
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "docs: notes", "--no-verify")
    out = tmp_path / "record.json"

    _ci_json(gated_repo, base, out)

    [record] = json.loads(out.read_text())["commits"]
    assert record["verdict"] == "passed_with_notes" and record["notes"]


def test_a_commit_without_the_config_is_recorded_as_before_adoption(gated_repo, tmp_path):
    base = _head(gated_repo)
    config = (gated_repo / pg.CONFIG).read_text()
    _git(gated_repo, "rm", "-q", pg.CONFIG)
    _git(gated_repo, "commit", "-qm", "chore: drop", "--no-verify")
    _write(gated_repo, pg.CONFIG, config)
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "chore: restore", "--no-verify")
    out = tmp_path / "record.json"

    _ci_json(gated_repo, base, out)

    dropped = json.loads(out.read_text())["commits"][0]
    assert dropped["verdict"] == "before_adoption" and dropped["adopted"] is False


def test_a_repairs_trailer_is_recorded_as_the_commits_it_names(gated_repo, tmp_path):
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "feat: sneak", "--no-verify")
    sneaked = _head(gated_repo)
    base = _head(gated_repo)
    _write(gated_repo, "docs/notes.md", "# Notes\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", f"docs: notes\n\nRepairs: {sneaked[:12]}\n", "--no-verify")
    out = tmp_path / "record.json"

    _ci_json(gated_repo, base, out)

    [record] = json.loads(out.read_text())["commits"]
    assert record["repairs"] == [sneaked]


def test_without_the_flag_no_file_is_written(gated_repo, tmp_path):
    base = _head(gated_repo)
    _compliant_commit(gated_repo)

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts/process_gate.py"), "ci", "--base", base, "--head", "HEAD"],
        cwd=gated_repo, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0
    assert not list(tmp_path.glob("*.json"))


def test_a_deviation_is_recorded_by_id_text_hash_and_approval():
    """The portal shows whether a deviation is approved and notices when its
    text changed after approval — so the hash is of the text the gate parsed."""
    registry = gm.Registry.model_validate_json(
        (REPO / "templates" / "governance.json").read_text(encoding="utf-8"))
    text = DESIGN.replace(
        "## Deviations\nnone\n",
        "## Deviations\n- D1 — P7 — a dataclass for now — approval: A-1a2b3c4d\n- D2 — P3 — no span yet\n",
    )

    summary = pg.design_summary(text, registry)

    deviations = {d["id"]: d for d in summary["deviations"]}
    assert deviations["D1"]["approval_id"] == "A-1a2b3c4d"
    assert deviations["D2"]["approval_id"] is None
    parsed, _ = gm.parse_deviations(pg._section(pg.front_matter(text)[1], "Deviations") or "")
    assert deviations["D1"]["text_sha256"] == hashlib.sha256(parsed[0].text.encode()).hexdigest()


def test_every_pillar_kind_is_recorded_as_answered():
    section = ("- P1 applies — `x`\n- P2 n/a — nothing\n- P3 gap — PB-12\n"
               "- P4 deviation D1 — see below\n- P5 perhaps — who knows\n")

    assert gm.pillar_kinds(section) == {
        "P1": "applies", "P2": "n/a", "P3": "gap", "P4": "deviation", "P5": "unrecognised"}


def test_an_incomplete_sign_off_is_recorded_as_not_signed_off():
    registry = gm.Registry.model_validate_json(
        (REPO / "templates" / "governance.json").read_text(encoding="utf-8"))

    assert pg.review_summary(REVIEW_CLEAN, registry)["signed_off"] is True
    unsigned = REVIEW_CLEAN.replace("Group 3 · Architecture / hygiene      [x] checked\n", "")
    assert pg.review_summary(unsigned, registry)["signed_off"] is False
    assert pg.review_summary(REVIEW_CLEAN, None)["signed_off"] is None


def test_the_gate_and_the_portal_agree_on_the_record():
    """The gate writes the record and the portal refuses what it does not know,
    so a verdict or schema added on one side alone breaks every ingest."""
    import re

    source = (REPO / "portal" / "lib" / "devIngest.ts").read_text(encoding="utf-8")
    verdicts = re.search(r"DEV_VERDICTS = \[([^\]]*)\]", source)
    schema = re.search(r"DEV_RECORD_SCHEMA = (\d+);", source)
    assert verdicts and schema, "the constants moved — re-point this test"
    assert tuple(re.findall(r'"([^"]+)"', verdicts.group(1))) == pg.DEV_VERDICTS
    assert int(schema.group(1)) == pg.DEV_RECORD_SCHEMA


def test_the_record_carries_every_design_as_it_stands_at_the_head(gated_repo, tmp_path):
    """A design is closed by a records commit that does not cite it, so the last
    commit that DID cite it still says `active`. The portal reads status from
    the head, which this list is."""
    base = _head(gated_repo)
    _compliant_commit(gated_repo)
    closed = (gated_repo / ".agent-rfc/designs/change.md").read_text().replace("status: active", "status: done", 1)
    _write(gated_repo, ".agent-rfc/designs/change.md", closed)
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "docs(design): change — status done", "--no-verify")
    out = tmp_path / "record.json"

    _ci_json(gated_repo, base, out)

    document = json.loads(out.read_text())
    [design] = [d for d in document["designs"] if d["path"] == ".agent-rfc/designs/change.md"]
    assert design["status"] == "done" and design["title"] == "A change"
    cited = next(c for c in document["commits"] if c["design"])
    assert cited["design"]["status"] == "active", "the commit keeps what was true when it was made"
