"""
scripts/test/test_gate_contract_v2.py — gate contract 2: a tenant's CI asks its
declared provider (.agent-rfc/designs/gate-contract-ci.md).

Contract 2 is contract 1 plus the `ci` event, which never falls back to a
framework path. These tests hold AgentSmith to it as a provider, hold the
published files to the models and to version 1, and run the tenant's launcher —
`.githooks/process-gate ci` — through every way a CI check can end.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from test_send_dev_record import Portal

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")

V1 = REPO / "contract" / "gate" / "v1"
V2 = REPO / "contract" / "gate" / "v2"
LAUNCHER = REPO / ".githooks" / "process-gate"
PROVIDER = f"{sys.executable} -m runtime.cli gate"


# ── The published contract ────────────────────────────────────────────────────


def test_agentsmith_passes_contract_2(tmp_path, monkeypatch):
    from runtime import conformance

    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("PYTHONPATH", str(REPO))

    report = conformance.run(PROVIDER, tmp_path / "work", contract=2)

    assert report.passed, report.render()
    assert any(r.case.event_name == "ci" for r in report.results), "the ci cases ran"


def test_the_v2_schemas_are_the_v2_models():
    """Generated, not written twice — compared whole, not by property names, so
    a changed type or default cannot drift from what a third party implements."""
    import gate_models as gm

    for name, model in (("event.schema.json", gm.GateEventV2), ("decision.schema.json", gm.DecisionV2)):
        published = json.loads((V2 / name).read_text(encoding="utf-8"))
        generated = model.model_json_schema()
        for key in ("description", "$schema", "$id"):
            published.pop(key, None)
            generated.pop(key, None)
        assert published == generated, f"contract/gate/v2/{name} no longer matches {model.__name__}"


def test_version_2_carries_version_1_unchanged():
    """A provider that passes 2 passes 1: v2 holds v1's cases and fixture
    word for word, and adds to them — so the two cannot quietly disagree."""
    v1_cases = json.loads((V1 / "cases.json").read_text())["cases"]
    v2_cases = json.loads((V2 / "cases.json").read_text())["cases"]
    assert v2_cases[: len(v1_cases)] == v1_cases
    added = v2_cases[len(v1_cases):]
    assert [c["event"]["paths"] for c in added if c["event_name"] != "ci"] == [[".agenticframework/providers.json"]], \
        "v2 adds the ci cases and the one rule it makes binding on every provider: the declaration is governed"

    v1_fixture = json.loads((V1 / "fixture.json").read_text())
    v2_fixture = json.loads((V2 / "fixture.json").read_text())
    assert v2_fixture["files"] == v1_fixture["files"]
    assert v2_fixture["commit"] == v1_fixture["commit"]


def test_every_history_step_changes_something():
    """A step that rewrites a file with what it held makes no commit — the
    fixture then fails to build, which is how the first draft of it failed."""
    fixture = json.loads((V2 / "fixture.json").read_text())
    state = dict(fixture["files"])
    for step in fixture["history"]:
        assert any(state.get(rel) != body for rel, body in step["files"].items()), step["tag"]
        state.update(step["files"])


def test_what_adopt_declares_is_a_valid_contract_2_declaration():
    import jsonschema

    from runtime.adopt import providers_declaration

    schema = json.loads((V2 / "providers.schema.json").read_text(encoding="utf-8"))
    declared = json.loads(providers_declaration())
    jsonschema.validate(declared, schema)
    assert declared["contract"] >= 2, "adopt declares contract 2 or later (3 since gate-local-events.md)"
    jsonschema.validate({**declared, "providers": {"gate": "none"}}, schema)
    for bad in ({"contract": 2, "providers": {"gate": {"command": "x", "contract": 3}}},
                {"contract": 2, "providers": {"gate": {"command": "x", "setup": ""}}}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


def test_a_version_1_declaration_still_reads_as_version_1():
    """Every declaration written before contract 2 keeps its meaning."""
    import jsonschema

    schema = json.loads((V1 / "providers.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate({"contract": 1, "providers": {"gate": {"command": "agentsmith gate", "version": "^2"}}},
                        schema)


# ── The tenant's launcher: `.githooks/process-gate ci` ────────────────────────


@pytest.fixture()
def fixture_repo(tmp_path):
    from runtime.conformance import build_fixture

    return build_fixture(tmp_path / "repo", 2)


def _declare(root: Path, gate, contract: int = 2) -> None:
    (root / ".agenticframework" / "providers.json").write_text(
        json.dumps({"contract": contract, "providers": {"gate": gate}}) + "\n", encoding="utf-8")


def _ci(root: Path, base: str, head: str, **env: str) -> subprocess.CompletedProcess:
    run_env = {**os.environ, "AGENTSMITH_DIR": str(REPO), "PYTHONPATH": str(REPO),
               "AGENTSMITH_PYTHON": sys.executable, **env}
    run_env.pop("GOVERNANCE_PROVIDER", None)
    run_env.pop("GITHUB_STEP_SUMMARY", None)
    return subprocess.run(["bash", str(LAUNCHER), "ci", "--base", base, "--head", head], cwd=root,
                          env=run_env, capture_output=True, text=True, check=False)


def test_at_contract_2_a_passing_range_passes(fixture_repo):
    _declare(fixture_repo, {"command": PROVIDER})

    result = _ci(fixture_repo, "fixture", "clean")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Process gates" in result.stdout, "the provider's report is printed for the person reading CI"


def test_at_contract_2_a_refused_range_fails_with_the_providers_reasons(fixture_repo):
    _declare(fixture_repo, {"command": PROVIDER})

    result = _ci(fixture_repo, "clean", "undesigned")

    assert result.returncode == 1
    assert "::error title=Process gate" in result.stdout
    assert "Design:" in result.stdout, "the provider's own annotations reach CI"


@pytest.mark.parametrize("command, why", [
    ("false", "printed no decision"),
    ("no-such-gate-provider-xyz", "not installed"),
])
def test_at_contract_2_no_decision_fails_and_never_falls_back(fixture_repo, command, why):
    """The range is CLEAN: AgentSmith's own gate, found through $AGENTSMITH_DIR,
    would pass it. Failing proves the launcher did not fall back to it."""
    _declare(fixture_repo, {"command": command})

    result = _ci(fixture_repo, "fixture", "clean")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "gave no decision" in result.stdout and why in result.stdout
    assert "nothing falls back" in result.stdout


def test_at_contract_1_ci_is_what_it_always_was(fixture_repo):
    """A provider that would fail every CI check, declared at contract 1, is not
    asked: the framework's own gate runs, as before contract 2 existed."""
    _declare(fixture_repo, {"command": "false"}, contract=1)

    result = _ci(fixture_repo, "fixture", "clean")

    assert result.returncode == 0, result.stdout + result.stderr


def test_the_gate_entrys_contract_wins_over_the_declarations(fixture_repo):
    _declare(fixture_repo, {"command": "false", "contract": 2}, contract=1)
    assert _ci(fixture_repo, "fixture", "clean").returncode == 1, "the gate entry says 2"

    _declare(fixture_repo, {"command": "false", "contract": 1}, contract=2)
    assert _ci(fixture_repo, "fixture", "clean").returncode == 0, "the gate entry says 1"


def test_a_repository_declared_ungoverned_is_not_checked(fixture_repo):
    _declare(fixture_repo, "none")

    result = _ci(fixture_repo, "clean", "undesigned")

    assert result.returncode == 0
    assert "ungoverned" in result.stdout


def test_a_ref_that_is_not_a_ref_is_refused_before_anything_runs(fixture_repo):
    _declare(fixture_repo, {"command": PROVIDER})

    result = _ci(fixture_repo, "x;touch pwned", "clean")

    assert result.returncode == 1
    assert "not a git ref" in result.stdout
    assert not (fixture_repo / "pwned").exists()


# ── The record, sent by the provider ──────────────────────────────────────────


def _decide(root: Path, base: str, head: str, **env: str) -> dict:
    run_env = {**os.environ, "AGENTSMITH_DIR": str(REPO), "PYTHONPATH": str(REPO), **env}
    for unset in ("AGENTSMITH_PORTAL_URL", "AGENTSMITH_PORTAL_INGEST_TOKEN", "GITHUB_ACTIONS"):
        if unset not in env:
            run_env.pop(unset, None)
    done = subprocess.run([sys.executable, "-m", "runtime.cli", "gate", "ci"], cwd=root, env=run_env,
                          input=json.dumps({"kind": "range", "base": base, "head": head}),
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_without_a_portal_the_range_is_judged_and_the_report_says_nothing_was_sent(fixture_repo):
    answer = _decide(fixture_repo, "fixture", "clean")

    assert answer["decision"] == "allow"
    assert "record was not sent" in answer["report"]


def test_a_stored_record_is_reported_and_the_token_never_appears(fixture_repo):
    portal = Portal(200, {"stored": 1})
    try:
        answer = _decide(fixture_repo, "fixture", "clean", AGENTSMITH_PORTAL_URL=portal.url,
                         AGENTSMITH_PORTAL_INGEST_TOKEN="asi_secret_value")
    finally:
        portal.close()

    assert answer["decision"] == "allow"
    [(auth, body)] = portal.received
    assert auth == "Bearer asi_secret_value" and body["schema"] == 1
    assert "asi_secret_value" not in json.dumps(answer), "SECURITY: the token never enters the decision"


def test_a_portal_that_refuses_the_record_fails_the_answer_with_its_own_reason(fixture_repo):
    """The record step used to fail the job here, so a wrong token could not
    hide behind a green check. The provider keeps that — and says the range
    itself passed, so nobody goes looking for a design that is not missing."""
    portal = Portal(401, {"error": "unknown token"})
    try:
        answer = _decide(fixture_repo, "fixture", "clean", AGENTSMITH_PORTAL_URL=portal.url,
                         AGENTSMITH_PORTAL_INGEST_TOKEN="asi_wrong")
    finally:
        portal.close()

    assert answer["decision"] == "deny"
    assert "passes the process gate, but the portal refused its record" in answer["text"]
    assert "unknown token" in answer["report"]
