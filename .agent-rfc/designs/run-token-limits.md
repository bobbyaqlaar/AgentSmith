---
status: active
scope:
  - agentsmith/token_limits.py
  - agentsmith/llm_gateway.py
  - agentsmith/tool_registry.py
  - scripts/gate_models.py
  - scripts/evals_port.py
  - contract/evals/**
  - agentsmith/test/test_token_limits.py
  - agentsmith/test/test_ttft_stream.py
  - agentsmith/test/test_moderation_declared.py
  - agentsmith/test/_gateway_fixtures.py
  - scripts/test/test_trajectory_evals.py
  - portal/**
---
# Tenant apps spend fewer tokens: caps per role, limits per run

The run half of the token goal (the paper's "Using fewer tokens").

## Problem

The gateway counts tokens and caps money, but nothing bounds tokens as such. Every role may answer at up to 4,096 tokens unless the caller passes less, and a prompt of any size is sent. A run that loops through tools or model calls runs until the monthly budget stops it, which on local models (cost zero) is never. On owned hardware that is lost capacity, not just money.

## Approach

**Per role, in `models.yaml`.** Two optional fields on a model entry:

- `max_output_tokens` caps the answer. The gateway sends the smaller of it and what the caller asked for, so the cost reservation shrinks too.
- `max_input_tokens` refuses a prompt estimated larger, with `ContextTooLargeError` naming the role and both sizes, before anything is sent.

**Per run, in `tenant.yaml`.**

- `limits.run_tokens` (or `AGENTSMITH_RUN_TOKEN_LIMIT`) is a token budget for one workflow run, keyed by `workflow_id`. Each call reserves its estimate (prompt plus output cap) before it is sent, through the same atomic budget backend the spend cap uses, so concurrent calls in one run cannot overshoot. It is settled to the real count afterwards, and released if the call fails. A call that would pass the budget raises `RunLimitExceededError` and is not sent.
- `limits.run_tool_calls` (or `AGENTSMITH_RUN_TOOL_CALL_LIMIT`) is a tool-call limit per run, enforced by `ToolRegistry.invoke(..., run_id=…)` through the same backend. The next call over raises `ToolCallLimitExceededError`.

Both are off until declared, so no tenant's behaviour changes on upgrade. With `BUDGET_BACKEND=memory` the run counters are per process, as the spend cap already is and already warns.

**In the trajectory evals.** A case may declare `max_tokens`. Its run's tokens are read from the trace's model spans (`gen_ai.usage.*`, else `llm.usage.*`), so CI can fail a recorded run that spent more than its budget.

**In the portal.** The Recent runs list shows each call's input and output tokens, with "not reported" where the provider gave none.

Tokens are estimated at four characters each where they must be known before the call. The real counts settle the run budget afterwards.

## After the 4.1.0 review (2026-11-11)

The 4.1.0 release review found seven places where this design's claims did not hold. Each is fixed here, with a test that failed before:

- **R1 — a refused call kept its run charge.** The run is now reserved only after the money cap accepts the call; the money is given back if the run refuses; every exit that sends nothing (no tier to try, a compliance refusal on the stream path, a failed stream) releases both.
- **R20 — a stream that falls back.** Both fallbacks to `complete()` pass `data_class` and `user_id`, and the stream's reservation is released before `complete()` reserves its own.
- **R5 — a fallback tier's caps.** Each attempt in the degrade chain is checked against its own `max_input_tokens` and sent at most its own `max_output_tokens`. `ContextTooLargeError` and `LimitUnreadableError` are raised as themselves, not wrapped as "all tiers exhausted".
- **R4 — a mistyped limit.** "Not declared" (absent or empty) is no limit; anything else that is not a positive whole number raises `LimitUnreadableError` naming the setting. `true`, `0`, `1.5` and `100k` are refused.
- **R6 — run counters.** They leave the money ledger for a store of their own, matched to the budget backend: in process (pruned after `RUN_TTL_SECONDS` idle), Redis (keys expire), or Postgres (`llm_gateway_run_counters`, stale rows deleted at most hourly). No month in the key.
- **R2 — `max_tokens` on a trace that reports no usage.** `_trace_tools` returns no token count when any model span lacks usage (`llm.usage.reported` false, or a model span with no token pair) or none reported any; the case is `not_gradable`.
- **R11 — an empty case file.** `dataset` returns "holds no cases", so every suite is `not_gradable` on `[]`.

## Pillars

- P1 applies — the paper's token goal is the requirement; `.agent-rfc/designs/run-token-limits.md` is the plan.
- P2 applies — `agentsmith/token_limits.py` holds the arithmetic; the gateway and the registry call it; no new dependency.
- P3 applies — `agentsmith/llm_gateway.py` already writes token counts on its span; a refusal is raised before a span claims a call.
- P4 applies — `agentsmith/test/test_token_limits.py` covers the caps, the run budget with its reserve, settle and release, and the tool limit; mutation-checked by hand.
- P7 applies — `scripts/gate_models.py` `TrajectoryExpect` gains `max_tokens`; the published schema is regenerated.
- P8 n/a — no telemetry attribute is added.
- P9 applies — `agentsmith/tool_registry.py` limits a run's tool calls, the loop an orchestration can fall into.
- P10 applies — `agentsmith/token_limits.py` is this pillar's runtime half: the output cap shrinks every reservation.
- P11 n/a — nothing new reads untrusted content.
- P12 n/a — no secrets involved.
- P13 n/a — no gate changes.
- P14 applies — `contract/evals/v1/dataset.trajectory.schema.json` is regenerated from the model, held by `scripts/test/test_evals_contract.py`.
- P15 applies — `agentsmith/test/test_token_limits.py` holds that an undeclared limit changes nothing, a run with unreported usage keeps its reservation as the charge, and an unreadable limit is refused (R4); `scripts/test/test_trajectory_evals.py` holds that an unmeasured trace is `not_gradable` (R2).
- P16 applies — `CHANGELOG.md` names the settings; all are off until declared. The run-counter table (`llm_gateway_run_counters`) is created on first use and holds nothing older than two days, so dropping it loses only live runs' counts.

## Deviations

none

## Dependencies

none

## Levers

- `failure-is-not-a-result` — unreported usage keeps the reservation; it is never read as zero.
- `test-that-cannot-fail` — hand mutants.
- `declared-vs-enforced` — each limit is enforced where it is declared, and off where it is not; a fallback tier is held to its own caps (R5).
- `early-exit-keeps-the-record` — every exit between reserve and send releases what it reserved (R1, R20).
- `guards-must-be-able-to-fail` — an unreadable limit raises instead of reading as none (R4).
- `ambiguous-signals` — an unreported token count is absent, never 0 (R2, R11).
- `use-existing-apis` — run counters get a store shaped for them, not the money table (R6).
