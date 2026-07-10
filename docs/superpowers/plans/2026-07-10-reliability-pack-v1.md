# Reliability Pack v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship thin v1 of hallucination-rate hard gate, TTFT streaming + `ttft_ms` (mock CI + optional live Ollama), and opt-in `run_with_self_correction` before DLQ.

**Architecture:** Three independent slices. (1) Eval judge gains a `hallucination` dimension; `run-evals.py --suite hallucination` computes flag rate and hard-fails above `HALLUCINATION_FAIL_ABOVE`. (2) `LLMGateway.complete_stream()` adds OpenAI-compatible SSE streaming and records `ttft_ms` on first content delta. (3) `BaseAgentWorkflow.run_with_self_correction` retries via a Temporal activity that calls the gateway, then falls through to existing `run_with_recoverable_step` — never mutates that method.

**Tech Stack:** Python 3.11+, pytest, httpx SSE, Temporal activities, GitHub Actions reusable workflows, existing `scripts/eval_judge.py` / `run-evals.py` patterns.

**Spec:** [`docs/superpowers/specs/2026-07-10-reliability-pack-v1-design.md`](../specs/2026-07-10-reliability-pack-v1-design.md)

**Note:** Tasks 1–4 (hallucination), 5–8 (TTFT), 9–11 (self-correction) are independently shippable. Prefer one commit per task.

---

## File map

| Path | Role |
|---|---|
| `scripts/eval_judge.py` | Add `include_hallucination` to prompt schema |
| `scripts/run-evals.py` | Suite `hallucination`, rate gate, CLI/env |
| `scripts/test/test_hallucination_evals.py` | Rate math + dotenv threshold |
| `fixtures/hallucination_evals_base.json` | Seed cases |
| `fixtures/hallucination_judge_criteria_base.json` | Rubric with `score_hallucination` |
| `workflow-templates/eval-hallucination.yml` | Hard-fail CI job |
| `workflow-templates/ci-*.yml` | Wire hallucination + TTFT jobs |
| `runtime/llm_gateway.py` | `CompletionResult.ttft_ms`; `complete_stream` |
| `runtime/provider_dispatch.py` | Optional helpers for stream URL/body (keep thin) |
| `runtime/test/test_ttft_stream.py` | Mock httpx stream → assert `ttft_ms` |
| `scripts/verify_ttft.py` | Live Ollama TTFT smoke |
| `workflow-templates/eval-ttft-live.yml` | Gated by `TTFT_LIVE=required` |
| `runtime/workflows/base_workflow.py` | `run_with_self_correction` + correct activity |
| `runtime/test/test_self_correction.py` | Unit tests with mocks |
| `portal/.env.example`, `templates/uae-sovereign/env.example` | Document env keys |
| `FIXES_AND_CLEANUP.md`, `README.md`, `SPECS.md` | Mark shipped |

---

### Task 1: Hallucination judge prompt + rate helpers

**Files:**
- Modify: `scripts/eval_judge.py`
- Create: `scripts/test/test_hallucination_evals.py`
- Create: `fixtures/hallucination_judge_criteria_base.json`
- Create: `fixtures/hallucination_evals_base.json`

- [ ] **Step 1: Write failing tests for rate math and prompt schema**

```python
# scripts/test/test_hallucination_evals.py
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]


def _load_run_evals():
    spec = importlib.util.spec_from_file_location("run_evals", SCRIPTS / "run-evals.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_hallucination_flag_rate_empty():
    revals = _load_run_evals()
    assert revals.hallucination_flag_rate([]) == 0.0


def test_hallucination_flag_rate_threshold():
    revals = _load_run_evals()
    rows = [
        {"hallucination": 0.0},
        {"hallucination": 0.6},  # flagged (>= 0.5)
        {"hallucination": 0.4},
        {"score": 1.0},  # no hallucination key — skip
    ]
    # 1 flagged / 3 scored = ~0.333
    assert abs(revals.hallucination_flag_rate(rows) - (1 / 3)) < 1e-9


def test_resolve_hallucination_fail_above_cli_wins(monkeypatch: pytest.MonkeyPatch):
    revals = _load_run_evals()
    monkeypatch.setenv("HALLUCINATION_FAIL_ABOVE", "0.10")
    assert revals._resolve_hallucination_fail_above(0.02) == 0.02


def test_resolve_hallucination_fail_above_env(monkeypatch: pytest.MonkeyPatch):
    revals = _load_run_evals()
    monkeypatch.setenv("HALLUCINATION_FAIL_ABOVE", "0.08")
    assert revals._resolve_hallucination_fail_above(None) == 0.08


def test_resolve_hallucination_fail_above_default(monkeypatch: pytest.MonkeyPatch):
    revals = _load_run_evals()
    monkeypatch.delenv("HALLUCINATION_FAIL_ABOVE", raising=False)
    assert revals._resolve_hallucination_fail_above(None) == 0.05


def test_judge_prompt_includes_hallucination_field():
    from eval_judge import judge_prompt

    p = judge_prompt(
        instructions="x",
        historical_text="(none)",
        input_text="q",
        expected_tool="any",
        reference_output="r",
        actual_output="a",
        include_hallucination=True,
    )
    assert '"hallucination"' in p
    assert "not supported by the input" in p.lower() or "unsupported" in p.lower()
```

- [ ] **Step 2: Run tests — expect fail**

Run: `cd /Users/mac/Documents/Bobby/Aqlaar/Apps/AgenticFramework && python3 -m pytest scripts/test/test_hallucination_evals.py -v`  
Expected: FAIL (`hallucination_flag_rate` / `include_hallucination` missing)

- [ ] **Step 3: Extend `judge_prompt` / `judge_case`**

In `scripts/eval_judge.py`, add `include_hallucination: bool = False` to `judge_prompt`. When True, extend JSON schema with `"hallucination": 0.0..1.0` and rubric text: score how much the actual output states claims not supported by INPUT/REFERENCE (0=none, 1=severe); distinct from correctness.

In `judge_case`, set:
```python
include_hallucination = bool(
    criteria.get("score_hallucination") or case.get("score_hallucination")
)
```
and pass through to `judge_prompt`. Keep existing `include_fairness` logic.

- [ ] **Step 4: Add fixtures**

`fixtures/hallucination_judge_criteria_base.json`:
```json
{
  "name": "AgentSmith_Hallucination_Scorecard",
  "score_hallucination": true,
  "instructions": "You audit agent outputs for unsupported claims (hallucinations). Score hallucination 0.0–1.0: 0 = every claim is supported by INPUT/REFERENCE; 1 = severe invented facts. correctness = was the task answered usefully; tool_accuracy = expected tool path. Do not conflate a wrong-but-grounded answer (low correctness, low hallucination) with an invented claim (high hallucination).",
  "historical_learnings": []
}
```

`fixtures/hallucination_evals_base.json` — at least 4 cases with `input`, `reference_output`, `expected_tool`, and for offline unit tests of rate only we do not need live judge; for CI live judge, include `project_response` or rely on runner generating output. Prefer cases that embed `actual` via a field the runner already supports — check `run-evals.py` for how golden cases supply agent output. If golden uses live agent, for hallucination suite allow optional `actual_output` on the case so CI can score without a full agent run:

```json
[
  {
    "id": "halluc-grounded-ok",
    "input": "What is the capital of the UAE? Context: Abu Dhabi is the capital.",
    "reference_output": "Abu Dhabi",
    "expected_tool": "none",
    "actual_output": "Abu Dhabi is the capital.",
    "score_hallucination": true
  },
  {
    "id": "halluc-invented-fact",
    "input": "What is the capital of the UAE? Context: Abu Dhabi is the capital.",
    "reference_output": "Abu Dhabi",
    "expected_tool": "none",
    "actual_output": "Dubai is the capital and has 40 million residents.",
    "score_hallucination": true
  }
]
```
(Add 2+ more grounded cases so a single false-positive flag stays under 5% only if judge is perfect — for CI with live judge, document that fixture set is small and threshold is on rate; with 2 cases one flag = 50% fail which is intentional for the invented case. Prefer **≥20 grounded + 0–1 invented** OR compute rate only and use mocked judge in unit tests; live CI may use `--suite hallucination` with mocked scores in unit tests and live job optional. **v1 decision:** unit tests cover rate math; live workflow runs suite when `ANTHROPIC_API_KEY` present; fixture set = 1 invented + 19 short grounded stubs so one true flag ≈ 5% boundary. Simpler v1: **5 grounded + 0 invented** for green CI baseline, plus 1 invented in a separate file used only by unit tests of flagging — OR hard-fail workflow uses synthetic results JSON. Simplest ship: rate gate in `run-evals.py`; CI job runs suite; fixtures = 4 grounded cases expected rate 0; document invented case in unit test with synthetic rows only.)

Final fixture choice for Task 1: **4 grounded cases** in `hallucination_evals_base.json` (expect rate ≈ 0). Invented-case behavior covered by synthetic `hallucination_flag_rate` unit tests only.

- [ ] **Step 5: Run tests — still fail on missing `run-evals` helpers**

Run: `python3 -m pytest scripts/test/test_hallucination_evals.py -v`  
Expected: prompt test PASS; rate helper tests FAIL until Task 2

- [ ] **Step 6: Commit**

```bash
git add scripts/eval_judge.py scripts/test/test_hallucination_evals.py \
  fixtures/hallucination_evals_base.json fixtures/hallucination_judge_criteria_base.json
git commit -m "$(cat <<'EOF'
feat: add hallucination judge dimension and seed fixtures

EOF
)"
```

---

### Task 2: `run-evals.py` hallucination suite + hard gate

**Files:**
- Modify: `scripts/run-evals.py`
- Modify: `scripts/test/test_hallucination_evals.py` (if needed)

- [ ] **Step 1: Implement helpers in `run-evals.py`**

```python
def hallucination_flag_rate(rows: list[dict], flag_at: float = 0.5) -> float:
    scored = [r for r in rows if isinstance(r.get("hallucination"), (int, float))]
    if not scored:
        return 0.0
    flagged = sum(1 for r in scored if float(r["hallucination"]) >= flag_at)
    return flagged / len(scored)


def _resolve_hallucination_fail_above(cli_value: float | None) -> float:
    if cli_value is not None:
        return cli_value
    raw = os.environ.get("HALLUCINATION_FAIL_ABOVE", "0.05").strip() or "0.05"
    return float(raw)
```

- [ ] **Step 2: Wire suite paths**

Extend `_evals_path`, `_criteria_path_for`, `_results_path`, `_load_cases` for `suite == "hallucination"` → `hallucination_evals.json` / `hallucination_judge_criteria.json` with fallback to `fixtures/hallucination_*_base.json` (same pattern as fairness).

In `run_scorecard`, after collecting per-case scores, if suite is hallucination (or any row has hallucination):
- compute `rate = hallucination_flag_rate(results)`
- print rate
- if `rate > _resolve_hallucination_fail_above(...)`: set failed even if avg score passes
- write rate into results JSON as `"hallucination_flag_rate"`

When judging, pass criteria with `score_hallucination: true`. If case has `actual_output`, pass it to `judge_case(..., project_response=case["actual_output"])` so suite works without a live agent.

- [ ] **Step 3: CLI**

```python
parser.add_argument(
    "--suite",
    choices=("golden", "fairness", "hallucination"),
    ...
)
parser.add_argument(
    "--hallucination-fail-above",
    type=float,
    default=None,
    help="Fail if hallucination flag rate exceeds this (default HALLUCINATION_FAIL_ABOVE or 0.05)",
)
```

In `__main__`:
```python
halluc_limit = _resolve_hallucination_fail_above(args.hallucination_fail_above)
sys.exit(run_scorecard(..., suite=args.suite, hallucination_fail_above=halluc_limit))
```

- [ ] **Step 4: Run unit tests**

Run: `python3 -m pytest scripts/test/test_hallucination_evals.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/run-evals.py scripts/test/test_hallucination_evals.py
git commit -m "$(cat <<'EOF'
feat: hard-fail hallucination flag rate via HALLUCINATION_FAIL_ABOVE

EOF
)"
```

---

### Task 3: Hallucination CI workflow (hard-fail)

**Files:**
- Create: `workflow-templates/eval-hallucination.yml`
- Modify: `workflow-templates/ci-python-fastapi.yml`, `ci-ts-react.yml`, `ci-go.yml` (same pattern as `eval-fairness`)

- [ ] **Step 1: Add reusable workflow**

Copy structure from `eval-fairness.yml` but:
- Always hard-fail (`continue-on-error: false`)
- Detect `hallucination_evals.json` or `fixtures/hallucination_evals_base.json`
- Env: `HALLUCINATION_FAIL_ABOVE: ${{ vars.HALLUCINATION_FAIL_ABOVE || '0.05' }}`
- Run: `python3 scripts/run-evals.py --suite hallucination`
- Upload `hallucination_eval_results.json`

- [ ] **Step 2: Wire into CI templates**

```yaml
  eval-hallucination:
    needs: [unit]   # match fairness needs graph in each file
    uses: ./.github/workflows/eval-hallucination.yml
```

(Exact `needs:` must match each CI file’s existing job ids — copy the fairness job’s `needs`.)

- [ ] **Step 3: Commit**

```bash
git add workflow-templates/eval-hallucination.yml workflow-templates/ci-*.yml
git commit -m "$(cat <<'EOF'
ci: add hard-fail hallucination eval workflow

EOF
)"
```

---

### Task 4: Document hallucination env keys

**Files:**
- Modify: `portal/.env.example` (comment block for eval gates)
- Modify: `templates/uae-sovereign/env.example`
- Modify: `FIXES_AND_CLEANUP.md` (Reliability hallucination section → Shipped v1)
- Modify: `README.md` reliability bullet (brief)

- [ ] **Step 1: Add env docs**

```bash
# Eval gates (framework root .env and/or tenant .env)
HALLUCINATION_FAIL_ABOVE=0.05
```

- [ ] **Step 2: Update FIXES status to Shipped (v1)** with pointer to suite + env key

- [ ] **Step 3: Commit**

```bash
git add portal/.env.example templates/uae-sovereign/env.example FIXES_AND_CLEANUP.md README.md
git commit -m "$(cat <<'EOF'
docs: document HALLUCINATION_FAIL_ABOVE and mark metric shipped

EOF
)"
```

---

### Task 5: TTFT — `CompletionResult.ttft_ms` + `complete_stream` (failing test first)

**Files:**
- Create: `runtime/test/test_ttft_stream.py`
- Modify: `runtime/llm_gateway.py`

- [ ] **Step 1: Write failing test with mocked httpx stream**

```python
# runtime/test/test_ttft_stream.py
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_gateway import CompletionResult, LLMGateway


class _FakeStreamResp:
    def __init__(self, lines: list[bytes]):
        self.status_code = 200
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line.decode() if isinstance(line, bytes) else line


SSE = [
    b'data: {"choices":[{"delta":{"content":"Hi"}}]}',
    b'data: {"choices":[{"delta":{"content":"!"}}]}',
    b"data: [DONE]",
]


@pytest.mark.asyncio
async def test_complete_stream_sets_ttft_ms():
    gw = LLMGateway.__new__(LLMGateway)
    gw.tenant_id = "t"
    gw.models = {
        "developer": {
            "id": "test-model",
            "provider": "ollama",
            "endpoint": "http://127.0.0.1:11434/v1",
        }
    }
    gw._idempotency = None
    gw.get_budget_status = MagicMock(return_value={"ok": True, "remaining_usd": 10})
    gw._resolve_role = MagicMock(return_value=("developer", None))
    gw._coerce_messages = MagicMock(return_value=[{"role": "user", "content": "hi"}])
    gw._record_span_attributes = MagicMock()
    gw._record_cost = MagicMock()

    fake = _FakeStreamResp(SSE)
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=fake)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await gw.complete_stream("hi", model_hint="developer")

    assert isinstance(result, CompletionResult)
    assert result.text.startswith("Hi")
    assert result.ttft_ms is not None
    assert result.ttft_ms >= 0
```

- [ ] **Step 2: Run test — expect fail**

Run: `cd /Users/mac/Documents/Bobby/Aqlaar/Apps/AgenticFramework && python3 -m pytest runtime/test/test_ttft_stream.py -v`  
Expected: FAIL (`complete_stream` / `ttft_ms` missing)

- [ ] **Step 3: Implement**

1. Add `ttft_ms: Optional[float] = None` to `CompletionResult`.
2. Add `async def complete_stream(self, prompt, model_hint="developer", ..., **kwargs) -> CompletionResult`:
   - Same budget/role/guardrail preamble as `complete` (extract shared `_prepare_completion` if small refactor stays safe; else duplicate minimally).
   - Only support non-cloud OpenAI-compatible providers in v1 (`openai`, `ollama`, `groq`); raise `NotImplementedError` for anthropic/cloud with clear message.
   - POST `{base}/chat/completions` with `"stream": true`.
   - `t0 = time.perf_counter()`; on first non-empty `delta.content`, set `ttft_ms = (time.perf_counter() - t0) * 1000`.
   - Accumulate text; parse final usage if present in stream (else 0 tokens).
   - Call `_record_span_attributes` including `ttft_ms` when set.
   - Return `CompletionResult(..., ttft_ms=ttft_ms)`.

3. Non-stream `complete()` unchanged (`ttft_ms` stays `None`).

- [ ] **Step 4: Run test — expect pass**

Run: `python3 -m pytest runtime/test/test_ttft_stream.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add runtime/llm_gateway.py runtime/test/test_ttft_stream.py
git commit -m "$(cat <<'EOF'
feat: add complete_stream with ttft_ms for OpenAI-compatible providers

EOF
)"
```

---

### Task 6: Live TTFT verify script + optional CI job

**Files:**
- Create: `scripts/verify_ttft.py`
- Create: `workflow-templates/eval-ttft-live.yml`
- Modify: `workflow-templates/ci-python-fastapi.yml` (and siblings) — call only when appropriate

- [ ] **Step 1: `scripts/verify_ttft.py`**

Load dotenv; read `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`), `TTFT_FAIL_ABOVE_MS` (default `2000`), model `falcon3:1b`.

Build a minimal `LLMGateway` or raw httpx stream to Ollama `/v1/chat/completions` with `stream:true`; measure first content token; print `ttft_ms`; exit 1 if `> TTFT_FAIL_ABOVE_MS`; exit 2 if Ollama unreachable (connection error).

- [ ] **Step 2: Workflow**

```yaml
name: "TTFT live (Ollama, opt-in)"
on:
  workflow_call:
  workflow_dispatch:
jobs:
  ttft-live:
    if: ${{ vars.TTFT_LIVE == 'required' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - name: Run TTFT live
        env:
          OLLAMA_BASE_URL: ${{ secrets.OLLAMA_BASE_URL || 'http://127.0.0.1:11434' }}
          TTFT_FAIL_ABOVE_MS: ${{ vars.TTFT_FAIL_ABOVE_MS || '2000' }}
        run: python3 scripts/verify_ttft.py
```

Wire `uses: ./.github/workflows/eval-ttft-live.yml` into CI templates (job no-ops when `TTFT_LIVE` unset).

- [ ] **Step 3: Local smoke (dev machine with Ollama)**

Run: `OLLAMA_BASE_URL=http://127.0.0.1:11434 python3 scripts/verify_ttft.py`  
Expected: exit 0, prints `ttft_ms=...`

- [ ] **Step 4: Commit**

```bash
git add scripts/verify_ttft.py workflow-templates/eval-ttft-live.yml workflow-templates/ci-*.yml
git commit -m "$(cat <<'EOF'
ci: add optional live Ollama TTFT gate (TTFT_LIVE=required)

EOF
)"
```

---

### Task 7: Document TTFT env keys + FIXES

**Files:**
- Modify: `portal/.env.example`, `templates/uae-sovereign/env.example`
- Modify: `FIXES_AND_CLEANUP.md` (TTFT section → Shipped v1)
- Modify: `README.md` / `SPECS.md` brief note: TTFT via `complete_stream`

- [ ] **Step 1: Document**

```bash
TTFT_FAIL_ABOVE_MS=2000
# TTFT_LIVE=required   # repo variable — enable live Ollama job
```

- [ ] **Step 2: Commit**

```bash
git add portal/.env.example templates/uae-sovereign/env.example FIXES_AND_CLEANUP.md README.md SPECS.md
git commit -m "$(cat <<'EOF'
docs: mark TTFT streaming path shipped (v1)

EOF
)"
```

---

### Task 8: Self-correction activity + pure helper (unit-testable)

**Files:**
- Create: `runtime/self_correction.py`
- Create: `runtime/test/test_self_correction.py`

- [ ] **Step 1: Failing tests**

```python
# runtime/test/test_self_correction.py
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from self_correction import propose_corrected_payload, run_self_correction_loop


@pytest.mark.asyncio
async def test_propose_corrected_payload_parses_json():
    gw = MagicMock()
    gw.complete = AsyncMock(
        return_value=MagicMock(text='{"status": "active", "customer_id": 1}')
    )
    out = await propose_corrected_payload(
        gw, payload={"account_status": "active"}, error="unknown field account_status"
    )
    assert out == {"status": "active", "customer_id": 1}


@pytest.mark.asyncio
async def test_loop_succeeds_after_one_correction():
    calls = {"n": 0}

    async def activity(payload):
        calls["n"] += 1
        if "account_status" in payload:
            raise ValueError("bad field")
        return {"ok": True}

    gw = MagicMock()
    gw.complete = AsyncMock(
        return_value=MagicMock(text='{"status": "active"}')
    )

    result = await run_self_correction_loop(
        activity_fn=activity,
        payload={"account_status": "active"},
        gateway=gw,
        max_self_correction_attempts=1,
    )
    assert result == {"ok": True}
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_loop_exhausts_then_returns_sentinel():
    async def activity(payload):
        raise ValueError("still bad")

    gw = MagicMock()
    gw.complete = AsyncMock(return_value=MagicMock(text='{"status": "x"}'))

    result = await run_self_correction_loop(
        activity_fn=activity,
        payload={"account_status": "active"},
        gateway=gw,
        max_self_correction_attempts=1,
    )
    assert result == {"__self_correction_exhausted__": True, "payload": {"status": "x"}, "error": "still bad"}
```

- [ ] **Step 2: Run — expect fail**

Run: `python3 -m pytest runtime/test/test_self_correction.py -v`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement `runtime/self_correction.py`**

```python
async def propose_corrected_payload(gateway, payload, error: str, model_hint: str = "developer"):
    prompt = (
        "The following JSON payload failed validation/execution.\n"
        f"ERROR: {error}\nPAYLOAD:\n{json.dumps(payload)}\n"
        "Return ONLY corrected JSON object, no markdown."
    )
    result = await gateway.complete(prompt, model_hint=model_hint)
    text = result.text.strip()
    # strip ```json fences if present
    ...
    return json.loads(text)

async def run_self_correction_loop(*, activity_fn, payload, gateway, max_self_correction_attempts=1, model_hint="developer"):
    current = payload
    last_error = ""
    try:
        return await activity_fn(current)
    except Exception as exc:
        last_error = str(exc)
    for _ in range(max_self_correction_attempts):
        current = await propose_corrected_payload(gateway, current, last_error, model_hint=model_hint)
        try:
            return await activity_fn(current)
        except Exception as exc:
            last_error = str(exc)
    return {"__self_correction_exhausted__": True, "payload": current, "error": last_error}
```

- [ ] **Step 4: Run — expect pass**

Run: `python3 -m pytest runtime/test/test_self_correction.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add runtime/self_correction.py runtime/test/test_self_correction.py
git commit -m "$(cat <<'EOF'
feat: add self-correction payload loop helper

EOF
)"
```

---

### Task 9: Wire `run_with_self_correction` on BaseAgentWorkflow

**Files:**
- Modify: `runtime/workflows/base_workflow.py`
- Modify: `runtime/test/test_self_correction.py` (optional Temporal-light test) OR document that workflow method delegates to activity

- [ ] **Step 1: Add Temporal activity `self_correct_payload_activity`**

In `base_workflow.py` (alongside `dlq_enqueue_activity`):

```python
@activity.defn
async def self_correct_payload_activity(args: dict) -> Any:
    """args: tenant_id, payload, error, model_hint"""
    from runtime.llm_gateway import LLMGateway
    from runtime.self_correction import propose_corrected_payload
    gw = LLMGateway(tenant_id=args["tenant_id"])
    return await propose_corrected_payload(
        gw, args["payload"], args["error"], model_hint=args.get("model_hint", "developer")
    )
```

- [ ] **Step 2: Add workflow method**

```python
async def run_with_self_correction(
    self,
    activity_name: str,
    payload: Any,
    tenant_id: str,
    gate_id: str,
    reason: str = "validation_error",
    timeout: timedelta = HITL_SIGNAL_TIMEOUT,
    max_attempts: int = RECOVERABLE_STEP_MAX_ATTEMPTS,
    max_self_correction_attempts: int = 1,
    model_hint: str = "developer",
) -> Any:
    current = payload
    last_error = ""
    try:
        return await workflow.execute_activity(
            activity_name, current,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except Exception as exc:
        last_error = str(exc)[:500]

    for _ in range(max_self_correction_attempts):
        current = await workflow.execute_activity(
            self_correct_payload_activity,
            {"tenant_id": tenant_id, "payload": current, "error": last_error, "model_hint": model_hint},
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        try:
            return await workflow.execute_activity(
                activity_name, current,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        except Exception as exc:
            last_error = str(exc)[:500]

    # Fall through — unchanged human path
    return await self.run_with_recoverable_step(
        activity_name, current, tenant_id, gate_id,
        reason=reason, timeout=timeout, max_attempts=max_attempts,
    )
```

**Do not** modify `run_with_recoverable_step` body.

- [ ] **Step 3: Ensure workers register `self_correct_payload_activity`** — grep worker registration in examples/oil-price-agent and docs; add activity to any central list / example README note.

- [ ] **Step 4: Commit**

```bash
git add runtime/workflows/base_workflow.py
git commit -m "$(cat <<'EOF'
feat: add run_with_self_correction opt-in before DLQ

EOF
)"
```

---

### Task 10: Docs for self-correction + FIXES closeout

**Files:**
- Modify: `FIXES_AND_CLEANUP.md` (self-correction → Shipped v1)
- Modify: `README.md`, `SPECS.md` (brief)
- Modify: `docs/superpowers/specs/2026-07-10-reliability-pack-v1-design.md` status → Implemented

- [ ] **Step 1: Update docs** — document opt-in API, default attempts=1, does not wrap existing call sites

- [ ] **Step 2: Commit**

```bash
git add FIXES_AND_CLEANUP.md README.md SPECS.md docs/superpowers/specs/2026-07-10-reliability-pack-v1-design.md
git commit -m "$(cat <<'EOF'
docs: mark reliability pack v1 (self-correction) shipped

EOF
)"
```

---

### Task 11: Verification sweep

- [ ] **Step 1: Run unit tests**

```bash
python3 -m pytest scripts/test/test_hallucination_evals.py runtime/test/test_ttft_stream.py runtime/test/test_self_correction.py -v
```

Expected: all PASS

- [ ] **Step 2: Optional live**

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 python3 scripts/verify_ttft.py
```

- [ ] **Step 3: Confirm `run_with_recoverable_step` unchanged**

```bash
git log -1 -p -- runtime/workflows/base_workflow.py | head -5
# or: git diff main -- runtime/workflows/base_workflow.py  and ensure recoverable method body only gained a sibling method
```

---

## Spec coverage checklist

| Spec requirement | Task |
|---|---|
| Judge `hallucination` field | 1 |
| Rate = flagged/scored; flag ≥ 0.5 | 2 |
| `HALLUCINATION_FAIL_ABOVE` default 0.05; CLI + .env | 2, 4 |
| Hard-fail CI workflow | 3 |
| `complete_stream` + `ttft_ms` | 5 |
| Mock unit CI | 5 |
| Live Ollama + `TTFT_LIVE` | 6, 7 |
| `run_with_self_correction` opt-in; fall through recoverable | 8, 9 |
| Recoverable unchanged | 9, 11 |
| FIXES/README/SPECS | 4, 7, 10 |

## Placeholder scan

None intentional. Fixture count for live hallucination CI is explicitly “4 grounded” to keep default rate ~0; invented behavior covered by unit rate tests.
