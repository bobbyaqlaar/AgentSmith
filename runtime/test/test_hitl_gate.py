"""
runtime/test/test_hitl_gate.py — regression tests for
BaseAgentWorkflow.run_with_hitl_gate.

These drive the method directly with a fake `workflow` module object rather
than a real Temporal test server, so they run everywhere — the Temporal-backed
tests in this directory (test_recoverable_step.py) skip without DATABASE_URL,
and a HITL bypass is not something to leave covered only by a suite that most
runs skip.

What they lock in: the gate must never run the resume activity — the
high-impact action — without either a `needs_hitl` decision that says it isn't
needed, or a recorded human approval. The bug that motivated this: KYC Sentinel
passed the Analyst activity as the gate activity when it had ALREADY run it, so
the gate re-executed a temperature=0.1 frontier call and honoured the second
run's needs_hitl. A re-run that came back unflagged approved the applicant with
no human in the loop at all.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from runtime.workflows import base_workflow
from runtime.workflows.base_workflow import AgentWorkflowResult, BaseAgentWorkflow


class _FakeWorkflowModule:
    """Stand-in for `temporalio.workflow` inside base_workflow's namespace."""

    def __init__(self, approve: bool | None = None, timeout: bool = False) -> None:
        self.executed: list[tuple[str, Any]] = []
        self._approve = approve
        self._timeout = timeout

    async def execute_activity(self, name, payload, **_kwargs):
        self.executed.append((name, payload))
        return {"ran": name}

    async def wait_condition(self, predicate, timeout=None):
        if self._timeout:
            raise TimeoutError("no signal within HITL_SIGNAL_TIMEOUT")
        return predicate()

    def info(self):
        class _Info:
            workflow_id = "wf-test-1"

        return _Info()

    @staticmethod
    def signal(fn=None, **_kwargs):
        return fn if fn is not None else (lambda f: f)


@pytest.fixture()
def fake_workflow(monkeypatch):
    def _install(**kwargs) -> _FakeWorkflowModule:
        fake = _FakeWorkflowModule(**kwargs)
        monkeypatch.setattr(base_workflow, "workflow", fake)
        monkeypatch.setattr(base_workflow, "_HAS_TEMPORAL", True)
        return fake

    return _install


def _gate(wf: BaseAgentWorkflow, **overrides):
    kwargs: dict[str, Any] = {
        "gate_activity_name": None,
        "gate_input": {"profile": "p"},
        "resume_activity_name": "approve_activity",
        "resume_input": {"assessment": "HIGH"},
        "dead_letter_activity_name": "dlq_enqueue_activity",
        "gate_result": {"needs_hitl": True},
    }
    kwargs.update(overrides)
    positional = (
        kwargs.pop("gate_activity_name"),
        kwargs.pop("gate_input"),
        kwargs.pop("resume_activity_name"),
        kwargs.pop("resume_input"),
        kwargs.pop("dead_letter_activity_name"),
    )
    return asyncio.run(wf.run_with_hitl_gate(*positional, **kwargs))


def test_supplied_gate_result_does_not_re_run_any_gate_activity(fake_workflow):
    """The whole point: a caller that already has needs_hitl pays for no
    second execution, so no second execution can disagree with the first."""
    fake = fake_workflow()
    wf = BaseAgentWorkflow()
    wf._hitl_approved = True

    _gate(wf, gate_result={"needs_hitl": True})

    assert [name for name, _ in fake.executed] == ["approve_activity"]


def test_high_risk_gate_result_waits_for_approval_before_resuming(fake_workflow):
    fake = fake_workflow()
    wf = BaseAgentWorkflow()
    wf._hitl_approved = True

    result = _gate(wf, gate_result={"needs_hitl": True})

    assert result == {"ran": "approve_activity"}
    assert fake.executed == [("approve_activity", {"assessment": "HIGH"})]


def test_rejection_never_runs_the_high_impact_action(fake_workflow):
    fake = fake_workflow()
    wf = BaseAgentWorkflow()
    wf._hitl_approved = False

    result = _gate(wf, gate_result={"needs_hitl": True})

    assert result == AgentWorkflowResult(status="failed")
    assert fake.executed == []


def test_gate_result_without_hitl_resumes_directly(fake_workflow):
    fake = fake_workflow()
    wf = BaseAgentWorkflow()

    result = _gate(wf, gate_result={"needs_hitl": False})

    assert result == {"ran": "approve_activity"}
    assert fake.executed == [("approve_activity", {"assessment": "HIGH"})]


def test_gate_activity_name_still_runs_the_gate(fake_workflow):
    """Backward compatibility: the original shape keeps working for callers
    whose gate really is a separate, not-yet-run check."""
    fake = fake_workflow()
    wf = BaseAgentWorkflow()

    result = _gate(wf, gate_activity_name="check_activity", gate_result=None)

    # {"ran": ...} has no needs_hitl, so the gate resumes without pausing.
    assert result == {"ran": "approve_activity"}
    assert [name for name, _ in fake.executed] == ["check_activity", "approve_activity"]


def test_rejects_both_gate_activity_and_gate_result(fake_workflow):
    fake_workflow()
    wf = BaseAgentWorkflow()

    with pytest.raises(ValueError, match="both"):
        _gate(wf, gate_activity_name="check_activity", gate_result={"needs_hitl": True})


def test_rejects_neither_gate_activity_nor_gate_result(fake_workflow):
    fake_workflow()
    wf = BaseAgentWorkflow()

    with pytest.raises(ValueError, match="neither"):
        _gate(wf, gate_activity_name=None, gate_result=None)


def test_timeout_with_tenant_id_emits_the_generic_dlq_envelope(fake_workflow):
    """dlq_enqueue_activity reads payload/error/tenant_id off its input; the
    legacy flattened shape carries none of them and raised KeyError, losing
    the very application the timeout path exists to park."""
    fake = fake_workflow(timeout=True)
    wf = BaseAgentWorkflow()

    result = _gate(wf, gate_result={"needs_hitl": True}, tenant_id="acme", gate_id="g1")

    assert result == AgentWorkflowResult(status="dead_letter")
    name, payload = fake.executed[0]
    assert name == "dlq_enqueue_activity"
    assert payload["payload"] == {"profile": "p"}
    assert payload["error"] == "hitl_timeout"
    assert payload["tenant_id"] == "acme"
    assert payload["gate_id"] == "g1"


def test_timeout_without_tenant_id_keeps_the_legacy_flattened_shape(fake_workflow):
    """examples/oil-price-agent's own dead_letter_activity expects the
    payload's fields inline — that contract must not change under it."""
    fake = fake_workflow(timeout=True)
    wf = BaseAgentWorkflow()

    _gate(wf, gate_result={"needs_hitl": True})

    assert fake.executed[0] == (
        "dlq_enqueue_activity",
        {"profile": "p", "error": "hitl_timeout"},
    )

# The dead-letter envelope's own contract moved to test_dead_letter.py: it is
# SEC-DLQ-001's evidence, and a control cannot be proven by another control's
# suite. What stays here is the HITL gate's use of it — which envelope shape a
# timeout emits — because that is the gate's behaviour, not the DLQ's.
