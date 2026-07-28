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


# ── Un-edited template detection ─────────────────────────────────────────────


def _seed_template(dest_dir: Path) -> Path:
    """Reproduce what ai-tenant-init / install-ai-stack.sh do (G5): copy the
    shipped template into a repo's .agent-rfc/security/ and leave it there."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    src = REPO / "fixtures" / "security" / "templates" / "risk_register.yaml"
    dest = dest_dir / "risk_register.yaml"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def test_seeded_but_unedited_register_fails_strict(tmp_path: Path) -> None:
    """Schema validity is not a risk register. A repo that seeded the pack and
    never filled it in used to pass --strict and publish an evidence pack whose
    SEC-RISK-001 row cited RISK-EXAMPLE-001 — a compliance artifact certifying
    a placeholder."""
    security = tmp_path / "security"
    _seed_template(security)
    result = run_risk_register(
        _control(), {"root": REPO, "tenant_security": security, "mode": "ci", "strict": True}
    )
    assert result.status == "fail"
    assert "RISK-EXAMPLE-001" in result.message


def test_seeded_but_unedited_register_warns_non_strict(tmp_path: Path) -> None:
    security = tmp_path / "security"
    _seed_template(security)
    result = run_risk_register(
        _control(), {"root": REPO, "tenant_security": security, "mode": "ci", "strict": False}
    )
    assert result.status == "warn"


def test_validating_the_template_itself_is_still_allowed() -> None:
    """The use_template_fallback path validates the shipped template on
    purpose; only shipping it AS your register is the problem."""
    template = REPO / "fixtures" / "security" / "templates" / "risk_register.yaml"
    result = run_risk_register(
        _control(),
        {
            "root": REPO,
            "tenant_security": Path("/nonexistent"),
            "risk_register_path": template,
            "mode": "ci",
            "strict": True,
        },
    )
    assert result.status == "pass"


def test_the_frameworks_own_register_is_not_the_template() -> None:
    """This repo carried a byte-copy of the placeholder, so its own self-test
    graded SEC-RISK-001 against RISK-EXAMPLE-001 and reported Met."""
    result = run_risk_register(
        _control(),
        {
            "root": REPO,
            "tenant_security": REPO / ".agent-rfc" / "security",
            "mode": "ci",
            "strict": True,
        },
    )
    assert result.status == "pass"
    assert "6 entries" in result.message
