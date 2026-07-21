# Test Coverage Review — 2026-07-21

**Inventory:** 16 `runtime/test/` files, 10 `scripts/test/` files, 5 portal tests
(4 suites + ts loader), 1 widget jsdom suite, plus the `self-test.yml` CI jobs
(py_compile, SPECS-tree drift, redaction/hooks/KG/on-prem/delivery checks,
Postgres-backed behaviour job with a live Temporal test server, portal
build+tests+live history-sync, security harness strict, ShellCheck).

## Coverage matrix by framework layer

| Layer (README §Architecture) | Tested today | Verdict |
|---|---|---|
| **Security & Guardrails** | prompt_guard, tool_registry (deny-by-default), structured_output, moderation, input_guardrail, trace_redactor, luhn parity, harness registry/evidence/risk-register, adversarial suite, SSO fail-closed | **Strong** — best-covered layer |
| **Reliability & Accuracy** | Recoverable step + self-correction on a real Temporal test server; budget race regression; provider dispatch (mocked); TTFT stream; fairness/hallucination eval logic | **Good** — unit level |
| **Memory Management** | conversation_memory + vector store (hash embedder, memory backend) | **Partial** — no pgvector CI job (known FIXES gap); KG API (`inject_production_learning`, `fetch_subgraph_context_window`) untested |
| **Perception & Input Parsing** | parse_llm_json + Pydantic validation | **Good** |
| **HITL** | Approve/reject + recoverable-step + self-correction workflow paths | **Partial** — `temporal_replay.py` and `replay_webhook_server.py` (portal "Replay with edits" → live workflow signal) have no test |
| **Observability** | trace_redactor profiles (CI), portal phoenix.ts parsing, live history-sync check | **Partial** — no automated span-contract E2E (agent → OTel → Phoenix → portal cost/owner attribution) |
| **Explainability / Audit** | Audit-log HMAC sign/verify + tamper detection (`test:db`) | **Good** |
| **Scalability / Deploy** | On-prem Compose+Helm render validation, canary/shadow config render | **Partial** — config-level only; no traffic-behavior test; CD verified live once (P11), not repeatably |
| **Data Bias & Fairness** | Pair-parity suite logic | **Good** (logic) — no live-judge run in CI (by design, needs keys) |
| **Continuous Improvement** | shadow-eval sampling logic; delivery evidence pack | **Partial** — promotion loop scripts (`promote-learning.py`, `sync-ui-feedback.py`) untested |
| **Ops Portal** | authz/cross-tenant isolation, SSO revocation, audit log, phoenix lib | **Partial** — `dlq.ts` replay/discard, `cost.ts`, `widgetTokens.ts`, `oidc.ts`, `promotions.ts` untested |
| **In-App Widget** | jsdom suite incl. XSS-attribute regression | **Good** |
| **Dev lifecycle (Layer 1)** | check_bare_except unit tests; hooks `bash -n` + ShellCheck; IDE-config drift gate (`--check-only`); `--check-kg` smoke | **Weakest layer** — see gaps |

## Gaps (unit-testable now, no tenant app needed)

1. ✅ **CLOSED 2026-07-21** — `scripts/test/test_cost_router.py` (10 tests): tier
   routing, offline/escalation policy, and the Groq-429 FULL-JITTER formula
   pinned (`(2**attempt)*5 + uniform(0,3)`), so the FIXES lesson can't be
   "cleaned up" away.
2. ✅ **CLOSED 2026-07-21** — `scripts/test/test_circuit_breaker.py` (7 tests):
   burst trip, rolling-window expiry, monthly trip (independent of burst),
   month rollover reset, corrupt-state recovery.
3. ✅ **CLOSED 2026-07-21** — `scripts/test/test_knowledge_graph.py` (9 tests):
   KG round-trip, incident injection, subgraph hops, symbol/impact queries,
   walker symbols+edges, vendor-dir exclusion, guardrail extraction, and the
   C2 incremental skip/purge pinned as a committed test.
4. ✅ **CLOSED 2026-07-21** — `scripts/test/test_promotion_loop.py` (7 tests).
   **Writing these exposed a real production bug, now fixed:** both dashed-
   filename imports (`from promote_learning import promote` in
   sync-ui-feedback.py, `from run_evals import run_scorecard` in
   promote-learning.py) could never resolve — every Phoenix-annotation
   promotion errored silently and scorecard re-runs always warned. Both now
   load by file path; the end-to-end sync test is the regression net.
5. ✅ **CLOSED 2026-07-21** — `runtime/test/test_pg_budget_live.py`: real-DB
   atomic-reservation race (20 threads vs $1 cap → exactly 5 winners) +
   reconcile deltas, through the shared `pg_pool` incl. its exhaustion
   fallback. Skips without `DATABASE_URL`; runs automatically in the
   `python-behaviour` CI job (Postgres already provisioned there).
6. ✅ **CLOSED 2026-07-21** — `portal/test/dlqCostWidget.test.ts` (12 tests,
   wired into `npm run test:db`): not-wired degradation paths, cost period
   math + ascending history, DLQ tenant scoping / discard-once transitions /
   replay HMAC signature + webhook-failure leaves entry pending, widget-token
   mint→resolve→revoke with hash-only persistence and cross-tenant isolation.
   Runs in the portal CI job's Postgres lane (tsc-verified locally).
7. ✅ **CLOSED 2026-07-21** — `scripts/test/test_hooks_behavior.py` (12 tests):
   real `git commit` against the installed hooks in a scratch repo with a
   fake `$HOME` — opt-in gate leaves unrelated repos alone, `DISABLE_AI_STACK`
   bypass, Conventional-Commits accept/reject incl. 72-char limit, AI-marker /
   empty-catch / Go double-blank / vendored empty-except blocking (with the
   `# fail-open:` suppression accepted), and both enterprise RFC guardrails.

## What genuinely requires a live tenant app

The remaining scenarios are cross-layer *integration* paths that unit tests
cannot represent: real multi-agent pipelines with real (multiple) LLM
providers; the HITL loop through the portal UI (pause → approve/edit → resume
via `replay_webhook_server` → `temporal_replay`); the budget degrade ladder
firing against live providers mid-pipeline; span → Phoenix → portal cost/owner
attribution; the promotion loop closing end-to-end (production failure →
annotation → golden case → gate blocks the regression); TTFT/live-judge/
sovereign smokes; canary + shadow routing with real traffic. The
`examples/oil-price-agent` reference covers a slice (one 3-step pipeline,
HITL + recoverable step) but was not designed to exercise the full surface —
it uses one model family, no RAG memory, no tool registry, no fairness-
sensitive domain, no widget/portal round-trip.

**Proposal:** a purpose-built testbed tenant — spec in
[`docs/testbed-tenant-spec.md`](./docs/testbed-tenant-spec.md) — designed so
that every framework layer is exercised by at least one observable scenario.

## Recommended order

1. ~~Close unit gaps 1–4~~ ✅ done 2026-07-21 (+33 tests; suite now 158 passed).
2. ~~Postgres budget-backend test in `python-behaviour`~~ ✅ done 2026-07-21.
3. ~~Portal lib tests (gap 6) + hook-behavior tests (gap 7)~~ ✅ done 2026-07-21
   (Python suite now 170 passed; portal test:db lane gained 12 DB tests).
4. Build the testbed tenant per the spec; wire its CI to the reusable eval workflows with `strict: true`; use it as the standing E2E bed for every framework release (§28 compatibility gate). **This is now the only remaining item.**
