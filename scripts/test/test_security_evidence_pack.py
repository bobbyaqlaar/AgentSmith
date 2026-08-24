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


def _registry_controls() -> list[ControlSpec]:
    return load_control_registry(REPO / "fixtures" / "security" / "control_registry.json")


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


def test_pack_records_the_mode_it_was_produced_in(tmp_path: Path) -> None:
    """A smoke run narrows the registry to three controls before anything runs.

    Without the mode the pack is indistinguishable from a full run that happens
    to have three controls — every one green, nothing saying the other twenty
    were never attempted.
    """
    import json

    out = tmp_path / "pack"
    controls = _registry_controls()[:3]
    write_evidence_pack(out, controls, _sample_results(controls), mode="smoke")

    payload = json.loads((out / "security_report.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "smoke"
    md = (out / "security_report.md").read_text(encoding="utf-8")
    assert "Mode: `smoke`" in md
    assert "not attempted, not passed" in md


def test_a_control_with_no_result_reads_as_not_run_not_skip(tmp_path: Path) -> None:
    """`skip` means not-applicable, which _resolve_exit treats as green.

    A control nothing produced a result for went UNEXAMINED — the distinction
    that let 14 of 23 controls report clean while nothing checked them.
    """
    from security.report import _status_for

    controls = _registry_controls()
    assert _status_for(controls[0], {}) == "not run"
