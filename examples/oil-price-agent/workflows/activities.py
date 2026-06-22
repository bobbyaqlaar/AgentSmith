"""
examples/oil-price-agent/workflows/activities.py — Domain activities for the
oil price prediction workflow.

Pipeline: IngestionAgent -> PredictionAgent -> DecisionAgent (see
examples/oil-price-agent/agents/README.md).

All LLM calls route through runtime/llm_gateway.py — never cost_router.py
(§25, §29). This file is a reference; tenant repos vendor or pip-install the
framework's runtime/ package rather than reaching into a sibling checkout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from temporalio import activity
except ImportError:
    class _NoopActivity:
        def defn(self, fn=None, **_k):
            return fn if fn is not None else (lambda f: f)
    activity = _NoopActivity()  # type: ignore


def _ensure_runtime_on_path() -> None:
    here = Path(__file__).resolve()
    for candidate in (here.parents[3] / "runtime", Path.home() / ".agent-framework" / "runtime"):
        if not candidate.is_dir():
            continue
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))          # bare imports, e.g. `from dead_letter import ...`
        if str(candidate.parent) not in sys.path:
            sys.path.insert(0, str(candidate.parent))    # package imports, e.g. `import runtime.llm_gateway`
        return


_ensure_runtime_on_path()


# ── HITL thresholds (examples/oil-price-agent/agents/README.md) ──────────────

ANOMALY_STD_DEV_THRESHOLD = 3.0
CONFIDENCE_HITL_THRESHOLD = 0.6


@activity.defn
async def fetch_oil_price_activity(payload: dict) -> dict:
    """IngestionAgent: fetch latest price data. Stub data source for the reference example."""
    # TODO (tenant implementation): replace with a real price feed API call.
    return {"price_series": payload.get("price_series", []), "tenant_id": payload["tenant_id"]}


@activity.defn
async def run_prediction_activity(payload: dict) -> dict:
    """
    PredictionAgent: forecast next price point. Flags for HITL review when the
    observed price deviates more than ANOMALY_STD_DEV_THRESHOLD standard
    deviations from the trailing series, or when model confidence is low.
    """
    from llm_gateway import LLMGateway  # type: ignore

    series = payload.get("price_series", [])
    tenant_id = payload["tenant_id"]

    mean = sum(series) / len(series) if series else 0.0
    variance = sum((p - mean) ** 2 for p in series) / len(series) if series else 0.0
    std_dev = variance ** 0.5
    latest = series[-1] if series else 0.0
    is_anomaly = std_dev > 0 and abs(latest - mean) > ANOMALY_STD_DEV_THRESHOLD * std_dev

    gateway = LLMGateway(tenant_id=tenant_id)
    result = await gateway.complete(
        prompt=f"Given recent oil prices {series}, predict the next price point and a "
               f"confidence score (0-1) as JSON: {{\"prediction\": <float>, \"confidence\": <float>}}.",
        model_hint="validator",  # cheap/fast tier for a bounded forecasting prompt
        workflow_id=payload.get("workflow_run_id"),
    )

    try:
        parsed = json.loads(result.text)
        prediction = float(parsed["prediction"])
        confidence = float(parsed["confidence"])
    except Exception:
        prediction, confidence = latest, 0.0

    needs_hitl = is_anomaly or confidence < CONFIDENCE_HITL_THRESHOLD
    return {
        "tenant_id": tenant_id,
        "prediction": prediction,
        "confidence": confidence,
        "is_anomaly": is_anomaly,
        "needs_hitl": needs_hitl,
        "cost_usd": result.cost_usd,
    }


@activity.defn
async def decide_action_activity(payload: dict) -> dict:
    """DecisionAgent: act on an approved (or non-flagged) prediction."""
    # TODO (tenant implementation): place the order / fire the alert.
    return {
        "status": "success",
        "prediction": payload.get("prediction"),
        "confidence": payload.get("confidence"),
    }


@activity.defn
async def dead_letter_activity(payload: dict) -> dict:
    """Routed to when the HITL signal times out (24h) — see base_workflow.py."""
    from dead_letter import DeadLetterQueue  # type: ignore

    dlq = DeadLetterQueue()
    try:
        dlq.enqueue(payload=payload, error=payload.get("error", "unknown"), tenant_id=payload["tenant_id"])
    except NotImplementedError:
        pass  # DLQ store not yet provisioned — surfaced via Ops Portal once it is
    return {"status": "dead_letter"}
