"""agentsmith/test/test_compliance_runtime.py — what a tenant app on a compliance
profile refuses, and that without a profile nothing changes.

The tests that need Postgres run when COMPLIANCE_TEST_DSN names a database.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
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
# Set by the CI job that runs these with a database: there a skip would be a pass nobody
# earned (the 4.1.0 review's second pass, P2-R23).
REQUIRE_DB = os.environ.get("AGENTSMITH_REQUIRE_DB") == "1"


def test_the_database_tests_run_where_they_are_required():
    assert DSN or not REQUIRE_DB, (
        "AGENTSMITH_REQUIRE_DB=1 and COMPLIANCE_TEST_DSN is not set: the database tests would be skipped")


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
    """Temporal's `workflow` module, enough for a gate. `deliver` is the reviewer's
    decision, signalled while the gate waits: after its pending record is written."""

    def __init__(self, fail_on: str | None = None, deliver: dict | None = None, wf=None) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.fail_on = fail_on
        self.deliver, self.wf = deliver, wf

    async def execute_activity(self, name, payload, **_k):
        label = getattr(name, "__name__", name)
        if label == "compliance_record_activity" and payload["kind"] == self.fail_on:
            raise RuntimeError("record refused")
        self.executed.append((label, payload))
        if label == "compliance_record_activity" and payload["kind"] == "hitl_pending":
            if self.deliver:
                self.wf.hitl_decide(dict(self.deliver))
            # What the real activity answers: the digest of the input as it received it,
            # after Temporal serialized it (P2-R13).
            return {"record_id": PENDING_RECORD, "input_sha256": c.payload_digest(_as_received(payload)["input"])}
        return {"ran": label}

    async def wait_condition(self, predicate, timeout=None):
        if not predicate():
            raise TimeoutError
        return True

    def info(self):
        return type("I", (), {"workflow_id": "wf-1", "run_id": "run-1"})()


def _as_received(payload: dict) -> dict:
    """The record's payload as the activity sees it: through Temporal's data converter."""
    from temporalio.converter import DataConverter

    converter = DataConverter.default.payload_converter
    return converter.from_payloads(converter.to_payloads([payload]), [dict])[0]["payload"]


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


PENDING_RECORD = 41  # the record id the fake pending activity answers with

DECISION = {
    "gate_id": "hitl-gate",
    "workflow_id": "wf-1",
    "approved": True,
    "actor": "a@x",
    "role": "hitl_reviewer",
    "rationale": "ok",
    "payload_sha256": c.payload_digest({"id": 1}),
    "decided_at": "2026-11-08T00:00:00Z",
    "request_record_id": PENDING_RECORD,
}


def _deciding(decision: dict, fail_on: str | None = None):
    wf = BaseAgentWorkflow()
    return _Workflow(fail_on=fail_on, deliver=decision, wf=wf), wf


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
    fake, wf = _deciding(DECISION)
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
    fake, wf = _deciding({**DECISION, "approved": False})
    _gate(fake, monkeypatch, wf)
    assert "issue_permit" not in _labels(fake) and "record:hitl_decision" in _labels(fake)


@pytest.mark.parametrize("kind", ["hitl_pending", "hitl_decision"])
def test_no_record_no_action(monkeypatch, kind):
    fake, wf = _deciding(DECISION, fail_on=kind)
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
    asked = _call(sidecar, "/v1/gate/request", ask).json()
    assert asked["status"] == "pending"
    assert _call(sidecar, "/v1/gate/status", gate).json()["status"] == "pending"
    digest = c.payload_digest({"n": 1})
    c.record("t", "hitl_decision", {**gate, "approved": True, "actor": "b@x", "payload_sha256": digest,
                                    "request_record_id": asked["record_id"]})
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


# ── The 4.1.0 release review: R13, R14, R19, R21, R25, R29 ──


def test_a_decision_given_before_the_gate_asked_does_not_answer_it(monkeypatch):
    """R14: an approval that arrived after a timeout answered the next request, whatever its input."""
    fake, wf = _Workflow(), BaseAgentWorkflow()
    wf._gate_decisions["hitl-gate"] = dict(DECISION)
    _gate(fake, monkeypatch, wf)
    assert "issue_permit" not in _labels(fake) and "record:hitl_timeout" in _labels(fake)


def test_a_decision_about_other_input_does_not_answer_the_gate(monkeypatch):
    """R14: the decision must name the digest of the input this request shows."""
    fake, wf = _deciding({**DECISION, "payload_sha256": c.payload_digest({"id": 2})})
    _gate(fake, monkeypatch, wf)
    assert "issue_permit" not in _labels(fake) and "record:hitl_decision" not in _labels(fake)


# ── The 4.1.0 review's second pass: P2-R13 (.agent-rfc/designs/review-pass2-majors.md) ──


@dataclasses.dataclass
class _Payment:
    to: str
    amount: float
    when: datetime.datetime


def test_a_decision_answers_an_input_temporal_serializes_differently(monkeypatch):
    """P2-R13: the workflow waited for a digest of the Python object, the reviewer's
    decision named the digest of the serialized input, and the gate always timed out."""
    payment = _Payment("x", 10.0, datetime.datetime(2026, 11, 11, 10, 0))
    shown = _as_received({"payload": {"input": payment}})["input"]  # what the reviewer saw
    fake, wf = _deciding({**DECISION, "payload_sha256": c.payload_digest(shown)})
    monkeypatch.setattr(base_workflow, "workflow", fake)
    monkeypatch.setattr(base_workflow, "_HAS_TEMPORAL", True)
    asyncio.run(wf.run_with_hitl_gate(
        None, {}, "issue_permit", payment, "dlq_enqueue_activity",
        gate_result={"needs_hitl": True, "requested_by": "someone@x"}, tenant_id="t", compliance=True))
    assert "issue_permit" in _labels(fake) and "record:hitl_timeout" not in _labels(fake)


def test_the_record_activity_answers_with_the_digest_of_what_it_recorded(monkeypatch):
    """The workflow waits for this value; the record and the portal carry the same one."""
    written = {}
    monkeypatch.setattr(c, "require_running", lambda *a, **k: None)
    monkeypatch.setattr(c, "record", lambda tenant, kind, payload, **k: written.update(payload) or 7)
    monkeypatch.setattr(c, "forward", lambda *a, **k: (0, ""))
    answer = asyncio.run(base_workflow.compliance_record_activity(
        {"tenant_id": "t", "workflow_id": "wf-1", "kind": "hitl_pending", "payload": {"input": {"to": "x"}}}))
    assert answer == {"record_id": 7, "input_sha256": c.payload_digest({"to": "x"})}
    assert written["input_sha256"] == answer["input_sha256"]


@pytest.mark.parametrize("missing", ["input_sha256", "record_id"])
def test_a_pending_record_without_its_id_or_digest_refuses_the_gate(monkeypatch, missing):
    """Nothing to compare a decision with: the gate fails closed rather than waiting for nothing."""
    fake, wf = _deciding(dict(DECISION))
    original = fake.execute_activity

    async def no_digest(name, payload, **k):
        answer = await original(name, payload, **k)
        if payload.get("kind") == "hitl_pending":
            answer.pop(missing)
        return answer

    fake.execute_activity = no_digest
    with pytest.raises(Exception, match="id or input digest"):
        _gate(fake, monkeypatch, wf)
    assert "issue_permit" not in _labels(fake)


@pytest.mark.parametrize("who", ["fatima", "EMP-1042", "  "])
def test_a_requester_who_is_not_a_sign_in_email_is_refused(monkeypatch, who):
    """R29: the portal compares the requester with the reviewer's sign-in email."""
    monkeypatch.setattr(base_workflow, "workflow", _Workflow())
    monkeypatch.setattr(base_workflow, "_HAS_TEMPORAL", True)
    with pytest.raises(Exception, match="sign-in email"):
        asyncio.run(BaseAgentWorkflow().run_with_hitl_gate(
            None, {}, "a", {}, "d", gate_result={"needs_hitl": True, "requested_by": who}, tenant_id="t",
            compliance=True))


def test_a_short_system_prompt_is_still_caught():
    """R19 (a): under eight words, the window loop never ran."""
    system = [{"role": "system", "content": "The admin password is hunter2 today"}]
    assert c.leaks_system_prompt(system, "Sure: the admin password is hunter2 today.")
    assert not c.leaks_system_prompt([{"role": "system", "content": "Be brief."}], "I will be brief.")


def test_an_unsigned_mark_does_not_verify_where_marks_are_signed(monkeypatch):
    """R19 (b): change the text, recompute the digest, drop the signature: it verified."""
    import hashlib

    monkeypatch.setenv(c.RECORD_KEY_ENV, "k")
    mark = c.ai_marking("the real answer", "m")
    forged = {k: v for k, v in mark.items() if k != "signature"}
    forged["content_sha256"] = hashlib.sha256(b"a forged answer").hexdigest()
    assert not c.verify_marking("a forged answer", forged)
    assert c.verify_marking("a forged answer", forged, require_signature=False)


def test_the_sidecar_reserves_every_kind_the_framework_writes():
    """R21: an app could write `retention_purge` through /v1/record."""
    from agentsmith import runtime_server

    assert runtime_server.RESERVED_KINDS == c.FRAMEWORK_KINDS
    assert {"retention_purge", "hitl_pending", "stop_control", "model_result"} <= c.FRAMEWORK_KINDS


class _Conn:
    """A connection that remembers what it was asked and whether it committed."""

    def __init__(self, count: int = 3) -> None:
        self.sql: list[str] = []
        self.committed: list[str] = []
        self.count = count

    def cursor(self):
        conn = self

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                conn.sql.append(" ".join(sql.split()))

            def fetchone(self):
                last = conn.sql[-1]
                if last.startswith("SELECT count"):
                    return (conn.count,)
                if last.startswith("SELECT record_hash"):
                    return None
                return (7,)

        return _Cursor()

    def commit(self):
        self.committed = list(self.sql)

    def rollback(self):
        pass

    def close(self):
        pass


def test_a_purge_that_cannot_be_recorded_deletes_nothing(profile, monkeypatch):
    """R13: the DELETE committed, then the record was refused."""
    conn = _Conn()
    monkeypatch.setattr(c, "_connect", lambda dsn=None: conn)
    monkeypatch.delenv(c.RECORD_KEY_ENV)
    with pytest.raises(c.ComplianceRefused):
        c.purge_runs("t", apply=True)
    assert not any(q.startswith("DELETE") for q in conn.committed)


def test_a_purge_and_its_record_commit_together(profile, monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(c, "_connect", lambda dsn=None: conn)
    assert c.purge_runs("t", apply=True) == 3
    assert any(q.startswith("DELETE FROM agent_runs") for q in conn.committed)
    assert any(q.startswith("INSERT INTO compliance_outbox") for q in conn.committed)  # the same commit


def test_a_stop_that_cannot_be_recorded_is_not_set(profile, monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(c, "_connect", lambda dsn=None: conn)
    monkeypatch.delenv(c.RECORD_KEY_ENV)
    with pytest.raises(c.ComplianceRefused):
        c.set_stop("t", "*", "why", "me@x")
    assert not any(q.startswith("INSERT INTO compliance_stop") for q in conn.committed)


def test_a_vector_write_never_takes_another_tenants_row(monkeypatch):
    """R25: the upsert keyed on id alone moved tenant A's row to tenant B."""
    from agentsmith import vector_store

    conn = _Conn()
    conn.cursor = lambda: _NoRow(conn)
    store = vector_store.PgVectorStore.__new__(vector_store.PgVectorStore)
    store.embedder = type("E", (), {"embed": staticmethod(lambda texts: [[0.0] for _ in texts])})()
    store._connect = lambda: conn
    monkeypatch.setattr(vector_store, "_scoped_tenant", lambda: "tenant-b")
    with pytest.raises(ValueError, match="another tenant"):
        store.add(["policy-1"], ["text"])
    assert "WHERE agentsmith_embeddings.tenant_id IS NOT DISTINCT FROM EXCLUDED.tenant_id" in conn.sql[-1]
    assert conn.committed == []


class _NoRow:
    """The upsert matched a row of another tenant: Postgres returns no row."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.sql.append(" ".join(sql.split()))

    def fetchone(self):
        return None


@pytest.mark.parametrize("answer, deleted", [(2, False), (1, False), (True, True)])
def test_purge_apply_asks_a_person_first(profile, monkeypatch, answer, deleted):
    """R13: `ops purge --apply` deleted with no confirmation, while `ops resume` asked."""
    import argparse

    from agentsmith import cli

    calls: list[bool] = []
    monkeypatch.setattr(c, "purge_runs", lambda tenant, apply=False: calls.append(apply) or 3)
    monkeypatch.setattr(cli, "_confirm_at_terminal", lambda verb, question, expected: answer)
    args = argparse.Namespace(verb="purge", apply=True, tenant="t", scope="*", reason=None, restored_url=None)
    code = cli._cmd_ops_compliance(args)
    assert (True in calls) is deleted
    assert code == (0 if deleted else answer)


@pytest.mark.parametrize("who", ["fatima", "EMP 1042@x"])
def test_the_sidecar_refuses_a_requester_that_is_not_an_email(sidecar, who):
    """R29, the sidecar's half: the portal compares the requester with a sign-in email."""
    ask = {"gate_id": "g", "workflow_id": "w", "action": "issue", "input": {}, "requested_by": who}
    reply = _call(sidecar, "/v1/gate/request", ask)
    assert reply.status_code == 400 and "sign-in email" in reply.text


# ── The 4.1.0 review's second pass: P2-R14, P2-R15 (.agent-rfc/designs/decision-names-its-request.md) ──


def test_a_decision_must_name_the_request_it_answers():
    """P2-R14: a decision said which input, not which request."""
    with pytest.raises(ValueError):
        c.HumanDecision.model_validate({k: v for k, v in DECISION.items() if k != "request_record_id"})
    assert c.HumanDecision.model_validate(DECISION).request_record_id == PENDING_RECORD


def test_on_the_temporal_path_a_decision_about_another_request_does_not_answer(monkeypatch):
    """P2-R14: the same input, asked twice; the decision names the first request."""
    fake, wf = _deciding({**DECISION, "request_record_id": PENDING_RECORD - 1})
    _gate(fake, monkeypatch, wf)
    assert "issue_permit" not in _labels(fake) and "record:hitl_timeout" in _labels(fake)


@needs_db
def test_on_the_store_path_a_late_decision_on_an_earlier_request_does_not_answer(sidecar, monkeypatch):
    """P2-R14: request 1 and request 2 show one input; a decision on request 1 recorded
    after request 2 was asked answered request 2."""
    monkeypatch.setenv("DATABASE_URL", DSN)
    gate = {"gate_id": f"late-{os.getpid()}", "workflow_id": f"wl-{os.getpid()}"}
    ask = {**gate, "action": "issue", "input": {"n": 7}, "requested_by": "a@x"}
    first = _call(sidecar, "/v1/gate/request", ask).json()["record_id"]
    second = _call(sidecar, "/v1/gate/request", ask).json()["record_id"]
    decided = {**gate, "approved": True, "actor": "b@x", "payload_sha256": c.payload_digest({"n": 7})}
    c.record("t", "hitl_decision", {**decided, "request_record_id": first})
    assert _call(sidecar, "/v1/gate/status", gate).json()["status"] == "pending"
    # The right request, the wrong input: not an answer either.
    c.record("t", "hitl_decision", {**decided, "payload_sha256": c.payload_digest({"n": 8}),
                                    "request_record_id": second})
    assert _call(sidecar, "/v1/gate/status", gate).json()["status"] == "pending"
    c.record("t", "hitl_decision", {**decided, "request_record_id": second})
    assert _call(sidecar, "/v1/gate/status", gate).json()["status"] == "approved"


class _DeleteFails(_Conn):
    """A connection whose `DELETE FROM compliance_stop` fails, as on a lost connection."""

    def cursor(self):
        cursor = super().cursor()
        execute = cursor.execute

        def failing(sql, params=None):
            if sql.lstrip().startswith("DELETE FROM compliance_stop"):
                raise RuntimeError("connection lost")
            execute(sql, params)

        cursor.execute = failing
        return cursor


def test_a_resume_that_fails_leaves_no_resume_record(profile, monkeypatch):
    """P2-R15: the record committed first, then the delete failed, and the chain said
    "resumed" for an app that was still stopped."""
    conn = _DeleteFails()
    monkeypatch.setattr(c, "_connect", lambda dsn=None: conn)
    with pytest.raises(c.ComplianceRefused):
        c.clear_stop("t", "*", "me@x")
    assert not any(q.startswith("INSERT INTO compliance_outbox") for q in conn.committed)


def test_a_resume_and_its_record_commit_together(profile, monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(c, "_connect", lambda dsn=None: conn)
    c.clear_stop("t", "*", "me@x")
    assert any(q.startswith("DELETE FROM compliance_stop") for q in conn.committed)
    assert any(q.startswith("INSERT INTO compliance_outbox") for q in conn.committed)


# ── The 4.1.0 review's second pass: P2-R16 (.agent-rfc/designs/declaration-ratchet-and-atomic-test.md) ──


def _sql(dsn: str, *statements: str) -> list:
    """Run statements in autocommit; the rows of the last."""
    import psycopg2

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
            return cur.fetchall() if cur.description else []
    finally:
        conn.close()


@pytest.fixture()
def isolated_dsn():
    """A schema of this test's own, so a trigger that refuses records touches nothing else.
    Unique per test: the gateway caches "tables created" by DSN, so a reused name would
    skip creating them in the fresh schema."""
    import uuid

    schema = f"p2r16_{uuid.uuid4().hex[:12]}"
    _sql(DSN, f"DROP SCHEMA IF EXISTS {schema} CASCADE", f"CREATE SCHEMA {schema}")
    separator = "&" if "?" in DSN else "?"
    yield f"{DSN}{separator}options=-csearch_path%3D{schema}"
    _sql(DSN, f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def _refuse_records(dsn: str, kind: str) -> None:
    c.record("t", "warm-up", {}, dsn=dsn)  # the outbox exists in this schema
    _sql(dsn,
         "CREATE FUNCTION refuse() RETURNS trigger AS $$ BEGIN "
         f"IF NEW.kind = '{kind}' THEN RAISE EXCEPTION 'refused'; END IF; RETURN NEW; END $$ LANGUAGE plpgsql",
         "CREATE TRIGGER refuse BEFORE INSERT ON compliance_outbox FOR EACH ROW EXECUTE FUNCTION refuse()")


@needs_db
def test_a_purge_whose_record_fails_in_the_database_deletes_nothing(profile, isolated_dsn):
    """P2-R16: with the record written after the delete committed, every test still passed."""
    _sql(isolated_dsn, "CREATE TABLE agent_runs (tenant_id TEXT, started_at TIMESTAMPTZ)",
         "INSERT INTO agent_runs VALUES ('t', now() - interval '2000 days')")
    _refuse_records(isolated_dsn, "retention_purge")
    with pytest.raises(c.ComplianceRefused):
        c.purge_runs("t", apply=True, dsn=isolated_dsn)
    assert _sql(isolated_dsn, "SELECT count(*) FROM agent_runs") == [(1,)]


@needs_db
def test_a_stop_or_resume_whose_record_fails_in_the_database_changes_nothing(profile, isolated_dsn):
    c.set_stop("t", c.APP_SCOPE, "held", "a@x", dsn=isolated_dsn)
    _refuse_records(isolated_dsn, "stop_control")
    with pytest.raises(c.ComplianceRefused):
        c.clear_stop("t", c.APP_SCOPE, "a@x", dsn=isolated_dsn)
    with pytest.raises(c.ComplianceRefused):
        c.set_stop("t", "wf-2", "also", "a@x", dsn=isolated_dsn)
    rows = _sql(isolated_dsn, "SELECT scope FROM compliance_stop WHERE tenant_id = 't' ORDER BY scope")
    assert rows == [(c.APP_SCOPE,)]  # still stopped, and the second stop never set
