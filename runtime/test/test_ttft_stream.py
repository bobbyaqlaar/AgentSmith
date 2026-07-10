from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_gateway import CompletionResult, LLMGateway  # noqa: E402


class _FakeStreamResp:
    def __init__(self, lines: list[str]) -> None:
        self.status_code = 200
        self._lines = lines

    async def __aenter__(self) -> "_FakeStreamResp":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


SSE = [
    'data: {"choices":[{"delta":{"content":"Hi"}}]}',
    'data: {"choices":[{"delta":{"content":"!"}}]}',
    "data: [DONE]",
]


@pytest.mark.asyncio
async def test_complete_stream_sets_ttft_ms() -> None:
    gw = LLMGateway.__new__(LLMGateway)
    gw.tenant_id = "t"
    gw.models = {
        "developer": {
            "id": "test-model",
            "provider": "ollama",
            "endpoint": "http://127.0.0.1:11434/v1",
        }
    }
    gw.budget_cap_usd = 10.0
    gw._idempotency = None
    gw.get_budget_status = MagicMock(return_value={"ok": True, "remaining_usd": 10})
    gw._resolve_role = MagicMock(return_value=("developer", None))
    gw._coerce_messages = MagicMock(return_value=[{"role": "user", "content": "hi"}])
    gw._record_span_attributes = MagicMock()
    gw._report_run_status = MagicMock()
    gw._degrade_chain = MagicMock(return_value=["developer"])
    gw._is_free_tier = MagicMock(return_value=True)

    fake = _FakeStreamResp(SSE)
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=fake)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await gw.complete_stream("hi", model_hint="developer")

    assert isinstance(result, CompletionResult)
    assert "Hi" in result.text
    assert result.ttft_ms is not None
    assert result.ttft_ms >= 0
