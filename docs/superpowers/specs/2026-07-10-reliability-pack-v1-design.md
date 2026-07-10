# Reliability pack v1 — hallucination rate, TTFT, self-correction

**Date:** 2026-07-10  
**Status:** Implemented  
**Approach:** Parallel thin slices (hallucination + TTFT + self-correction)

## Goals

Ship three independent thin v1s from `FIXES_AND_CLEANUP.md`:

1. **Hallucination-rate metric** — named judge dimension + hard CI gate  
2. **TTFT** — opt-in streaming path + `ttft_ms` + mock CI + optional live Ollama job  
3. **LLM self-correction** — opt-in `run_with_self_correction` before DLQ  

Non-goals for v1: replacing `correctness`; changing default non-stream `complete()`; inserting self-correction in front of existing `run_with_recoverable_step` call sites; claiming streaming UX in the Ops Portal.

## Decisions (locked)

| Topic | Choice |
|---|---|
| Scope | All three, thin v1 each |
| CI bar | Hard fail for hallucination rate + TTFT budget |
| TTFT CI | Mock stream in unit CI **and** optional live Ollama job |
| Hallucination gate | Rate ≤ 5% flagged cases; `HALLUCINATION_FAIL_ABOVE=0.05` |
| Config | AgentSmith root `.env` **and** tenant `.env` (same load pattern as fairness) |
| Self-correction | Separate opt-in API; fall through to existing recoverable/DLQ path |

---

## 1. Hallucination-rate metric

### Behavior

- Add judge dimension `hallucination` (float 0.0–1.0):  
  **0** = nothing unsupported by input/retrieved context; **1** = severe unsupported claims.  
  Distinct from `correctness` (wrong answer vs invented claim).
- A case is **flagged** when `hallucination >= 0.5`.
- **Rate** = `flagged_count / scored_count` (scored = cases with a numeric hallucination score).
- Hard fail when `rate > HALLUCINATION_FAIL_ABOVE` (default **0.05**).

### Config

| Source | Precedence |
|---|---|
| CLI `--hallucination-fail-above` | Highest |
| Env `HALLUCINATION_FAIL_ABOVE` | After dotenv load |
| Default `0.05` | Lowest |

Dotenv: reuse `run-evals.py` `_load_dotenv` (repo root `.env` does not overwrite existing env). Document key in:

- AgentSmith / portal-facing env example (framework root guidance in OPERATIONS / `portal/.env.example` comment block or tenant template as appropriate)
- Tenant scaffolding / `templates/uae-sovereign/env.example` (and any existing tenant `.env.example` pattern)

### Artifacts

- Extend `.agent-rfc/fixtures/custom_judge_criteria.json` (and fairness criteria if shared) with `hallucination` rubric text.
- Small golden/hallucination fixture cases (supported vs unsupported claims).
- `scripts/run-evals.py`: compute rate; exit non-zero on breach.
- Workflow: hard-fail job (new `eval-hallucination.yml` or extend scorecard) — **required** gate, not warn-only.
- Unit tests: rate math + threshold from `.env`.

### Out of scope

- Separate “hallucination suite” product name unless fixtures need isolation (prefer additive field on golden + dedicated fixtures file if cleaner).
- Human review UI for flagged cases.

---

## 2. Time-to-First-Token (TTFT)

### Behavior

- Non-streaming `complete()` stays default; **no** `ttft_ms` required on that path.
- Opt-in streaming: e.g. `complete(..., stream=True)` returning an iterator/async generator **or** a dedicated `complete_stream()` — pick one shape in implementation; prefer minimal change to existing callers.
- On first content chunk: record `ttft_ms` (ms since request start) on the span / return metadata alongside existing cost/token fields.
- Provider wiring in `runtime/provider_dispatch.py` (OpenAI-compatible / Ollama path first; other cloud adapters best-effort or stub with clear skip).

### Config

| Env | Default | Meaning |
|---|---|---|
| `TTFT_FAIL_ABOVE_MS` | `2000` | Live Ollama job fails if measured TTFT exceeds this |

Configurable in AgentSmith `.env` and tenant `.env`.

### CI

1. **Unit (required):** mock streaming transport → assert `ttft_ms` is set and ≥ 0 when streaming requested; fail test if missing.
2. **Optional live job:** Ollama `falcon3:1b` stream against `OLLAMA_BASE_URL`; fail if `ttft_ms > TTFT_FAIL_ABOVE_MS`. Skip cleanly if Ollama unreachable (job `continue-on-error: false` only when explicitly enabled via repo variable e.g. `TTFT_LIVE=required`, otherwise optional/skip — **implementation note:** hard-fail when the live job is enabled; default template may be `workflow_dispatch` or `if: vars.TTFT_LIVE == 'required'` so forks without Ollama do not break).

Clarification for implementers: “Hard fail gates” for TTFT means:

- Mock path always hard-fails in normal unit CI.
- Live path hard-fails **when the live job runs**; enablement is opt-in via `TTFT_LIVE=required` so default PR CI stays green without a GPU host.

### Out of scope

- Portal chat UI streaming.
- TTFT on every non-stream call (impossible without fake first-token).

---

## 3. LLM-driven self-correction

### Behavior

- New API: `run_with_self_correction(activity_name, payload, tenant_id, max_self_correction_attempts=1, ...)` (exact signature aligned with `run_with_recoverable_step`).
- On activity failure: call `gw.complete()` with original payload + error text; parse corrected payload; retry activity up to `max_self_correction_attempts`.
- If still failing: **reuse** `run_with_recoverable_step` / existing DLQ enqueue path — do not duplicate DLQ logic.
- **Do not** change behavior of existing `run_with_recoverable_step` call sites.

### Tests

- Unit tests with mocked gateway + mocked activity: success on first correction; exhaust attempts → DLQ path invoked.
- No CI “rate” gate (runtime feature).

### Out of scope

- Auto-enabling self-correction globally.
- Multi-turn tool-choice planners beyond single corrected payload JSON.

---

## File map (expected)

| Area | Likely paths |
|---|---|
| Judge / evals | `scripts/eval_judge.py`, `scripts/run-evals.py`, fixtures under `.agent-rfc/fixtures/` |
| Hallucination CI | `workflow-templates/eval-hallucination.yml` (+ wire into `ci-*.yml`) |
| Streaming / TTFT | `runtime/llm_gateway.py`, `runtime/provider_dispatch.py`, `runtime/test/` |
| TTFT live CI | `workflow-templates/eval-ttft-live.yml` (gated by `TTFT_LIVE`) |
| Self-correction | near recoverable step (`runtime/workflows/` or `runtime/dead_letter.py` neighbor) |
| Docs | `FIXES_AND_CLEANUP.md`, `README.md` reliability bullets, `SPECS.md` brief, env examples |

## Success criteria

- [ ] Hallucination rate computed; hard-fail above `HALLUCINATION_FAIL_ABOVE` (default 0.05); `.env` documented for framework + tenant.
- [ ] Streaming path records `ttft_ms`; unit mock hard-fails if absent; live Ollama job hard-fails when `TTFT_LIVE=required` and over budget.
- [ ] `run_with_self_correction` exists, tested, leaves recoverable path unchanged.
- [ ] FIXES sections updated to **Shipped (v1)** / remaining notes.

## Risks

- Judge variance on `hallucination` → keep threshold on **rate of flags**, not mean score; small fixture set.
- Live TTFT flaky on shared runners → keep behind `TTFT_LIVE`.
- Self-correction may amplify bad retries → default `max_self_correction_attempts=1`.
