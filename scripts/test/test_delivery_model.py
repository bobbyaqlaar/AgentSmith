"""
scripts/test/test_delivery_model.py — Delivery Model soft gate + evidence pack
(no network; FIXES Enterprise Delivery Model).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def test_delivery_evidence_writes_json_and_markdown(tmp_path: Path) -> None:
    de = _load("delivery_evidence", "delivery_evidence.py")
    fixtures = tmp_path / ".agent-rfc" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "eval_results.json").write_text(
        json.dumps({"passed": True, "avg_score": 0.9, "suite": "golden"})
    )

    manifest = de.collect_evidence(tmp_path)
    assert manifest["items"]
    eval_item = next(i for i in manifest["items"] if i["id"] == "eval_scorecard")
    assert eval_item["status"] == "present"

    paths = de.write_evidence_pack(tmp_path, manifest)
    assert paths["json"].exists()
    assert paths["md"].exists()
    assert "eval_scorecard" in paths["md"].read_text()
