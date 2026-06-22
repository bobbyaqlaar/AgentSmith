"""
examples/oil-price-agent/workflows/oil_price_workflow.py — Temporal reference
workflow for the oil price prediction pipeline.

Pipeline: IngestionAgent -> PredictionAgent -> DecisionAgent.

HITL triggers (see examples/oil-price-agent/agents/README.md):
  - Price anomaly > 3 standard deviations: pause workflow, alert ops team
  - Model confidence < 0.6: pause for human review before order

This demonstrates the pattern in runtime/workflows/base_workflow.py applied
to a concrete domain. It is a reference implementation: copy this directory
into your own tenant repository rather than deploying it from
AgenticFramework/examples (§28).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

try:
    from temporalio import workflow
    _HAS_TEMPORAL = True
except ImportError:
    _HAS_TEMPORAL = False

    class _Workflow:
        def defn(self, cls=None, **_k):
            return cls if cls is not None else (lambda c: c)

        def run(self, fn):
            return fn

        def signal(self, fn=None, **_k):
            return fn if fn is not None else (lambda f: f)

    workflow = _Workflow()  # type: ignore

HITL_SIGNAL_TIMEOUT = timedelta(hours=24)


@dataclass
class OilPriceWorkflowInput:
    tenant_id: str
    workflow_run_id: str
    price_series: list


@workflow.defn
class OilPricePredictionWorkflow:
    """
    Scheduled via `.agenticframework/schedules.yaml` (cron: "0 6 * * *", §25).
    Task queue: f"agent-tasks-{tenant_id}" (shared pool, partitioned by tenant.id).
    """

    def __init__(self) -> None:
        self._hitl_approved: Optional[bool] = None

    @workflow.signal
    def hitl_approved(self, approved: bool) -> None:
        """Fired by the Ops Portal when an operator resolves a HITL-flagged prediction."""
        self._hitl_approved = approved

    @workflow.run
    async def run(self, input: OilPriceWorkflowInput) -> dict:
        if not _HAS_TEMPORAL:
            raise RuntimeError(
                "temporalio is not installed. Run: pip install temporalio. "
                "See SPECS.md §25 for the production runtime spec."
            )

        ingestion = await workflow.execute_activity(
            "fetch_oil_price_activity",
            {"tenant_id": input.tenant_id, "price_series": input.price_series},
            start_to_close_timeout=timedelta(minutes=5),
        )

        prediction = await workflow.execute_activity(
            "run_prediction_activity",
            {**ingestion, "workflow_run_id": input.workflow_run_id},
            start_to_close_timeout=timedelta(minutes=10),
        )

        if not prediction.get("needs_hitl"):
            return await workflow.execute_activity(
                "decide_action_activity",
                prediction,
                start_to_close_timeout=timedelta(minutes=5),
            )

        try:
            await workflow.wait_condition(
                lambda: self._hitl_approved is not None,
                timeout=HITL_SIGNAL_TIMEOUT,
            )
        except TimeoutError:
            return await workflow.execute_activity(
                "dead_letter_activity",
                {**prediction, "error": "hitl_timeout"},
                start_to_close_timeout=timedelta(minutes=5),
            )

        if not self._hitl_approved:
            return {"status": "rejected", **prediction}

        return await workflow.execute_activity(
            "decide_action_activity",
            prediction,
            start_to_close_timeout=timedelta(minutes=5),
        )
