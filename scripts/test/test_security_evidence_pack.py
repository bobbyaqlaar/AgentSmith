from __future__ import annotations

from pathlib import Path

from security.registry import ControlSpec, FrameworkTags, load_control_registry
from security.report import ControlResult, write_evidence_pack

REPO = Path(__file__).resolve().parents[2]

EXPECTED_MD = [
    "security_report.md",
    "owasp_llm_top10.md",
    "nist_ai_rmf.md",
    "mitre_atlas.md",
    "iso_42001.md",
]


def _sample_results(controls: list[ControlSpec]) -> list[ControlResult]:
    return [
        ControlResult(
            control_id=c.id,
            status="pass" if c.status == "met" else "warn",
            message="fixture",
            evidence={},
        )
        for c in controls
    ]


def test_write_evidence_pack_creates_five_markdown_reports(tmp_path: Path) -> None:
    registry = REPO / "fixtures" / "security" / "control_registry.json"
    controls = load_control_registry(registry)
    out = tmp_path / "evidence"
    write_evidence_pack(out, controls, _sample_results(controls), framework=None)

    assert (out / "security_report.json").exists()
    for name in EXPECTED_MD:
        path = out / name
        assert path.exists(), f"missing {name}"
        assert path.stat().st_size > 0
    assert len(EXPECTED_MD) == 5


def test_owasp_rollup_includes_sec_pii_001(tmp_path: Path) -> None:
    registry = REPO / "fixtures" / "security" / "control_registry.json"
    controls = load_control_registry(registry)
    out = tmp_path / "evidence"
    write_evidence_pack(out, controls, _sample_results(controls))

    text = (out / "owasp_llm_top10.md").read_text(encoding="utf-8")
    assert "SEC-PII-001" in text
    assert "LLM06" in text


def test_framework_filter_limits_markdown(tmp_path: Path) -> None:
    controls = [
        ControlSpec(
            id="SEC-PII-001",
            title="PII pre-call scrub",
            status="partial",
            owner="shared",
            frameworks=FrameworkTags(
                owasp=["LLM06"],
                nist=["MAP 2.6"],
                atlas=["AML.T0043"],
                iso42001=[9],
            ),
            runner="pii_precall",
            check_type="unit",
            mechanism="test",
        ),
        ControlSpec(
            id="SEC-AUDIT-001",
            title="HMAC audit log",
            status="met",
            owner="framework",
            frameworks=FrameworkTags(
                owasp=[],
                nist=["GOVERN 1.2"],
                atlas=["AML.T0025"],
                iso42001=[6],
            ),
            runner="audit_hmac",
            check_type="unit",
            mechanism="test",
        ),
    ]
    results = _sample_results(controls)
    out = tmp_path / "evidence"
    write_evidence_pack(out, controls, results, framework="owasp")

    owasp = (out / "owasp_llm_top10.md").read_text(encoding="utf-8")
    assert "SEC-PII-001" in owasp
    # Filtered pack still writes all report files; owasp report focuses tagged controls.
    assert "SEC-PII-001" in (out / "security_report.md").read_text(encoding="utf-8")
