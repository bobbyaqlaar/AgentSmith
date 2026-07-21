"""
scripts/test/test_promotion_loop.py — the HITL self-improvement write path
(TestCoverageReview-2026-07-21 gap 4): promote-learning.py's golden-dataset
append / judge-learning versioning / log resolution, and sync-ui-feedback.py's
annotation → promotion flow with dedupe and the C4 bound.

Writing these tests exposed a real bug, now fixed: both dashed-filename
imports (`from promote_learning import ...`, `from run_evals import ...`)
could never resolve, so Phoenix-annotation promotion failed on every entry
and scorecard re-runs silently warned. The end-to-end sync test below is
the regression net for that class of bug.

No network: Phoenix accessors are stubbed on the loaded module.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))


def _load_dashed(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    sys.modules[module_name] = mod
    return mod


promote_learning = _load_dashed("promote_learning", "promote-learning.py")
sync_ui_feedback = _load_dashed("sync_ui_feedback", "sync-ui-feedback.py")


@pytest.fixture()
def repo(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _golden(repo: Path) -> list:
    p = repo / ".agent-rfc" / "fixtures" / "golden_evals.json"
    return json.loads(p.read_text()) if p.exists() else []


# ── promote() ────────────────────────────────────────────────────────────────


def test_promote_appends_golden_case_and_learning(repo):
    result = promote_learning.promote(
        "case:1",
        "book a flight for next tuesday",
        "call search_flights with parsed ISO date",
        expected_tool="search_flights",
        resolution_note="date phrases must be parsed before tool choice",
        resolved_by="bobby@example.com",
        rerun_evals=False,
    )
    assert result["golden_count"] == 1
    case = _golden(repo)[0]
    assert case["id"] == "case:1" and case["expected_tool"] == "search_flights"
    criteria = json.loads(
        (repo / ".agent-rfc" / "fixtures" / "custom_judge_criteria.json").read_text()
    )
    assert any("date phrases" in x for x in criteria["historical_learnings"])


def test_promote_same_case_updates_not_duplicates(repo):
    for output in ("first answer", "revised answer"):
        promote_learning.promote(
            "case:dup", "input", output, resolution_note="same note", rerun_evals=False
        )
    golden = _golden(repo)
    assert len(golden) == 1 and golden[0]["reference_output"] == "revised answer"
    criteria = json.loads(
        (repo / ".agent-rfc" / "fixtures" / "custom_judge_criteria.json").read_text()
    )
    # learning entries carry a timestamp prefix; both promotions may add one
    # each, but identical (ts, case, note) strings are never duplicated
    assert len(criteria["historical_learnings"]) == len(
        set(criteria["historical_learnings"])
    )


def test_promote_marks_matching_log_entry_resolved(repo):
    log = repo / ".agent-history.log"
    entries = [
        {"event": "case:log", "level": "MAJOR", "hitl_resolved": False},
        {"event": "case:log", "level": "INFO", "hitl_resolved": False},  # wrong level
        {"event": "other", "level": "CRITICAL", "hitl_resolved": False},  # wrong event
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    result = promote_learning.promote(
        "case:log", "in", "out", rerun_evals=False
    )
    assert result["hitl_entries_resolved"] == 1
    updated = [json.loads(l) for l in log.read_text().splitlines() if l]
    assert updated[0]["hitl_resolved"] is True and "hitl_resolved_by" in updated[0]
    assert updated[1]["hitl_resolved"] is False
    assert updated[2]["hitl_resolved"] is False


# ── sync() end-to-end (stubbed Phoenix) ──────────────────────────────────────


def _stub_phoenix(monkeypatch, annotations, spans):
    monkeypatch.setattr(sync_ui_feedback, "_phoenix_get", lambda path, params=None: {})
    monkeypatch.setattr(sync_ui_feedback, "_fetch_annotations", lambda: annotations)
    monkeypatch.setattr(sync_ui_feedback, "_fetch_span", lambda sid: spans.get(sid))


def test_sync_promotes_negative_feedback_end_to_end(repo, monkeypatch):
    """Regression net for the dashed-import bug: a negative annotation must
    land in the golden dataset, not the error counter."""
    _stub_phoenix(
        monkeypatch,
        annotations=[
            {"span_id": "span-neg-000001", "label": "thumbs_down", "explanation": "wrong tool"},
            {"span_id": "span-pos-000001", "label": "thumbs_up", "score": 1.0},
        ],
        spans={"span-neg-000001": {"attributes": {"input.value": "user asked X"}}},
    )
    stats = sync_ui_feedback.sync()
    assert stats == {"synced": 1, "skipped": 1, "errors": 0}
    golden = _golden(repo)
    assert len(golden) == 1 and golden[0]["id"].startswith("phoenix:")


def test_sync_dedupes_already_synced_spans(repo, monkeypatch):
    _stub_phoenix(
        monkeypatch,
        annotations=[{"span_id": "span-neg-000001", "label": "incorrect"}],
        spans={"span-neg-000001": {"attributes": {"input.value": "q"}}},
    )
    assert sync_ui_feedback.sync()["synced"] == 1
    stats2 = sync_ui_feedback.sync()  # same annotation again
    assert stats2 == {"synced": 0, "skipped": 1, "errors": 0}
    assert len(_golden(repo)) == 1


def test_sync_state_bounded(repo, monkeypatch):
    """C4: synced_span_ids keeps only the newest MAX_SYNCED_IDS."""
    monkeypatch.setattr(sync_ui_feedback, "MAX_SYNCED_IDS", 3)
    annotations = [
        {"span_id": f"span-{i:04d}", "label": "fail"} for i in range(5)
    ]
    spans = {f"span-{i:04d}": {"attributes": {"input.value": "q"}} for i in range(5)}
    _stub_phoenix(monkeypatch, annotations, spans)
    sync_ui_feedback.sync()
    state = json.loads(
        (repo / ".agent-rfc" / "fixtures" / "sync_state.json").read_text()
    )
    assert state["synced_span_ids"] == ["span-0002", "span-0003", "span-0004"]


def test_sync_offline_phoenix_degrades_gracefully(repo, monkeypatch):
    def down(path, params=None):
        raise RuntimeError("Phoenix API error")

    monkeypatch.setattr(sync_ui_feedback, "_phoenix_get", down)
    stats = sync_ui_feedback.sync()
    assert stats == {"synced": 0, "skipped": 0, "errors": 0}
