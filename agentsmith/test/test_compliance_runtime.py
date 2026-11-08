"""agentsmith/test/test_compliance_runtime.py — what a tenant app on a compliance
profile refuses, and that without a profile nothing changes.

The tests that need Postgres run when COMPLIANCE_TEST_DSN names a database.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from agentsmith import compliance as c
from agentsmith.workflows import base_workflow
from agentsmith.workflows.base_workflow import BaseAgentWorkflow

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = (
    (REPO / "templates" / "compliance" / "dubai-gov" / "compliance.json")
    .read_text()
    .replace("REPLACE_ME", "x.example.ae")
)
DSN = os.environ.get("COMPLIANCE_TEST_DSN", "")
needs_db = pytest.mark.skipif(not DSN, reason="COMPLIANCE_TEST_DSN is not set")


@pytest.fixture()
def profile(tmp_path, monkeypatch):
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / c.DECLARATION_FILE).write_text(TEMPLATE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(c.PATH_ENV, raising=False)
    monkeypatch.setenv(c.RECORD_KEY_ENV, "test-key")
    return tmp_path


@pytest.fixture()
def no_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(c.PATH_ENV, raising=False)
    return tmp_path


def test_without_a_profile_nothing_is_recorded_or_refused(no_profile):
    assert c.record("t", "k", {}) is None
    c.require_running("t")
    c.guard_model_call("t", None, None, "https://anywhere.example.com", "m")


def test_a_deployment_that_lost_its_declaration_is_not_no_profile(no_profile, monkeypatch):
    monkeypatch.setenv(c.PROFILE_ENV, "dubai-gov")
    with pytest.raises(c.ComplianceUnreadable):
        c.profile_active()


def test_a_broken_declaration_is_never_read_as_no_profile(no_profile):
    (no_profile / ".agenticframework").mkdir()
    (no_profile / c.DECLARATION_FILE).write_text("{")
    with pytest.raises(c.ComplianceUnreadable):
        c.load_declaration()


def test_no_signing_key_refuses(profile, monkeypatch):
    monkeypatch.delenv(c.RECORD_KEY_ENV)
    with pytest.raises(c.ComplianceRefused, match="OB-RECORD"):
        c.record("t", "k", {})


def test_no_database_refuses(profile, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(c.ComplianceRefused, match="OB-RECORD"):
        c.record("t", "k", {})


def test_an_unreachable_database_refuses(profile, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody@127.0.0.1:1/none?connect_timeout=1")
    with pytest.raises(c.ComplianceRefused, match="OB-RECORD"):
        c.record("t", "k", {})


def test_a_stop_flag_nobody_can_read_refuses(profile, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody@127.0.0.1:1/none?connect_timeout=1")
    with pytest.raises(c.ComplianceRefused, match="OB-STOP"):
        c.require_running("t")


@pytest.fixture()
def quiet(monkeypatch):
    """Stop flag clear and record written, so a test sees only the rule it is about."""
    written: list[tuple[str, dict]] = []
    monkeypatch.setattr(c, "require_running", lambda *a, **k: None)
    monkeypatch.setattr(c, "record", lambda tenant, kind, payload, **k: written.append((kind, payload)) or 1)
    return written


def test_classified_data_outside_the_boundary_is_refused(profile, quiet):
    with pytest.raises(c.ComplianceRefused, match="OB-RESIDENCY"):
        c.guard_model_call("t", None, "secret", "https://api.openai.com/v1", "m")
    assert quiet == []


def test_classified_data_inside_the_boundary_is_recorded(profile, quiet):
    c.guard_model_call("t", "wf", "secret", "https://x.example.ae/v1", "m")
    assert quiet[0][0] == "model_call"


def test_an_unstated_class_is_treated_as_classified(profile, quiet):
    with pytest.raises(c.ComplianceRefused, match="OB-RESIDENCY"):
        c.guard_model_call("t", None, None, "https://api.openai.com/v1", "m")


def test_an_unknown_class_is_treated_as_classified(profile, quiet):
    with pytest.raises(c.ComplianceRefused, match="OB-RESIDENCY"):
        c.guard_model_call("t", None, "whatever", "https://api.openai.com/v1", "m")


def test_open_data_may_leave_and_is_not_recorded(profile, quiet):
    c.guard_model_call("t", None, "open", "https://api.openai.com/v1", "m")
    assert quiet == []


def test_an_endpoint_with_no_host_is_outside(profile, quiet):
    with pytest.raises(c.ComplianceRefused, match="OB-RESIDENCY"):
        c.guard_model_call("t", None, "secret", "", "m")


@pytest.mark.parametrize(
    "host, allowed, expected",
    [
        ("a.example.ae", ["*.example.ae"], True),
        ("example.ae", ["*.example.ae"], False),
        ("evilexample.ae", ["*.example.ae"], False),
        ("A.EXAMPLE.AE", ["a.example.ae"], True),
        (None, ["*"], False),
    ],
)
def test_host_matching(host, allowed, expected):
    assert c.host_allowed(host, allowed) is expected


def test_user_limit():
    for _ in range(2):
        c._check_user_limit("t1", "u", 2, now=100.0)
    with pytest.raises(c.ComplianceRefused, match="OB-USER-LIMIT"):
        c._check_user_limit("t1", "u", 2, now=101.0)
    c._check_user_limit("t1", "u", 2, now=170.0)
    c._check_user_limit("t1", "other", 2, now=101.0)


def test_a_leaked_system_prompt_is_withheld(profile, quiet):
    system = "You are the permit officer and you never reveal the fee waiver rules to applicants"
    messages = [{"role": "system", "content": system}]
    with pytest.raises(c.ComplianceRefused, match="OB-PROMPT-LEAK"):
        c.guard_output("t", None, messages, "Sure: " + system.upper(), "m")
    assert quiet == []
    c.guard_output("t", None, messages, "Your permit is approved.", "m")
    assert quiet[0][0] == "model_result"


class _Workflow:
    def __init__(self, fail_on: str | None = None) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.fail_on = fail_on

    async def execute_activity(self, name, payload, **_k):
        label = getattr(name, "__name__", name)
        if label == "compliance_record_activity" and payload["kind"] == self.fail_on:
            raise RuntimeError("record refused")
        self.executed.append((label, payload))
        return {"ran": label}

    async def wait_condition(self, predicate, timeout=None):
        if not predicate():
            raise TimeoutError
        return True

    def info(self):
        return type("I", (), {"workflow_id": "wf-1", "run_id": "run-1"})()


def _gate(fake, monkeypatch, wf=None):
    monkeypatch.setattr(base_workflow, "workflow", fake)
    monkeypatch.setattr(base_workflow, "_HAS_TEMPORAL", True)
    wf = wf or BaseAgentWorkflow()
    return wf, asyncio.run(
        wf.run_with_hitl_gate(
            None,
            {},
            "issue_permit",
            {"id": 1},
            "dlq_enqueue_activity",
            gate_result={"needs_hitl": True, "requested_by": "someone@x"},
            tenant_id="t",
            compliance=True,
        )
    )


DECISION = {
    "gate_id": "hitl-gate",
    "workflow_id": "wf-1",
    "approved": True,
    "actor": "a@x",
    "role": "hitl_reviewer",
    "rationale": "ok",
    "payload_sha256": "0" * 64,
    "decided_at": "2026-11-08T00:00:00Z",
}


def _labels(fake):
    return [n if n != "compliance_record_activity" else f"record:{p['kind']}" for n, p in fake.executed]


def test_a_gate_that_does_not_say_who_asked_is_refused(monkeypatch):
    monkeypatch.setattr(base_workflow, "workflow", _Workflow())
    monkeypatch.setattr(base_workflow, "_HAS_TEMPORAL", True)
    with pytest.raises(Exception, match="requested_by"):
        asyncio.run(
            BaseAgentWorkflow().run_with_hitl_gate(
                None, {}, "a", {}, "d", gate_result={"needs_hitl": True}, tenant_id="t", compliance=True
            )
        )


def test_a_named_decision_is_recorded_before_and_after(monkeypatch):
    fake, wf = _Workflow(), BaseAgentWorkflow()
    wf._gate_decisions["hitl-gate"] = dict(DECISION)
    _gate(fake, monkeypatch, wf)
    assert _labels(fake) == ["record:hitl_pending", "record:hitl_decision", "issue_permit"]


def test_a_bare_boolean_does_not_answer_a_compliance_gate(monkeypatch):
    fake, wf = _Workflow(), BaseAgentWorkflow()
    wf._gate_approvals["hitl-gate"] = True
    wf._gate_approvals[wf._ANY_GATE] = True
    _gate(fake, monkeypatch, wf)
    assert "issue_permit" not in _labels(fake)
    assert "dlq_enqueue_activity" in _labels(fake)


def test_a_timeout_is_recorded_so_the_queue_clears(monkeypatch):
    fake = _Workflow()
    _gate(fake, monkeypatch)
    assert _labels(fake) == ["record:hitl_pending", "record:hitl_timeout", "dlq_enqueue_activity"]


def test_a_rejection_does_not_act(monkeypatch):
    fake, wf = _Workflow(), BaseAgentWorkflow()
    wf._gate_decisions["hitl-gate"] = {**DECISION, "approved": False}
    _gate(fake, monkeypatch, wf)
    assert "issue_permit" not in _labels(fake) and "record:hitl_decision" in _labels(fake)


@pytest.mark.parametrize("kind", ["hitl_pending", "hitl_decision"])
def test_no_record_no_action(monkeypatch, kind):
    fake, wf = _Workflow(fail_on=kind), BaseAgentWorkflow()
    wf._gate_decisions["hitl-gate"] = dict(DECISION)
    with pytest.raises(RuntimeError, match="record refused"):
        _gate(fake, monkeypatch, wf)
    assert "issue_permit" not in _labels(fake)


def test_compliance_needs_a_tenant(monkeypatch):
    monkeypatch.setattr(base_workflow, "_HAS_TEMPORAL", True)
    with pytest.raises(ValueError, match="tenant_id"):
        asyncio.run(
            BaseAgentWorkflow().run_with_hitl_gate(
                None, {}, "a", {}, "d", gate_result={"needs_hitl": True}, compliance=True
            )
        )


def _gateway(monkeypatch, models):
    from agentsmith.llm_gateway import LLMGateway

    monkeypatch.setenv("BUDGET_BACKEND", "memory")
    monkeypatch.setenv("IDEMPOTENCY_BACKEND", "memory")
    gateway = LLMGateway(tenant_id="acme")
    gateway.models = models
    return gateway


def test_a_fallback_outside_the_boundary_is_refused_before_it_is_called(profile, quiet, monkeypatch):
    models = {
        "developer": {
            "id": "in",
            "provider": "ollama",
            "endpoint": "https://x.example.ae/v1",
            "degrade_to": "cloud",
            "cost_per_input_token": 0,
            "cost_per_output_token": 0,
        },
        "cloud": {
            "id": "out",
            "provider": "ollama",
            "endpoint": "https://api.example.com/v1",
            "cost_per_input_token": 0,
            "cost_per_output_token": 0,
        },
    }
    gateway = _gateway(monkeypatch, models)
    called: list[str] = []

    async def invoke(cfg, *_a, **_k):
        called.append(cfg["id"])
        raise RuntimeError("quota")

    monkeypatch.setattr(gateway, "_invoke", invoke)
    monkeypatch.setattr(gateway, "_is_provider_exhausted", lambda exc: not isinstance(exc, c.ComplianceRefused))
    with pytest.raises(c.ComplianceRefused, match="OB-RESIDENCY"):
        asyncio.run(gateway.complete("hi", model_hint="developer", data_class="secret"))
    assert called == ["in"]


def test_a_stopped_app_does_not_answer_from_the_cache(profile, monkeypatch):
    def stopped(*_a, **_k):
        raise c.ComplianceRefused("OB-STOP", "stopped")

    monkeypatch.setattr(c, "require_running", stopped)
    gateway = _gateway(monkeypatch, {})
    with pytest.raises(c.ComplianceRefused, match="OB-STOP"):
        asyncio.run(gateway.complete("hi", idempotency_key="k"))


def test_best_effort_sends_stay_inside(profile):
    assert c.outbound_allowed("https://x.example.ae/hook")
    assert c.outbound_allowed("http://localhost:4318/v1/traces")
    assert not c.outbound_allowed("https://hooks.slack.com/services/x")


def test_no_profile_allows_every_send(no_profile):
    assert c.outbound_allowed("https://hooks.slack.com/services/x")


def test_traces_are_not_exported_outside_the_boundary(profile):
    from agentsmith import otlp

    assert otlp.span_exporter({"OTEL_EXPORTER_OTLP_ENDPOINT": "https://otlp.vendor.example.com"}) is None
    assert otlp.span_exporter({"OTEL_EXPORTER_OTLP_ENDPOINT": "https://x.example.ae"}) is not None


def test_a_status_report_is_not_sent_outside_the_boundary(profile, monkeypatch):
    from agentsmith import ops_contract

    monkeypatch.setenv(ops_contract.URL_ENV, "https://portal.vendor.example.com")
    monkeypatch.setenv(ops_contract.TOKEN_ENV, "t")
    sent = []

    class Http:
        Timeout = staticmethod(lambda **_k: None)

        @staticmethod
        def post(*a, **_k):
            sent.append(a)
            return type("R", (), {"status_code": 200})()

    monkeypatch.setitem(__import__("sys").modules, "httpx", Http)
    message = ops_contract.RunMessage.model_validate({"schema": 1, "run_id": "r", "status": "running"})
    assert ops_contract.send(message) is None
    assert sent == []


def test_every_answer_carries_a_mark_that_can_be_checked(monkeypatch):
    from agentsmith.llm_gateway import CompletionResult

    monkeypatch.setenv(c.RECORD_KEY_ENV, "k")
    result = CompletionResult(text="an answer", model_used="m", input_tokens=1, output_tokens=1, cost_usd=0.0)
    assert result.provenance["ai_generated"] is True and result.provenance["model"] == "m"
    assert c.verify_marking("an answer", result.provenance)
    assert not c.verify_marking("a different answer", result.provenance)
    forged = {**result.provenance, "model": "other"}
    assert not c.verify_marking("an answer", forged)
    assert c.marking_headers(result.provenance)["X-AI-Generated"] == "true"


# ── The sidecar ──────────────────────────────────────────────────────────────


@pytest.fixture()
def sidecar(profile, monkeypatch):
    import threading

    from agentsmith import runtime_server

    server = runtime_server.make_server("t", "secret-token", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _call(url, path, body=None, token="secret-token"):
    import httpx

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.post(url + path, json=body or {}, headers=headers, timeout=10.0)


def test_the_sidecar_passes_its_conformance_cases(sidecar):
    from agentsmith import conformance

    checks = conformance.run_runtime(sidecar, "secret-token")
    assert [c for c in checks if not c[1]] == [] and len(checks) >= 6


def test_a_wrong_token_is_refused(sidecar):
    assert _call(sidecar, "/v1/running", token="wrong").status_code == 401


def test_a_refusal_reaches_the_caller_named(sidecar, monkeypatch):
    def stopped(*_a, **_k):
        raise c.ComplianceRefused("OB-STOP", "stopped")

    monkeypatch.setattr(c, "require_running", stopped)
    response = _call(sidecar, "/v1/running", {"workflow_id": "w"})
    assert response.status_code == 403 and response.json()["obligation"] == "OB-STOP"


def test_a_blocked_answer_is_not_a_server_error(sidecar, monkeypatch):
    from agentsmith import runtime_server
    from agentsmith.prompt_guard import PromptGuardBlockedError

    def blocked(_tenant, _body):
        raise PromptGuardBlockedError("prompt blocked", reasons=["x"])

    monkeypatch.setitem(runtime_server.ROUTES, "/v1/complete", blocked)
    response = _call(sidecar, "/v1/complete", {"prompt": "x", "data_class": "open"})
    assert response.status_code == 422 and response.json()["blocked"] is True


def test_one_gateway_per_app(monkeypatch):
    from agentsmith import llm_gateway, runtime_server

    runtime_server._gateways.clear()
    monkeypatch.setattr(llm_gateway, "LLMGateway", lambda tenant_id: object())
    assert runtime_server._gateway("t") is runtime_server._gateway("t")
    runtime_server._gateways.clear()


def test_it_will_not_start_without_a_token():
    from agentsmith import runtime_server

    with pytest.raises(SystemExit):
        runtime_server.make_server("t", "", 0)


def test_it_binds_to_this_machine_only():
    from agentsmith import runtime_server

    server = runtime_server.make_server("t", "x", 0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


@needs_db
def test_a_gate_through_the_sidecar(sidecar, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DSN)
    gate = {"gate_id": f"g-{os.getpid()}", "workflow_id": f"w-{os.getpid()}"}
    ask = {**gate, "action": "issue", "input": {"n": 1}, "requested_by": "a@x"}
    assert _call(sidecar, "/v1/gate/request", ask).json()["status"] == "pending"
    assert _call(sidecar, "/v1/gate/status", gate).json()["status"] == "pending"
    digest = c.payload_digest({"n": 1})
    c.record("t", "hitl_decision", {**gate, "approved": True, "actor": "b@x", "payload_sha256": digest})
    answer = _call(sidecar, "/v1/gate/status", gate).json()
    assert answer["status"] == "approved" and answer["decision"]["actor"] == "b@x"
    # Asked again with other input: the old approval does not answer it.
    _call(sidecar, "/v1/gate/request", {**ask, "input": {"n": 2}})
    assert _call(sidecar, "/v1/gate/status", gate).json()["status"] == "pending"


# ── Against a real Postgres ──────────────────────────────────────────────────


@needs_db
def test_the_chain_detects_a_changed_record(profile):
    tenant = f"chain-{os.getpid()}"
    first = c.record(tenant, "a", {"n": 1}, dsn=DSN)
    second = c.record(tenant, "b", {"n": 2}, dsn=DSN)
    assert first and second and second > first
    assert c.verify_chain(tenant, dsn=DSN) == []
    connection = c._connect(DSN)
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE compliance_outbox DISABLE TRIGGER compliance_outbox_guard_row")
        cursor.execute(
            "UPDATE compliance_outbox SET payload = %s::jsonb WHERE record_id = %s", (json.dumps({"n": 9}), first)
        )
        cursor.execute("ALTER TABLE compliance_outbox ENABLE TRIGGER compliance_outbox_guard_row")
    connection.commit()
    connection.close()
    assert any("does not match" in p for p in c.verify_chain(tenant, dsn=DSN))


@needs_db
@pytest.mark.parametrize("statement", ["UPDATE compliance_outbox SET kind = 'x'", "DELETE FROM compliance_outbox"])
def test_the_outbox_cannot_be_changed(profile, statement):
    tenant = f"immutable-{os.getpid()}"
    c.record(tenant, "a", {}, dsn=DSN)
    connection = c._connect(DSN)
    try:
        with connection.cursor() as cursor, pytest.raises(Exception, match="append-only"):
            cursor.execute(statement + " WHERE tenant_id = %s", (tenant,))
    finally:
        connection.rollback()
        connection.close()


@needs_db
def test_stop_and_resume(profile, monkeypatch):
    tenant = f"stop-{os.getpid()}"
    monkeypatch.setenv("DATABASE_URL", DSN)
    c.require_running(tenant, "wf")
    c.set_stop(tenant, "wf", "bad output", "a@x")
    with pytest.raises(c.ComplianceRefused, match="bad output"):
        c.require_running(tenant, "wf")
    c.require_running(tenant, "other-run")
    c.clear_stop(tenant, "wf", "a@x")
    c.require_running(tenant, "wf")
    c.set_stop(tenant, c.APP_SCOPE, "all of it", "a@x")
    with pytest.raises(c.ComplianceRefused):
        c.require_running(tenant, "any")
    c.clear_stop(tenant, c.APP_SCOPE, "a@x")


@needs_db
def test_a_resume_that_cannot_be_recorded_does_not_happen(profile, monkeypatch):
    tenant = f"resume-{os.getpid()}"
    monkeypatch.setenv("DATABASE_URL", DSN)
    c.set_stop(tenant, c.APP_SCOPE, "held", "a@x")
    monkeypatch.delenv(c.RECORD_KEY_ENV)
    with pytest.raises(c.ComplianceRefused):
        c.clear_stop(tenant, c.APP_SCOPE, "a@x")
    with pytest.raises(c.ComplianceRefused, match="held"):
        c.require_running(tenant)


@needs_db
def test_forward_waits_for_the_portal(profile, monkeypatch):
    from agentsmith import ops_contract

    tenant = f"forward-{os.getpid()}"
    c.record(tenant, "a", {}, dsn=DSN)
    c.record(tenant, "b", {}, dsn=DSN)
    monkeypatch.setattr(ops_contract, "send", lambda m, **k: None)
    assert c.forward(tenant, dsn=DSN)[0] == 0
    sent = []
    monkeypatch.setattr(ops_contract, "send", lambda m, **k: sent.append(m.record_kind) or 200)
    assert c.forward(tenant, dsn=DSN) == (2, "")
    assert sent == ["a", "b"]
    assert c.forward(tenant, dsn=DSN) == (0, "")
