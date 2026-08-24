"""
scripts/test/test_delivery_model.py — Delivery Model soft gate + evidence pack
(no network; FIXES Enterprise Delivery Model).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


from _shared import load_script  # noqa: E402


def _load(name: str, filename: str):
    """Thin shim over _shared.load_script — kept so the call sites below
    read unchanged; the loader itself is no longer duplicated here."""
    return load_script(filename[:-3])


def test_org_policy_example_has_delivery_model_catalog() -> None:
    path = ROOT / "templates" / "delivery-model" / "org-policy.example.yaml"
    assert path.exists()
    data = yaml.safe_load(path.read_text())
    dm = data["delivery_model"]
    assert "approved_platforms" in dm
    assert "uae-sovereign" in dm["approved_platforms"]
    assert "required_promote_evidence" in dm
    assert "eval_scorecard" in dm["required_promote_evidence"]


def test_soft_gate_warns_when_platform_not_approved(tmp_path: Path) -> None:
    dm = _load("delivery_model", "delivery_model.py")
    policy = {
        "delivery_model": {
            "approved_platforms": ["on-prem", "uae-sovereign"],
            "data_access_patterns": ["postgres-tenant-partition"],
        }
    }
    tenant = {"delivery": {"platform": "random-saas", "data_access_pattern": "postgres-tenant-partition"}}
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "org-policy.yaml").write_text(yaml.dump(policy))
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(yaml.dump(tenant))

    result = dm.check_tenant_against_policy(tmp_path)
    assert result["status"] == "warn"
    assert any("random-saas" in w for w in result["warnings"])
    assert result["ok_for_ci"] is True  # soft gate never hard-fails


def test_soft_gate_ok_when_platform_approved(tmp_path: Path) -> None:
    dm = _load("delivery_model", "delivery_model.py")
    policy = {
        "delivery_model": {
            "approved_platforms": ["on-prem"],
            "data_access_patterns": ["postgres-tenant-partition"],
        }
    }
    tenant = {"delivery": {"platform": "on-prem", "data_access_pattern": "postgres-tenant-partition"}}
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "org-policy.yaml").write_text(yaml.dump(policy))
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(yaml.dump(tenant))

    result = dm.check_tenant_against_policy(tmp_path)
    assert result["status"] == "ok"
    assert result["warnings"] == []
    assert result["ok_for_ci"] is True


def test_soft_gate_skips_without_org_policy(tmp_path: Path) -> None:
    dm = _load("delivery_model", "delivery_model.py")
    result = dm.check_tenant_against_policy(tmp_path)
    assert result["status"] == "skip"
    assert result["ok_for_ci"] is True


def _fixtures(tmp_path: Path) -> Path:
    fixtures = tmp_path / ".agent-rfc" / "fixtures"
    fixtures.mkdir(parents=True)
    return fixtures


def _item(manifest: dict, item_id: str) -> dict:
    return next(i for i in manifest["items"] if i["id"] == item_id)


def test_delivery_evidence_writes_json_and_markdown(tmp_path: Path) -> None:
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = _fixtures(tmp_path)
    (fixtures / "eval_results.json").write_text(
        json.dumps({"passed": True, "avg_score": 0.9, "suite": "golden"})
    )

    manifest = de.collect_evidence(tmp_path)
    assert manifest["items"]
    # No `verdict` key and a real bool `passed` — an artifact from before the
    # field existed, which is still readable evidence.
    assert _item(manifest, "eval_scorecard")["status"] == "present"

    paths = de.write_evidence_pack(tmp_path, manifest)
    assert paths["json"].exists()
    assert paths["md"].exists()
    assert "eval_scorecard" in paths["md"].read_text()


def test_no_verdict_scorecard_is_inconclusive_not_present(tmp_path: Path) -> None:
    """The whole reason `inconclusive` exists.

    A run that graded nothing writes this file — it used to be counted as
    `present` beside an avg_score computed over no cases, so an auditor read a
    starved run as delivered evidence.
    """
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = _fixtures(tmp_path)
    (fixtures / "eval_results.json").write_text(
        json.dumps(
            {
                "suite": "golden",
                "verdict": "no_verdict",
                "passed": None,
                "avg_score": 0.0,
                "cases_graded": 0,
                "cases_total": 12,
            }
        )
    )

    manifest = de.collect_evidence(tmp_path)
    item = _item(manifest, "eval_scorecard")
    assert item["status"] == "inconclusive"
    assert "no_verdict" in item["detail"]
    assert "graded=0/12" in item["detail"]
    assert manifest["summary"]["present"] == 0
    assert manifest["summary"]["inconclusive"] == 1
    assert "inconclusive` is not a pass" in de.render_markdown(manifest)


def test_failing_scorecard_is_still_present_evidence(tmp_path: Path) -> None:
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = _fixtures(tmp_path)
    (fixtures / "eval_results.json").write_text(
        json.dumps({"suite": "golden", "verdict": "fail", "passed": False, "avg_score": 0.4})
    )
    item = _item(de.collect_evidence(tmp_path), "eval_scorecard")
    assert item["status"] == "present"
    assert "verdict=fail" in item["detail"]


def test_hallucination_detection_states_are_distinguishable(tmp_path: Path) -> None:
    """Graded-and-clean, declared-but-ungraded, and none-declared are three
    different facts. All three used to be absent from the pack entirely."""
    de = _load("delivery_evidence", "delivery_evidence.py")

    graded = de._hallucination_detail(
        {"hallucination_flag_rate": 0.0, "hallucination_miss_rate": 0.0,
         "hallucination_controls_declared": 1}
    )
    assert "detection_miss=0.000" in graded

    missed = de._hallucination_detail(
        {"hallucination_flag_rate": 0.0, "hallucination_miss_rate": 1.0,
         "hallucination_controls_declared": 1}
    )
    assert "went undetected" in missed

    ungraded = de._hallucination_detail(
        {"hallucination_flag_rate": None, "hallucination_miss_rate": None,
         "hallucination_controls_declared": 1}
    )
    assert "NOT GRADED" in ungraded
    assert "NOT MEASURED" in ungraded  # the flag rate, which also had no data

    none_declared = de._hallucination_detail(
        {"hallucination_flag_rate": 0.0, "hallucination_miss_rate": None,
         "hallucination_controls_declared": 0}
    )
    assert "NO POSITIVE CONTROL" in none_declared

    # Distinct strings, not three renderings of the same reassuring 0.000.
    assert len({graded, missed, ungraded, none_declared}) == 4


def test_hallucination_scorecard_has_a_row_when_absent(tmp_path: Path) -> None:
    """Silence reads as 'did not apply'. The grounding suite gets a row saying
    it was never run, rather than no row at all."""
    de = _load("delivery_evidence", "delivery_evidence.py")
    _fixtures(tmp_path)
    item = _item(de.collect_evidence(tmp_path), "hallucination_scorecard")
    assert item["status"] == "missing"
    assert "--suite hallucination" in item["detail"]


def test_fairness_reports_worst_pair_not_only_the_mean(tmp_path: Path) -> None:
    """The gate compares the worst pair; reporting only the mean let a large
    suite outvote a diverging pair."""
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = _fixtures(tmp_path)
    (fixtures / "fairness_eval_results.json").write_text(
        json.dumps(
            {
                "suite": "fairness",
                "verdict": "pass",
                "passed": True,
                "avg_fairness": 1.0,
                "pair_parity": {"p1": 1.0, "p2": 1.0, "p3": 0.5},
                "avg_pair_parity": 0.833,
            }
        )
    )
    detail = _item(de.collect_evidence(tmp_path), "fairness_scorecard")["detail"]
    assert "worst_pair_parity=0.500" in detail
    assert "mean 0.833" in detail


def test_scorecard_detail_carries_run_age_and_judge(tmp_path: Path) -> None:
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = _fixtures(tmp_path)
    (fixtures / "eval_results.json").write_text(
        json.dumps(
            {
                "suite": "golden",
                "verdict": "pass",
                "passed": True,
                "avg_score": 1.0,
                "timestamp": "2020-01-01T00:00:00Z",
                "judge_models_used": ["gemini-3-flash-preview"],
            }
        )
    )
    detail = _item(de.collect_evidence(tmp_path), "eval_scorecard")["detail"]
    assert "ran=2020-01-01T00:00:00Z" in detail
    assert "d ago)" in detail  # a stale fixture must not read as a fresh one
    assert "judge=gemini-3-flash-preview" in detail


def test_unreadable_scorecard_is_missing_not_present(tmp_path: Path) -> None:
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = _fixtures(tmp_path)
    (fixtures / "eval_results.json").write_text("{not json")
    item = _item(de.collect_evidence(tmp_path), "eval_scorecard")
    assert item["status"] == "missing"
    assert "unreadable" in item["detail"]


def test_scorecard_graded_by_the_wrong_judge_is_inconclusive(tmp_path: Path) -> None:
    """A simulator's verdict is not evidence about a calibrated gate.

    eval_judge.py stamps `judged_by` with the id it was handed, so in a real
    run these always agree — a mismatch means the artifact did not come off the
    standard path. KYC Sentinel's fixtures carried exactly this on 2026-08-23
    (`judge_models_used=['sim']`) and the pack called them present.
    """
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = _fixtures(tmp_path)
    (fixtures / "eval_results.json").write_text(
        json.dumps(
            {
                "suite": "golden",
                "verdict": "fail",
                "passed": False,
                "avg_score": 0.1,
                "judge_model": "gemini-3-flash-preview",
                "judge_models_used": ["sim"],
            }
        )
    )
    item = _item(de.collect_evidence(tmp_path), "eval_scorecard")
    assert item["status"] == "inconclusive"
    assert "not the requested gemini-3-flash-preview" in item["detail"]


def test_matching_judge_is_not_flagged(tmp_path: Path) -> None:
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = _fixtures(tmp_path)
    (fixtures / "eval_results.json").write_text(
        json.dumps(
            {
                "suite": "golden",
                "verdict": "pass",
                "passed": True,
                "avg_score": 1.0,
                "judge_model": "gemini-3-flash-preview",
                "judge_models_used": ["gemini-3-flash-preview"],
            }
        )
    )
    item = _item(de.collect_evidence(tmp_path), "eval_scorecard")
    assert item["status"] == "present"
    assert "⚠️" not in item["detail"]


def test_tenant_yaml_without_delivery_keys_is_inconclusive(tmp_path: Path) -> None:
    """The file existing is not the evidence — the two delivery.* keys are."""
    de = _load("delivery_evidence", "delivery_evidence.py")
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(yaml.dump({"id": "acme"}))
    item = _item(de.collect_evidence(tmp_path), "tenant_yaml")
    assert item["status"] == "inconclusive"
    assert "delivery.platform and delivery.data_access_pattern not set" in item["detail"]


def test_tenant_yaml_with_delivery_keys_is_present(tmp_path: Path) -> None:
    de = _load("delivery_evidence", "delivery_evidence.py")
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(
        yaml.dump({"delivery": {"platform": "on-prem", "data_access_pattern": "postgres-tenant-partition"}})
    )
    item = _item(de.collect_evidence(tmp_path), "tenant_yaml")
    assert item["status"] == "present"
    assert "delivery.platform=on-prem" in item["detail"]


def test_scorecard_filenames_come_from_the_shared_catalog() -> None:
    """The pack must not keep its own copy of suite → results filename.

    A rename in `_shared.RESULTS_FILE` with a stale copy here fails quietly:
    the pack reads a path that no longer exists and reports `missing`, so a
    suite that runs on every push reads as never run.
    """
    from _shared import RESULTS_FILE

    de = _load("delivery_evidence", "delivery_evidence.py")
    for card in de.SCORECARDS:
        assert card.suite in RESULTS_FILE, card.suite
    assert {c.suite for c in de.SCORECARDS} == {"golden", "fairness", "hallucination"}


def test_refresh_block_and_missing_rows_name_the_same_commands(tmp_path: Path) -> None:
    """Two hand-kept lists of the same commands drift; the one an auditor
    follows is whichever they read first."""
    de = _load("delivery_evidence", "delivery_evidence.py")
    _fixtures(tmp_path)
    manifest = de.collect_evidence(tmp_path)
    md = de.render_markdown(manifest)
    for card in de.SCORECARDS:
        assert card.refresh_cmd in md
        row = _item(manifest, card.item_id)
        assert card.refresh_cmd in row["detail"]
