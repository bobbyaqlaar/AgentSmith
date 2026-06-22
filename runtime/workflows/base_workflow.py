"""
runtime/workflows/base_workflow.py — Reference Temporal workflow base class.

Demonstrates the durable-execution pattern described in SPECS.md §25:
  - Activities call runtime/llm_gateway.py (never cost_router.py)
  - HITL pause/resume via workflow signal, with a timeout that routes to the DLQ
  - All spans carry tenant.id, workflow.id, workflow.run_id

This is a PATTERN, not a deployable workflow. Tenant repos copy and adapt this
shape into their own workflow files — see examples/oil-price-agent/workflows/
for a concrete domain example built on top of it. Framework workflows are
never deployed directly as tenant production code (§25).

Requires: pip install temporalio
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

try:
    from temporalio import activity, workflow
    _HAS_TEMPORAL = True
except ImportError:
    _HAS_TEMPORAL = False

    class _Workflow:
        """No-op stand-in so this module is importable without temporalio installed."""
        def signal(self, fn=None, **_k):
            return fn if fn is not None else (lambda f: f)

    workflow = _Workflow()  # type: ignore
    activity = None  # type: ignore


HITL_SIGNAL_TIMEOUT = timedelta(hours=24)


@dataclass
class AgentWorkflowInput:
    tenant_id: str
    task: str
    spec: str
    workflow_run_id: str


@dataclass
class AgentWorkflowResult:
    status: str  # "success" | "failed" | "dead_letter"
    plan: str = ""
    code: str = ""
    validation: str = ""


class BaseAgentWorkflow:
    """
    Reference three-node pattern: Architect -> Developer -> Validator, with an
    optional HITL pause before a destructive/low-confidence step.

    Subclass and override `activities()` to bind domain-specific activity
    functions (e.g. IngestionActivity, PredictionActivity, DecisionActivity
    for the oil-price example) while keeping the HITL/DLQ control flow here.
    """

    def __init__(self) -> None:
        self._hitl_approved: Optional[bool] = None

    if _HAS_TEMPORAL:
        @workflow.signal
        def hitl_approved(self, approved: bool) -> None:
            """External signal fired by the Phoenix annotation -> Ops Portal bridge on HITL review."""
            self._hitl_approved = approved

    async def run_with_hitl_gate(
        self,
        gate_activity_name: str,
        gate_input: Any,
        resume_activity_name: str,
        resume_input: Any,
        dead_letter_activity_name: str,
    ) -> AgentWorkflowResult:
        """
        Run `gate_activity_name`; if it requests human review, wait on the
        `hitl_approved` signal up to HITL_SIGNAL_TIMEOUT. On timeout, route to
        the dead-letter activity instead of blocking the workflow forever.
        """
        if not _HAS_TEMPORAL:
            raise RuntimeError(
                "temporalio is not installed. Run: pip install temporalio. "
                "See SPECS.md §25 for the production runtime spec."
            )

        gate_result = await workflow.execute_activity(
            gate_activity_name,
            gate_input,
            start_to_close_timeout=timedelta(minutes=10),
        )

        if not gate_result.get("needs_hitl"):
            return await workflow.execute_activity(
                resume_activity_name,
                resume_input,
                start_to_close_timeout=timedelta(minutes=10),
            )

        try:
            await workflow.wait_condition(
                lambda: self._hitl_approved is not None,
                timeout=HITL_SIGNAL_TIMEOUT,
            )
        except TimeoutError:
            await workflow.execute_activity(
                dead_letter_activity_name,
                {**gate_input, "error": "hitl_timeout"},
                start_to_close_timeout=timedelta(minutes=5),
            )
            return AgentWorkflowResult(status="dead_letter")

        if not self._hitl_approved:
            return AgentWorkflowResult(status="failed")

        return await workflow.execute_activity(
            resume_activity_name,
            resume_input,
            start_to_close_timeout=timedelta(minutes=10),
        )
