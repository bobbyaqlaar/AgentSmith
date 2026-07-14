from __future__ import annotations

from pathlib import Path

from security.registry import ControlSpec, FrameworkTags
from security.runners.risk_register import run as run_risk_register

REPO = Path(__file__).resolve().parents[2]


def _control() -> ControlSpec:
    return ControlSpec(
        id="SEC-RISK-001",
        title="Risk register artifact",
        status="org-owned",
        owner="tenant",
        frameworks=FrameworkTags(owasp=[], nist=["MAP 1.5"], atlas=["AML.T0000"], iso42001=[2]),
        runner="risk_register",
        check_type="artifact",
        mechanism="risk register template",
    )


def test_missing_risk_register_warns_non_strict(tmp_path: Path) -> None:
    ctx = {
        "root": REPO,
        "tenant_security": tmp_path / "security",
        "mode": "ci",
        "strict": False,
    }
    result = run_risk_register(_control(), ctx)
    assert result.status == "warn"
    assert "missing" in result.message.lower()


def test_missing_risk_register_fails_strict(tmp_path: Path) -> None:
    ctx = {
        "root": REPO,
        "tenant_security": tmp_path / "security",
        "mode": "ci",
        "strict": True,
    }
    result = run_risk_register(_control(), ctx)
    assert result.status == "fail"
    assert "missing" in result.message.lower()


def test_valid_template_passes_schema() -> None:
    templates = REPO / "fixtures" / "security" / "templates"
    ctx = {
        "root": REPO,
        "tenant_security": templates,
        "mode": "full",
        "strict": True,
    }
    result = run_risk_register(_control(), ctx)
    assert result.status == "pass", result.message
