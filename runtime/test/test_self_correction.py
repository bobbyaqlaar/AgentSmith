from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime.self_correction import propose_corrected_payload, run_self_correction_loop  # type: ignore  # noqa: E402


class FakeCompletion:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeGateway:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[Any] = []

    async def complete(self, *, prompt: Any, model_hint: str) -> FakeCompletion:
        self.prompts.append({"prompt": prompt, "model_hint": model_hint})
        return FakeCompletion(self.text)


@pytest.mark.asyncio
async def test_propose_corrected_payload_parses_json_from_fenced_response() -> None:
    gateway = FakeGateway(
        '```json\n{"customer_id": 102, "status": "active"}\n```'
    )

    result = await propose_corrected_payload(
        gateway,
        {"customer_id": 102, "account_status": "active"},
        "account_status is not a valid property",
    )

    assert result == {"customer_id": 102, "status": "active"}
    assert gateway.prompts[0]["model_hint"] == "developer"


@pytest.mark.asyncio
async def test_run_self_correction_loop_succeeds_after_one_correction() -> None:
    gateway = FakeGateway('{"customer_id": 102, "status": "active"}')
    attempts: list[dict[str, Any]] = []

    async def activity_fn(payload: dict[str, Any]) -> dict[str, Any]:
        attempts.append(payload)
        if "status" not in payload:
            raise ValueError("account_status is not a valid property")
        return {"ok": True, "applied": payload}

    result = await run_self_correction_loop(
        activity_fn=activity_fn,
        payload={"customer_id": 102, "account_status": "active"},
        gateway=gateway,
    )

    assert result == {"ok": True, "applied": {"customer_id": 102, "status": "active"}}
    assert attempts == [
        {"customer_id": 102, "account_status": "active"},
        {"customer_id": 102, "status": "active"},
    ]


@pytest.mark.asyncio
async def test_run_self_correction_loop_returns_sentinel_when_exhausted() -> None:
    gateway = FakeGateway('{"customer_id": 102, "account_status": "active"}')

    async def activity_fn(payload: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("account_status is not a valid property")

    result = await run_self_correction_loop(
        activity_fn=activity_fn,
        payload={"customer_id": 102, "account_status": "active"},
        gateway=gateway,
        max_self_correction_attempts=1,
    )

    assert result == {
        "__self_correction_exhausted__": True,
        "payload": {"customer_id": 102, "account_status": "active"},
        "error": "account_status is not a valid property",
    }
