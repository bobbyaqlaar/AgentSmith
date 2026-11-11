"""scripts/test/test_compliance_port.py — the compliance profile's provider side."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from agentsmith import compliance as c
import compliance_port as cp
import gate_pillars as gp
import gate_shell

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)
TEMPLATE = (REPO / "templates" / "compliance" / "dubai-gov" / "compliance.json").read_text()


def _repo(tmp_path: Path, placeholder: bool = False) -> Path:
    (tmp_path / ".agenticframework").mkdir()
    body = TEMPLATE if placeholder else TEMPLATE.replace("REPLACE_ME", "x.example.ae")
    (tmp_path / c.DECLARATION_FILE).write_text(body)
    return tmp_path


def _signed(obligation: str, expires: datetime | None = None) -> c.Attestation:
    return c.Attestation(
        id="T-1",
        obligation=obligation,
        actor="a@x",
        role="compliance_officer",
        evidence="doc",
        attested_at=(NOW - timedelta(days=1)).isoformat(),
        expires_at=expires.isoformat() if expires else None,
        channel="tty",
    )


def _row(result: dict, ident: str) -> dict:
    return next(r for r in result["rows"] if r["id"] == ident)


def test_no_declaration_is_no_profile(tmp_path: Path) -> None:
    assert cp.evaluate(tmp_path, "production", NOW, [], security={})["verdict"] == "no_profile"


def test_an_unreadable_declaration_is_never_no_profile(tmp_path: Path) -> None:
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / c.DECLARATION_FILE).write_text("{not json")
    with pytest.raises(c.ComplianceUnreadable):
        cp.evaluate(tmp_path, "production", NOW, [], security={})


def test_a_missing_signature_blocks_production_and_only_waits_in_ci(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    attested = [r for r in cp.load_catalogue() if r.kind == "attested"]
    production = cp.evaluate(root, "production", NOW, [], security={}, catalogue=attested)
    assert production["verdict"] == "fail" and _row(production, "OB-RISK")["result"] == "fail"
    ci = cp.evaluate(root, "ci", NOW, [], security={}, catalogue=attested)
    assert ci["verdict"] == "pass" and _row(ci, "OB-RISK")["result"] == "pending"


def test_a_valid_signature_passes_and_an_expired_one_does_not(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    good = cp.evaluate(root, "production", NOW, [_signed("OB-RISK", NOW + timedelta(days=1))], security={})
    assert _row(good, "OB-RISK")["result"] == "pass"
    stale = cp.evaluate(root, "production", NOW, [_signed("OB-RISK", NOW - timedelta(hours=1))], security={})
    assert _row(stale, "OB-RISK")["result"] == "fail"


def _mech(ident: str, mechanism: str, layer: str = "app", blocks: tuple[str, ...] = ("production",)) -> c.Obligation:
    return c.Obligation.model_validate(
        {
            "id": ident,
            "title": "t",
            "refs": {},
            "layer": layer,
            "class": "verified",
            "phases": ["build"],
            "mechanism": mechanism,
            "owner_role": "x",
            "instructions": "i",
            "evidence": "e",
            "blocks": list(blocks),
            "profiles": ["dubai-gov"],
        }
    )


def test_a_declared_gap_does_not_pass(tmp_path: Path) -> None:
    rows = {"SEC-X-001": {"result": "gap", "message": "not built"}}
    result = cp.evaluate(_repo(tmp_path), "production", NOW, [], security=rows, catalogue=[_mech("OB-X", "SEC-X-001")])
    assert result["verdict"] == "fail"


def test_a_security_provider_that_could_not_run_fails(tmp_path: Path) -> None:
    result = cp.evaluate(
        _repo(tmp_path),
        "production",
        NOW,
        [],
        security={},
        security_error="no answer",
        catalogue=[_mech("OB-X", "SEC-X-001")],
    )
    assert result["verdict"] == "fail"


def test_a_placeholder_fails_the_declaration_row(tmp_path: Path) -> None:
    catalogue = [_mech("OB-X", "declaration:complete")]
    assert (
        cp.evaluate(_repo(tmp_path, placeholder=True), "production", NOW, [], security={}, catalogue=catalogue)[
            "verdict"
        ]
        == "fail"
    )


def test_a_filled_declaration_passes_it(tmp_path: Path) -> None:
    catalogue = [_mech("OB-X", "declaration:complete")]
    assert cp.evaluate(_repo(tmp_path), "production", NOW, [], security={}, catalogue=catalogue)["verdict"] == "pass"


def test_an_unknown_mechanism_fails(tmp_path: Path) -> None:
    assert (
        cp.evaluate(_repo(tmp_path), "production", NOW, [], security={}, catalogue=[_mech("OB-X", "mystery")])[
            "verdict"
        ]
        == "fail"
    )


def test_a_provider_row_is_not_run_in_a_tenant(tmp_path: Path) -> None:
    catalogue = [_mech("OB-X", "SEC-X-001", layer="provider")]
    assert (
        _row(cp.evaluate(_repo(tmp_path), "production", NOW, [], security={}, catalogue=catalogue), "OB-X")["result"]
        == "not_applicable"
    )


def test_every_catalogue_row_parses_and_attested_rows_say_who_and_what() -> None:
    catalogue = cp.load_catalogue()
    assert len({r.id for r in catalogue}) == len(catalogue)
    for row in catalogue:
        assert (row.kind == "attested") == (row.mechanism is None), row.id


def test_published_schemas_match_the_models() -> None:
    base = REPO / "contract" / "compliance" / "v1"
    assert json.loads((base / "declaration.schema.json").read_text()) == c.Declaration.model_json_schema()
    assert json.loads((base / "attestation.schema.json").read_text()) == c.Attestation.model_json_schema()
    assert json.loads((base / "obligation.schema.json").read_text()) == c.Obligation.model_json_schema(by_alias=True)


def test_generated_copies_match_the_catalogue() -> None:
    done = subprocess.run(
        [sys.executable, "scripts/generate-ide-config.py", "--compliance", "--check", "--repo-root", str(REPO)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_attest_refuses_without_a_terminal(tmp_path: Path) -> None:
    (tmp_path / ".agenticframework").mkdir()
    done = subprocess.run(
        [sys.executable, "-m", "agentsmith.cli", "attest", "OB-RISK", "--evidence", "x", "--role", "r"],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        start_new_session=True,
        env={"PATH": "/usr/bin:/bin", "AGENTSMITH_DIR": str(REPO), "PYTHONPATH": str(REPO), "HOME": str(tmp_path)},
    )
    assert done.returncode == 2 and "terminal" in done.stderr
    assert not (tmp_path / c.ATTESTATIONS_FILE).exists()


def test_the_shell_gate_refuses_attest_and_writes_to_the_file() -> None:
    names = [n for n in dir(gate_shell) if n in ("refusal", "check", "refused", "judge")]
    assert names, "gate_shell has no entry point this test knows"
    judge = getattr(gate_shell, names[0])
    assert judge("agentsmith attest OB-RISK --evidence x --role r")
    assert judge("echo x >> .agenticframework/attestations.jsonl")


def test_the_profile_only_strengthens() -> None:
    enforced = {"profile": "dubai-gov", "mode": "enforce"}
    assert gp.compliance_transition_problems(enforced, None, [])
    assert gp.compliance_transition_problems(enforced, {"profile": "dubai-gov", "mode": "report"}, [])
    assert not gp.compliance_transition_problems(enforced, enforced, [])
    assert not gp.compliance_transition_problems(None, enforced, [])


def test_signatures_are_not_sent_outside_the_boundary(tmp_path: Path, monkeypatch) -> None:
    import httpx

    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("OPS_PORTAL_URL", "https://portal.vendor.example.com")
    monkeypatch.setenv("OPS_PORTAL_TOKEN", "t")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("nothing may be sent"))
    records, why = cp.exchange([])
    assert records == [] and "boundary" in why


# ── The 4.1.0 release review: R15, R24 ──


def _at(obligation: str, attested: datetime, expires: datetime | None) -> c.Attestation:
    return c.Attestation(id="T-2", obligation=obligation, actor="a@x", role="compliance_officer", evidence="doc",
                         attested_at=attested.isoformat(), expires_at=expires.isoformat() if expires else None,
                         channel="tty")


@pytest.mark.parametrize("expires", [None, NOW + timedelta(days=99_999)])
def test_a_recurring_obligation_expires_on_its_catalogue_period(tmp_path: Path, expires) -> None:
    """R15: a 2020 signature with no expiry, or one of 99,999 days, satisfied OB-ISR-VERSION today."""
    root = _repo(tmp_path)
    old = _at("OB-ISR-VERSION", NOW - timedelta(days=366 * 6), expires)
    assert _row(cp.evaluate(root, "production", NOW, [old], security={}), "OB-ISR-VERSION")["result"] == "fail"
    fresh = _at("OB-ISR-VERSION", NOW - timedelta(days=10), expires)
    row = _row(cp.evaluate(root, "production", NOW, [fresh], security={}), "OB-ISR-VERSION")
    assert row["result"] == "pass" and row["expires_at"].startswith((NOW + timedelta(days=355)).date().isoformat())


def test_a_signature_dated_in_the_future_does_not_count(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    ahead = _at("OB-RISK", NOW + timedelta(days=30), NOW + timedelta(days=60))
    assert _row(cp.evaluate(root, "production", NOW, [ahead], security={}), "OB-RISK")["result"] == "fail"


def test_an_enforced_profile_without_its_declaration_fails(tmp_path: Path) -> None:
    """R24: the port answered no_profile, and the job was green."""
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "process-gates.json").write_text(
        json.dumps({"compliance": {"profile": "dubai-gov", "mode": "enforce"}}))
    result = cp.evaluate(tmp_path, "ci", NOW, [], security={})
    assert result["verdict"] == "fail" and "compliance.json is missing" in result["reason"]


def test_the_shell_gate_protects_the_declaration() -> None:
    assert gate_shell._protects(".agenticframework/compliance.json")


# ── The 4.1.0 release review: R23 ──


@pytest.mark.parametrize("cited, verdict", [
    ("agentsmith/test/test_compliance_runtime.py", "pass"),
    ("portal/test/signInPolicy.test.ts", "pass"),
    ("portal/app/api/audit/export/route.ts", "fail"),
    ("portal/test/recordCases.ts", "fail"),
])
def test_a_release_row_passes_only_on_a_test_ci_runs(tmp_path: Path, cited, verdict) -> None:
    """R23: a file that existed read as "tested in AgentSmith's own CI"."""
    found = cp._judge_mechanism(tmp_path, _mech("OB-X", f"release:{cited}", layer="provider"), {}, {}, "", {},
                                own=True)
    assert found[0] == verdict, found


def test_a_portal_test_no_script_runs_is_not_evidence(tmp_path: Path, monkeypatch) -> None:
    portal = tmp_path / "portal"
    (portal / "test").mkdir(parents=True)
    (portal / "test" / "lonely.test.ts").write_text("")
    (portal / "package.json").write_text(json.dumps({"scripts": {"test": "node test/other.test.ts"}}))
    monkeypatch.setattr(cp, "FRAMEWORK", tmp_path)
    found = cp._judge_mechanism(tmp_path, _mech("OB-X", "release:portal/test/lonely.test.ts", layer="provider"),
                                {}, {}, "", {}, own=True)
    assert found == ("fail", "portal/test/lonely.test.ts is in neither `npm test` nor `npm run test:db`, "
                             "so CI never runs it")
