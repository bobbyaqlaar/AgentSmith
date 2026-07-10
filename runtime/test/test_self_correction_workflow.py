from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "workflows"))

import base_workflow as bw  # type: ignore  # noqa: E402
from base_workflow import BaseAgentWorkflow  # type: ignore  # noqa: E402


class FakeWorkflow:
    def __init__(self, *, corrected_payload: dict[str, Any]) -> None:
        self.corrected_payload = corrected_payload
        self.calls: list[tuple[Any, Any]] = []

    async def execute_activity(self, activity: Any, payload: Any, **_kwargs: Any) -> Any:
        self.calls.append((activity, payload))
        if activity == "crm_update_activity":
            if "status" not in payload:
                raise ValueError("account_status is not a valid property")
            return {"ok": True, "applied": payload}
        return self.corrected_payload


@pytest.mark.asyncio
async def test_run_with_self_correction_retries_corrected_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_workflow = FakeWorkflow(
        corrected_payload={"customer_id": 102, "status": "active"}
    )
    monkeypatch.setattr(bw, "_HAS_TEMPORAL", True)
    monkeypatch.setattr(bw, "RetryPolicy", lambda maximum_attempts: maximum_attempts)
    monkeypatch.setattr(bw, "workflow", fake_workflow)

    result = await BaseAgentWorkflow().run_with_self_correction(
        "crm_update_activity",
        {"customer_id": 102, "account_status": "active"},
        tenant_id="acme",
        gate_id="crm-update-gate",
    )

    assert result == {"ok": True, "applied": {"customer_id": 102, "status": "active"}}
    assert [call[0] for call in fake_workflow.calls] == [
        "crm_update_activity",
        bw.self_correct_payload_activity,
        "crm_update_activity",
    ]


@pytest.mark.asyncio
async def test_run_with_self_correction_falls_back_to_recoverable_step_with_last_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_workflow = FakeWorkflow(
        corrected_payload={"customer_id": 102, "account_status": "active"}
    )

    async def execute_activity(activity: Any, payload: Any, **_kwargs: Any) -> Any:
        fake_workflow.calls.append((activity, payload))
        if activity == "crm_update_activity":
            raise ValueError("account_status is not a valid property")
        return fake_workflow.corrected_payload

    fake_workflow.execute_activity = execute_activity  # type: ignore[method-assign]
    monkeypatch.setattr(bw, "_HAS_TEMPORAL", True)
    monkeypatch.setattr(bw, "RetryPolicy", lambda maximum_attempts: maximum_attempts)
    monkeypatch.setattr(bw, "workflow", fake_workflow)

    workflow = BaseAgentWorkflow()
    fallback_calls: list[dict[str, Any]] = []

    async def fallback(**kwargs: Any) -> dict[str, Any]:
        fallback_calls.append(kwargs)
        return {"status": "dead_letter"}

    workflow.run_with_recoverable_step = fallback  # type: ignore[method-assign]

    result = await workflow.run_with_self_correction(
        "crm_update_activity",
        {"customer_id": 102, "account_status": "active"},
        tenant_id="acme",
        gate_id="crm-update-gate",
        max_self_correction_attempts=1,
    )

    assert result == {"status": "dead_letter"}
    assert fallback_calls == [
        {
            "activity_name": "crm_update_activity",
            "payload": {"customer_id": 102, "account_status": "active"},
            "tenant_id": "acme",
            "gate_id": "crm-update-gate",
            "reason": "validation_error",
            "timeout": bw.HITL_SIGNAL_TIMEOUT,
            "max_attempts": bw.RECOVERABLE_STEP_MAX_ATTEMPTS,
        }
    ]
