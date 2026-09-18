# Review log

Every review this repository has recorded that is not a per-change record under
`.agent-rfc/reviews/`, oldest first. Append-only: a finding is closed by a later entry, never by
editing an earlier one.

## Docs ↔ Code Sync & Code Quality Review — 2026-07-18

*Folded in from `docs/REVIEW_LOG.md` on 2026-09-18.*

**Method:** automated cross-reference of every file path, `ai-*` command, and CLI flag
cited in README / UserManual / OPERATIONS / SPECS / CHANGELOG / FIXES / docs/ against
`git ls-files` and actual argparse definitions; duplicate-function scan across
`scripts/` + `runtime/`; perf-pattern scan of hot paths (gateway, hooks, portal);
`py_compile` sweep and fixtures JSON validation (both pass clean).

### Verified in sync (no action needed)

All 15 `ai-*` shell commands in docs exist in `install-ai-stack.sh` and vice versa.
All `verify_system.py --check-*`, `run-security-checks.py`, and `run-evals.py` flags
cited in docs exist in code. Git hygiene is good: no build artifacts tracked
(`.next`, `.venv`, `node_modules`, `*.tsbuildinfo`, `.DS_Store` all ignored). The
installer copies `scripts/` rather than embedding heredocs, so no installer/repo
duplication. Portal uses a shared pg pool and `Promise.all` on the dashboard.
`scripts/_shared.py` consolidation exists and the scripts↔runtime duplication
boundary is documented as deliberate. On-prem doc references to `scripts/up.sh`
etc. are correct (they refer to the rendered tenant `deploy/onprem/` tree).

### A. Doc ↔ code drift

| # | Severity | Finding |
|---|---|---|
| A1 | Medium | `runtime/agent_logger.py` cited in **docs/UserManual.md:1628** and **templates/onprem-deploy/README.md** (item 4) — the file is `scripts/agent_logger.py`. No runtime copy exists. |
| A2 | Medium | **docs/DESIGN.md › GitHub Repository Repository Structure** claims to be "the only copy" but omits P12+ artifacts: `runtime/` is missing `environment.py`, `moderation.py`, `prompt_guard.py`, `provider_dispatch.py`, `structured_output.py`, `tool_registry.py`, `requirements-runtime.txt`, `test/`; `scripts/` is missing `_shared.py`, `check_bare_except.py`, `delivery_evidence.py`, `delivery_model.py`, `eval_judge.py`, `run-security-checks.py`, `security/`, `shadow-eval.py`, `sync-portal-history.py`, `test/`; `fixtures/` is missing `security/`; `docs/` is missing `security-framework-map.md`, `team-observability.md`, `session-handoff/`; `.agent-rfc/` is missing `security/`. The self-test CI only diffs top-level entries, so sub-tree drift accumulates silently — exactly what happened. |
| A3 | Medium | **docs/DESIGN.md › Component Inventory › Python Agent Stack** is stale vs P12: `run-evals.py` row lists suites `golden, fairness, hallucination` (missing `adversarial`, which the code and CHANGELOG ship); `verify_system.py` row lists 7 CI flags (missing `--check-security` and `--check-delivery-model`, both implemented). The §16 tree's `run-evals.py` comment has the same missing-suite issue. |
| A4 | Low | **docs/DESIGN.md › Component Inventory › Production Runtime** runtime inventory lists only 6 of ~20 runtime modules. It defers to Production Runtime, but as an "inventory" it no longer inventories — either complete it or demote it to a pointer. |
| A5 | Low | `scripts/security/runners/moderation_hook.py` is the only source file not named anywhere in the docs (referenced only via `control_registry.json` runner id). One line in `docs/security-framework-map.md` SEC-MOD-001 row fixes it. |

### B. Redundant code

| # | Severity | Finding |
|---|---|---|
| B1 | Medium | `_luhn_valid` has **two divergent implementations inside `runtime/`**: `input_guardrail.py` strips all non-digits (`\D`); `trace_redactor.py` strips only spaces/hyphens then requires `isdigit()`. A card number with unusual separators can be caught pre-call but survive post-call redaction (or vice versa). Same package — no vendoring boundary excuse; unify into one helper with the more permissive normalization. |
| B2 | Low | `_load_sync_state` / `_save_sync_state` copied byte-for-byte in `shadow-eval.py` and `sync-portal-history.py` (variant defaults in `sync-ui-feedback.py`) despite `scripts/_shared.py` existing precisely for this. |
| B3 | Low | `_load_dotenv` duplicated in `run-evals.py`, `verify_ttft.py`, `verify_sovereign_endpoint.py` — move to `_shared.py`. |
| B4 | Low | `run-security-checks.py` defines its own `_repo_root` while sitting in the same directory as `_shared.py` which exports it. |

### C. Performance

| # | Severity | Finding |
|---|---|---|
| C1 | **High** | `runtime/llm_gateway.py` `_PostgresBudgetBackend` opens a **fresh psycopg2 connection per operation** (`try_reserve`, `add_spend`, `get_spend`) — 2–3 TCP+auth round-trips added to **every LLM call** in the hottest path of the runtime. `idempotency.py` and `dead_letter.py` use the same connect-per-call pattern. SQL atomicity is correct; only pooling is missing. |
| C2 | Medium | `map_codebase.py` re-parses the **entire** repo AST on every commit and checkout (post-commit + post-checkout hooks). It already records per-file `mtime` but never uses it to skip unchanged files. The FIXES "cherry-pick, don't rebase" lesson is a symptom of this cost. |
| C3 | Low | `portal/lib/issues.ts` `syncHistoryEntries` awaits one INSERT per entry; batch into a single multi-VALUES statement (input is bounded, so low impact). |
| C4 | Low | `sync-ui-feedback.py` persists `synced_span_ids` as an ever-growing JSON list re-loaded each run; cap it or key off `last_sync` timestamp. |

### D. Hygiene

| # | Severity | Finding |
|---|---|---|
| D1 | Low | `.claude/settings.local.json` is untracked and not gitignored (shows in `git status`). Add to `.gitignore` (`.claude/settings.json` stays tracked). |
| D2 | Info | Local disk: `.venv` 1.7 GB, `portal/.next` 155 MB, `portal/node_modules` 286 MB — all correctly ignored; prune only if disk pressure. |

### Action plan

**P1 — this week (correctness/perf in production path)** ✅ DONE 2026-07-21
1. **C1 ✅:** `runtime/pg_pool.py` — per-DSN `ThreadedConnectionPool` with ping-validated borrows, pool-exhaustion fallback to direct connect, and a proxy whose `close()` releases to the pool (so every existing `finally: conn.close()` call site stayed untouched; only the three `_connect` methods changed). `PG_POOL_MAX` env (default 5). Tests: `runtime/test/test_pg_pool.py` (fake psycopg2, no live DB).
2. **B1 ✅:** `runtime/luhn.py` — single `luhn_valid` (strips all non-digits), imported by both `input_guardrail.py` and `trace_redactor.py`. Tests: `runtime/test/test_luhn_parity.py` incl. an identity assertion so the two controls can never drift again. Full `runtime/test/` suite: 71 passed, 13 skipped (pre-existing optional-dep skips).

**P2 — next docs pass (drift removal)** ✅ DONE 2026-07-21
3. **A1 ✅:** `runtime/agent_logger.py` → `scripts/agent_logger.py` in docs/UserManual.md and templates/onprem-deploy/README.md.
4. **A2/A3/A4 ✅:** SPECS §16 tree updated (P12 runtime/scripts/fixtures/docs entries + new `pg_pool.py`/`luhn.py` + this file); §5.4 gained rows for the 10 undocumented scripts, the `adversarial` suite, and both missing `verify_system` flags; §5.5 now inventories all runtime modules. `self-test.yml` drift diff extended to second-level entries of `scripts/`, `runtime/`, `docs/`, `fixtures/` (verified locally: 31 top-level + 64 second-level entries pass; the old check was top-level-only, which is exactly where P12 drifted).
5. **A5 ✅:** `scripts/security/runners/moderation_hook.py` named in the SEC-MOD-001 evidence column.

**P3 — opportunistic cleanup (low risk, do alongside other changes)** ✅ DONE 2026-07-21
6. **B2/B3 ✅:** `_load_sync_state`/`_save_sync_state`/`_load_dotenv` now live in `scripts/_shared.py`; local copies deleted from all 6 consumers. **B4 ✓ (amended):** `run-security-checks.py`'s `_repo_root` turned out to be a *false* duplicate — file-relative (install location), not cwd-relative like `_shared`'s — so it was renamed to `_install_root()` with the rationale documented instead of being swapped.
7. **C2 ✅:** `map_codebase.py` skips files whose stored `last_modified` matches current mtime (also eliminating the per-upsert graph save each node triggered); `AGENT_KG_DEFER=1` guard added to both hooks. Verified in a scratch repo: full parse → all-skip → single re-parse on touch → purge on delete. FIXES lesson updated (rebase is safe with the guard).
8. **C3/C4/D1 ✅:** `syncHistoryEntries` batches into chunked multi-VALUES upserts (with in-batch dedupe, since ON CONFLICT rejects same-key twice per statement); `synced_span_ids` bounded to newest 5000; `.claude/settings.local.json` gitignored. Verification: 125 Python tests + 7 portal tests pass, `tsc --noEmit` clean, hooks `bash -n` clean, `check_bare_except` clean.

**Not run here:** the pytest/vitest suites (host `.venv` is macOS-native; sandbox is Linux). Run `pytest` + `npm test` in `portal/` after P1 changes.

## Test Coverage Review — 2026-07-21

*Folded in from `docs/REVIEW_LOG.md` on 2026-09-18.*

**Inventory:** 16 `runtime/test/` files, 10 `scripts/test/` files, 5 portal tests
(4 suites + ts loader), 1 widget jsdom suite, plus the `self-test.yml` CI jobs
(py_compile, SPECS-tree drift, redaction/hooks/KG/on-prem/delivery checks,
Postgres-backed behaviour job with a live Temporal test server, portal
build+tests+live history-sync, security harness strict, ShellCheck).

### Coverage matrix by framework layer

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

### Gaps (unit-testable now, no tenant app needed)

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

### What genuinely requires a live tenant app

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
[`docs/testbed-tenant-spec.md`](testbed-tenant-spec.md) — designed so
that every framework layer is exercised by at least one observable scenario.

### Recommended order

1. ~~Close unit gaps 1–4~~ ✅ done 2026-07-21 (+33 tests; suite now 158 passed).
2. ~~Postgres budget-backend test in `python-behaviour`~~ ✅ done 2026-07-21.
3. ~~Portal lib tests (gap 6) + hook-behavior tests (gap 7)~~ ✅ done 2026-07-21
   (Python suite now 170 passed; portal test:db lane gained 12 DB tests).
4. Build the testbed tenant per the spec; wire its CI to the reusable eval workflows with `strict: true`; use it as the standing E2E bed for every framework release (§28 compatibility gate). **This is now the only remaining item.**

## What Building a Tenant Taught Us — AgentSmith feedback from KYC Sentinel

*Folded in from `docs/REVIEW_LOG.md` on 2026-09-18.*

**Source:** first full build of the `KYC_Sentinel` testbed tenant
(`Apps/KYC_Sentinel`, spec: `docs/testbed-tenant-spec.md`), 2026-07-21.
**Method:** every claim below was reproduced against the real framework
code, not inferred from docs. Reproduction commands are inline.

The testbed paid for itself: it surfaced one **High** framework gap that
no unit test could have caught, because it only appears when two
separately-tested features are combined the way a real tenant would
combine them.

---

### A. Framework gaps

> **Status 2026-07-21 (same day):** **every framework gap G1–G10 is fixed.**
> Framework suite 170 → **283 passing**; the testbed tenant 25 → **36**, and
> the tenant now runs entirely against the installed package. Four findings
> were discovered by fixing others: G9 while wiring G3, G10 while hardening
> the tenant's security CI after G5, G6's `scripts/` breakage while removing
> the import fallbacks, and G8's clobber bug while writing its test — each
> fix exposed the next layer down, which is the argument for keeping the
> testbed permanently. Remaining work is the tenant's own (E2/E3) and the
> deployment path (DEVLOG pending sections), not framework gaps.

#### G1 — `complete_stream()` cannot stream the frontier providers (**High**) ✅ FIXED

`complete_stream()` raises `NotImplementedError` for `anthropic` and for
every cloud-native provider (Vertex / Bedrock / Azure / Huawei). Only
`openai`, `ollama`, and `groq` work.

```
$ python3 - <<'EOF'   # gateway with analyst=claude-sonnet-4-6 (provider anthropic)
asyncio.run(gw.complete_stream("hi", model_hint="analyst"))
EOF
NotImplementedError: complete_stream currently supports OpenAI-compatible providers only; got 'anthropic'.
```

Why this matters: the TTFT budget is the framework's latency guarantee,
and the docs present it unconditionally —

- SPECS §3: "TTFT via opt-in `LLMGateway.complete_stream()`"
- SPECS §5.5 / §16: "`complete()` + `complete_stream()` (ttft_ms)"
- OPERATIONS "TTFT on the streaming path", CHANGELOG 1.0.0

None of them mention a provider restriction. The natural tenant design —
frontier model on the user-visible latency-critical path — is exactly the
configuration that cannot use TTFT. `verify_ttft.py` smoke-tests Ollama, so
CI never noticed.

**Fix options:** (a) implement Anthropic SSE in `complete_stream` (its
streaming API is well-defined and `provider_dispatch` already owns the
request/response envelope); (b) at minimum, make `complete_stream`
fall back to `complete()` with `ttft_ms=None` and a logged warning
instead of raising, so a provider swap in `models.yaml` can't take a
tenant's pipeline down; (c) document the restriction everywhere TTFT is
claimed. Recommend (a) + (c); (b) as the interim.

**Fixed:** all three. `provider_dispatch.parse_stream_delta()` +
`supports_streaming()` own the per-provider SSE envelope (Anthropic's
`content_block_delta` text events; non-text frames return `None` so TTFT is
timed from the first real *token*, not the first protocol frame).
Cloud-native providers fall back to `complete()` *before* any budget
reservation or run-status row, so `complete()` owns the whole call — no
double reservation. `_resolve_endpoint()` was extracted because the
streaming path's near-duplicate copy silently omitted the `anthropic`
branch, which is part of why this never worked. Tests:
`runtime/test/test_stream_providers.py` (9). Docs: SPECS §3/§5.5,
OPERATIONS TTFT section, CHANGELOG.

#### G2 — The degrade ladder only descends one rung (**Medium**) ✅ FIXED

`_degrade_chain()` correctly builds the full chain, but `_resolve_role()`
returns `chain[1]` — one hop — and `complete()` then hard-fails if the
reservation still doesn't fit:

```
full chain from analyst: ['analyst', 'research', 'intake']
resolve(analyst) when breached -> ('research', 'downgrade')
resolve(research) when breached -> ('intake', 'local')
```

A caller always asking for `analyst` therefore never reaches the free
`intake` rung: it degrades to the *paid* `research` tier, and when that
reservation fails it raises `BudgetExceededError`. SPECS §29's documented
ladder ends in "4. Local — switch to Ollama … 5. Alert", but rung 4 is
unreachable whenever a paid tier sits between the caller's role and the
local one — which is the normal shape of a cost ladder.

**Fix:** walk the chain until a role's reservation succeeds (or the chain
is exhausted), rather than taking a single step; prefer the first free
tier when the budget is breached. Add a test asserting `analyst` resolves
to `intake` when both `analyst` and `research` are unaffordable.

**Fixed:** `_resolve_role` now walks the whole chain to the first free
tier (the budget is already breached, so a paid rung only buys one more
call before failing, while a free rung keeps the tenant serving), falling
back to the next configured paid rung only when the chain has no free
tier. Tests: `runtime/test/test_degrade_ladder.py` (8), including the
testbed's real `analyst → research → intake` shape, broken chain links,
and a cyclic `degrade_to`.

#### G3 — Guardrail evidence is unreachable by the caller (**Medium**) ✅ FIXED

`complete()` runs the PII scrub internally and records the counts to logs
and span attributes — but `CompletionResult` exposes only
`text, model_used, input_tokens, output_tokens, cost_usd, degrade_tier,
ttft_ms`. An app that must record *what was redacted* in its own decision
record (any PDPL/GDPR decision-path app — the exact use case the framework
markets) cannot get the counts back.

KYC Sentinel worked around this by re-running `scrub_text()` in the intake
agent before calling the gateway, which means the scrub runs twice per
application. It's idempotent, so it's safe — but it's a workaround every
compliance-minded tenant will independently reinvent.

**Fix:** add `guardrail_counts: dict[str, int]` and `prompt_guard_reasons:
list[str]` to `CompletionResult`. Cheap, backward-compatible, removes the
double scrub.

**Fixed:** both fields added (defaulting empty, so every existing caller is
unaffected) and populated on both the streaming and non-streaming paths.
Tests: `runtime/test/test_guardrail_evidence.py` (4), which also asserts
the redacted text is what actually reached the provider. Fixing this
surfaced **G9** below.

#### G4 — No test double for the gateway (**Medium**) ✅ FIXED

Nothing in `runtime/` provides a fake/recording `LLMGateway`, so the
tenant wrote ~60 lines of `FakeGateway` (`agents/gateway.py`) before it
could test anything. Every tenant will write that same class, differently,
and each one will drift from `CompletionResult`'s real shape.

**Fix:** ship `runtime/testing.py` with `FakeGateway` (scripted responses,
recorded calls, `degrade_tier`/`ttft_ms` simulation) and a
`RecordingGateway` wrapper for live-call assertions. This is the single
highest-leverage addition for tenant developer experience — it is what
made the whole testbed runnable offline.

**Fixed:** `runtime/testing.py` ships both, with scripted per-call response
queues, callables, budget-cap simulation raising the real
`BudgetExceededError`, and assertion helpers (`routes_used()`,
`calls_for()`, `assert_prompt_excludes()` — the last one turns "PII never
reached the model" into one line). Tests:
`runtime/test/test_testing_doubles.py` (9).

**The rule the double encodes:** it is deliberately *no more capable than
the real gateway* — `complete_stream` refuses to stream what the real
gateway can't. This is the lesson from G1: the testbed's hand-rolled
double aliased `complete_stream` to `complete`, so a guaranteed production
crash looked green offline for the entire build. A test double that
over-promises hides exactly the bugs a testbed exists to find.

KYC Sentinel now subclasses it (only ~45 lines of domain scripting remain),
which immediately exposed a second, smaller lesson: the extension point
must be named unambiguously. The tenant's `_respond()` helper collided with
the framework's internal method of the same name; the internal one is now
`_build_result()` and `_resolve_text(call)` is documented as the single
override hook.

#### G5 — Tenant security pack is never seeded (**Medium**) ✅ FIXED

`fixtures/security/templates/` contains `agency_manifest.yaml`,
`nist_profile.yaml`, `risk_register.yaml`, `tool_allowlist.yaml`, and the
`SEC-*` harness has runners that look for them in a tenant's
`.agent-rfc/security/`. But nothing copies them there:

```
$ grep -rn "security/templates|agency_manifest|risk_register.yaml" install-ai-stack.sh hooks/post-checkout
(no matches)
```

So a new tenant starts with those controls skipping/failing and must
discover the templates by reading the framework tree. KYC Sentinel
hand-wrote `tool_allowlist.yaml` and never created the other three —
which is why its CI security step is currently `|| true`.

**Fix:** `ai-tenant-init` (and/or `post-checkout` on an opted-in repo)
copies `fixtures/security/templates/*` into `.agent-rfc/security/` when
absent — the same vendoring mechanism already used for
`agent-rules.yaml` and the golden-eval seeds.

**Fixed** via exactly that two-stage vendoring path:

1. `install-ai-stack.sh` copies `fixtures/security/templates/*.yaml` into
   `~/.agent-framework/shared/security/` (refreshed every install — these
   are pristine templates, never a tenant's edited copy).
2. `hooks/post-checkout` seeds any of the four that are **missing** from an
   opted-in repo's `.agent-rfc/security/`, and prints which ones are
   placeholders plus the command to verify them.

The never-overwrite guard is the important half: a filled-in risk register
is the tenant's own document — its content is precisely what the framework
cannot know — so a later branch switch must not clobber it. Tests:
`scripts/test/test_security_pack_seeding.py` (7), covering seed-all,
seed-only-missing, never-overwrite, the opt-in gate still applying, and a
machine whose install predates the step.

#### G6 — `runtime/` is not an installable package (**Medium**) ✅ FIXED

There is no `pyproject.toml`/`setup.py` anywhere in the repo, so a tenant
cannot `pip install` the runtime. Consequences observed:

- The tenant needs a path-bootstrap module (`agents/_framework.py`) before
  any framework import.
- The `try: from runtime.X import … except ImportError: from X import …`
  dance appears in **7 of the framework's own runtime modules** and had to
  be replicated in 6 tenant files.
- `Dockerfile` must `COPY AgenticFramework/runtime` from a parent
  directory, so the tenant image can't be built from the tenant repo alone.

**Fix:** add a minimal `pyproject.toml` exposing `runtime` as
`agentsmith_runtime`, publish to an internal index (or install from git
ref). This also kills the dual-import boilerplate.

**Fixed.** `pyproject.toml` publishes `agentsmith-runtime` with backend
extras (`[postgres] [redis] [temporal] [hitl] [cloud] [all]`) mirroring the
runtime's lazy imports, so a tenant takes only what it uses.

*Deviation from the original note:* the import name stays **`runtime`**, not
`agentsmith_runtime`. Renaming would break every `from runtime.X import Y`
in every tenant repo simultaneously — a major-version change, not something
to land under a live tenant. The generic name is a real collision risk in a
crowded virtualenv and is recorded in `pyproject.toml` as the follow-up.

Removed: **16 dual-import blocks** across 6 runtime modules, plus 8 more in
the tenant. Verified the actual goal — from an unrelated working directory,
with no `sys.path` manipulation and no `AGENTSMITH_DIR`:

```
$ python -c "from runtime.testing import FakeGateway; ..."
gateway call: hello
cross-module import (trace_redactor -> environment) OK: [REDACTED]
```

and the tenant's full suite (35) plus all eight F-scenarios pass against the
installed package alone.

**What this nearly broke, and the lesson:** removing the fallbacks made
`scripts/verify_system.py --check-redaction` fail, which surfaced as
`SEC-PII-002` failing in the *tenant's* strict CI — several `scripts/`
imported runtime modules flat after inserting `runtime/` onto `sys.path`.
That works only while runtime modules don't import each other; the moment
they do, the package root is required. Those scripts now add the repo
**root** and import `runtime.X`. Worth noting the failure showed up two
layers away from the change, in a different repo's compliance gate — the
kind of coupling a packaging change is supposed to eliminate, caught only
because the tenant's security harness was already wired to hard-fail (G5).

#### G7 — No runtime primitives for the two hard judge checks (**Low**) ✅ FIXED

Citation-grounding and pair-parity exist in `run-evals.py` as *offline
eval* suites, but a live app that wants to enforce them per-request writes
them itself (KYC Sentinel's `judge.check_citations` / `check_parity`,
~30 lines). These are the most reusable judge primitives in the framework.

**Fix:** promote both into `runtime/` (e.g. `runtime/judging.py`) and have
`run-evals.py` import them, so the CI gate and the production check are
provably the same logic — the same argument that justified `_shared.py`'s
`DEFAULT_JUDGE_MODEL`.

**Fixed.** `runtime/judging.py` ships `citations_grounded`,
`pair_parity` (the CI shape: result dicts keyed by `pair_id`) and
`parity_violation` (the per-request shape: two outcomes). `run-evals.py`'s
`_pair_parity` now delegates to `judging.pair_parity` — a test
(`test_judging.test_run_evals_delegates_to_the_shared_function`) asserts the
two produce identical output, so the "same logic" guarantee isn't just a
comment. KYC Sentinel's `judge.check_citations` / `check_parity` are now
thin wrappers over the same functions. Tests:
`runtime/test/test_judging.py` (11).

#### G8 — Tenant pipeline steps have no span helper (**Low**) ✅ FIXED

The gateway emitted richly-attributed spans for LLM calls, but a tenant's
non-LLM steps (tool invocations, scrub counts, judge verdicts, HITL
decisions) had no framework way onto a span — and `ToolRegistry.invoke()`
emitted nothing, so the "every tool call streamed to Phoenix" claim was
unmet at the tool layer.

**Fixed.** `runtime/tracing.py` ships `agent_span(name, tenant_id=..., **attrs)`
for tenant steps, and `ToolRegistry.invoke` emits a **child span per tool
call** (`agent.tool.<name>`: allow/deny outcome, duration, error class).

Building the test caught a design bug I'd have shipped otherwise: the first
version *annotated the enclosing step span* instead of creating a child
span. A single research step calls three tools, so they clobbered each
other's `agent.tool.*` attributes and only the last survived — the tenant
test failed showing `adverse_media_search` where it expected
`sanctions_lookup`. Switched to a child span per call, nested under the
active step. Everything no-ops without OpenTelemetry, so a tenant wraps
every step unconditionally. KYC Sentinel's `pipeline.py` now wraps all four
stages; the round-trip is asserted in the tenant's `test_tracing.py`
(step spans + per-tool child spans present). Tests:
`runtime/test/test_tracing.py` (13).

#### G8 — Tenant pipeline steps have no span helper (**Low**)

The gateway emits richly-attributed spans for LLM calls, but a tenant's
non-LLM steps (tool invocations, scrub counts, judge verdicts, HITL
decisions) have no framework-provided way onto a span — the tenant must
hand-roll OpenTelemetry. The observability story is "every token and tool
call streamed to Phoenix", but tool calls through `ToolRegistry.invoke()`
currently emit nothing.

**Fix:** instrument `ToolRegistry.invoke()` with a span (name, args hash,
allow/deny outcome, duration), and expose a small
`runtime/tracing.py:agent_span(name, **attrs)` context manager for tenant
steps.

#### G9 — `PROMPT_GUARD=default` behaves exactly like `strict` ✅ RESOLVED (option C)

Found while wiring G3. `prompt_guard.apply_prompt_guard()` documents three
modes and explicitly promises that **default does not raise**:

```python
# - default: scan; return result (caller may log); does not raise
# - strict:  scan; raise PromptGuardBlockedError when blocked
mode = resolve_mode()
return scan_messages(messages, raise_on_block=(mode == "strict"))
```

It keeps that promise — but the gateway then raises anyway, in both
`complete()` and `complete_stream()`:

```python
pg_result = apply_prompt_guard(messages)
if pg_result.blocked:
    raise PromptGuardBlockedError(...)   # regardless of mode
```

So the two modes are indistinguishable at the only call site that matters,
and `default` — which is the shipped default (`PROMPT_GUARD` unset →
`"default"`) — hard-blocks on heuristic matches. Consequences: the
documented mode contract is false; there is no "observe first" posture for
a tenant rolling out the guard; and a false positive is a hard outage
rather than a logged warning.

**This is not a drive-by fix** — it changes a security control's default
posture, so it needs an explicit decision:

- **(a) Make `default` warn-only** (raise only in `strict`). Matches the
  module's documented contract and gives tenants a safe rollout path; the
  already-wired `CompletionResult.prompt_guard_reasons` starts carrying the
  evidence with no further code change. Weakens the out-of-the-box posture.
- **(b) Keep blocking, fix the docs** (rename the modes, e.g.
  `off | block | strict`), and note that `prompt_guard_reasons` is
  structurally always empty.

A third option emerged while writing this up and is the one taken:

- **(c) Add an explicit `warn` tier and keep `default` blocking.** Modes
  become `off | warn | default(=block) | strict`. No upgrade regression, a
  real rollout path, and `prompt_guard_reasons` becomes meaningful for
  tenants who opt into `warn`.

**Resolved (option C, owner decision 2026-07-21).** Option (a) was rejected
precisely because of the upgrade risk: every deployment on the shipped
default would have silently stopped blocking injections, and — as this
finding also established — the security harness would not have caught it.
Adding the missing tier fixes the false contract without weakening what
ships.

Implemented:

- `PROMPT_GUARD=off|warn|default|strict`, `block` accepted as an explicit
  alias for `default`; unrecognised values still fall back to `default`, so
  a typo cannot disable the guard.
- New `prompt_guard.is_enforcing(mode)` — one definition of "blocking",
  used by both the gateway and the harness runner, so they cannot drift.
- The gateway raises in `default`/`strict` and logs-and-proceeds in `warn`,
  populating `CompletionResult.prompt_guard_reasons`.
- **`SEC-PROMPT-001` now proves enforcement, not just detection** (the
  second half of the same finding — the runner only called `scan_prompt()`,
  so the control reported *Met* regardless of whether anything was blocked).
  Verified end-to-end: `default → pass`, `warn → warn` (fails `--strict`),
  `off → fail`, with the mode recorded in the evidence pack.
- Tests: `runtime/test/test_prompt_guard_modes.py` (17) and
  `scripts/test/test_security_prompt_guard_enforcement.py` (6), including
  an explicit regression guard that an unset `PROMPT_GUARD` still blocks —
  i.e. that option (a) was not taken by accident.
- Docs: module docstring, OPERATIONS prompt-guard section (mode table +
  rollout procedure), SPECS §5.5, `docs/security-framework-map.md`, CHANGELOG.

#### G10 — `MODERATION_HOOK=required` can never pass the harness ✅ FIXED (option a)

Found while flipping the testbed's security CI to hard-fail. The
`moderation_hook` runner calls `reset_output_moderator()` as part of its API
smoke test and then:

```python
if mode == "required":
    return ControlResult(status="fail",
                         message="no output moderator registered (MODERATION_HOOK=required)")
```

That branch is unconditional — the runner has just cleared any registration
and has no way to observe a durable one made in tenant code (a worker
registers its classifier at startup, in a different process from the
harness). So `required` always fails, while `optional` passes.

The consequence is backwards: FIXES_AND_CLEANUP and the P12 notes tell
regulated tenants to `set MODERATION_HOOK=required`, which is exactly the
setting that makes their strict CI un-passable. KYC Sentinel's CI therefore
runs `optional` with a comment explaining why.

**Root cause, stated precisely:** SEC-MOD-001 conflates two different
claims — "the framework's moderation API works" (framework-owned, always
checkable) and "this tenant has a classifier registered" (tenant-owned,
only observable if the tenant declares it somewhere the harness can read).
The runner proves the first and then fails the second by construction.

**Fix options:**

- **(a) Declared hook — recommended.** The tenant commits a dotted path,
  e.g. in `.agenticframework/tenant.yaml`:

  ```yaml
  moderation:
    hook: "agents.moderation:classify_output"
  ```

  Under `required`, the runner imports it, asserts it is callable, and runs
  the same smoke pair it already runs against its own lambda (clean text
  allowed, unsafe text blocked). Pass only if the tenant's *real* classifier
  behaves. This upgrades the control from "the API exists" to "this tenant
  has a working classifier", which is the evidence a regulated tenant
  actually needs — and it makes `required` usable, matching the guidance.

  Worth pairing with: have `runtime/moderation.py` auto-register from the
  same key at startup. Otherwise the declaration and what the worker really
  registers can drift, and the harness would be certifying the wrong thing.

- **(b) Keep the fail, fix the guidance.** Document `required` as a
  deployment-time setting that CI must not use, and correct the P12 /
  FIXES notes. Zero code change and honest, but SEC-MOD-001 then never
  proves anything tenant-specific — the weakest option for the control
  that regulated deployments lean on hardest.

- **(c) Split the control.** `SEC-MOD-001` stays the framework API smoke
  (owner: framework, always passes), and a new `SEC-MOD-002` covers tenant
  registration (owner: tenant, skips when undeclared). Architecturally the
  cleanest — it matches the registry's existing `owner` field, which today
  labels SEC-MOD-001 "Tenant" while the runner mostly tests framework code.
  Bigger change: new control id, registry entry, framework-map row, and
  evidence-pack columns.

(a) and (c) compose: (a) is the detection mechanism, (c) is the
bookkeeping. Whichever is chosen, the runner and the docs must stop
contradicting each other.

**Fixed (option a, owner decision 2026-07-21).**

- `moderation.hook: "module.path:callable"` in
  `.agenticframework/tenant.yaml`, overridable per-deployment with
  `MODERATION_HOOK_PATH`.
- **The runtime loads the same declaration** (`_ensure_declared_moderator()`
  on first use, imperative `register_output_moderator()` still wins). This
  binding is the point: a harness that checked a config key production
  ignored would be certifying the wrong thing.
- The SEC-MOD-001 runner imports the declared hook under `required` and
  smoke-tests **the tenant's own classifier** — it must return a
  `ModerationResult` and must not block benign text, so a block-everything
  stub cannot "pass" the control. A broken declaration fails loudly
  (`ModerationHookImportError`) rather than degrading to a silent skip,
  which would leave a regulated tenant unmoderated while CI looked green.
- `load_declared_moderator()` puts the tenant repo root on `sys.path` before
  importing: a declared hook is tenant code by definition, and the harness
  runs from the framework install, so without this every tenant would have
  had to set `PYTHONPATH` by hand.
- Tests: `runtime/test/test_moderation_declared.py` (12) and
  `scripts/test/test_security_moderation_declared.py` (8).

Verified on the testbed: KYC Sentinel declares
`agents.moderation:classify_output`, and `--mode ci --strict` with
`MODERATION_HOOK=required` now exits 0 with evidence reading *"tenant
moderator declared and verified (agents.moderation:classify_output)"* —
the control now proves something tenant-specific instead of only that the
framework API exists.

Option (c) — splitting into SEC-MOD-001 (framework API) and SEC-MOD-002
(tenant registration) — remains available and is still the cleaner
bookkeeping; it was not needed to make `required` satisfiable.

---

### B. Documentation corrections

| # | Where | Correction |
|---|---|---|
| D1 | `llm_gateway.complete()` docstring | Says `model_hint options: "architect" \| "developer" \| "validator" \| "fast"`. Misleading: `_resolve_role` uses `model_hint` as a direct key into the merged registry, so **tenant-defined roles work** (KYC Sentinel uses `intake`/`research`/`analyst`/`judge` via `tenant.yaml → gateway.routing_overrides`). Reword to "any role defined in the model registry; framework defaults are …". |
| D2 | SPECS §3, §5.5, §16; OPERATIONS TTFT section; CHANGELOG | State the `complete_stream` provider restriction (G1) until it's lifted. |
| D3 | SPECS §29 degrade ladder | Describe actual behavior (one hop) or fix the code (G2) — currently the doc over-promises. |
| D4 | SPECS §25 / tenant guidance | Record the architectural rule the build discovered: **keep domain logic in plain async functions; Temporal activities are thin wrappers.** The determinism sandbox rejects `Path.resolve()` and file I/O at workflow-module import time — the oil-price example knows this (buried in a code comment), but no tenant-facing doc says it. KYC Sentinel's `pipeline.py`/`activities.py` split exists solely because of it, and that split is also what makes every F-scenario runnable without an orchestrator. |

---

### C. Errors in the tenant app (KYC Sentinel's own bugs)

| # | Issue | Status |
|---|---|---|
| E1 | `agents/analyst.py` calls `complete_stream()` with an Anthropic route → guaranteed `NotImplementedError` in real mode (fake mode masked it). This is G1 landing as a live crash. | **Fixed** — provider-aware: stream when supported, else `complete()` with a logged reason. |
| E2 | The Research agent never makes an LLM call (`del gateway`), so the Groq route is only ever reached as a *degrade target*. The spec claims four exercised routes; only three are. | ✅ **Fixed** — Research makes its own `model_hint="research"` screening-summary call; `demo.py f5` shows all four routes used in one run. Degrades to a deterministic brief on failure (the tool findings drive the decision, not the prose). |
| E3 | `tenant.yaml` sets `judge` and `analyst` to the same model id, contradicting RFC-002's judge/actor separation. | ✅ **Fixed** — judge → `claude-opus-4-8`, analyst → `claude-sonnet-4-6`. **Framework gained `runtime.judging.judge_independence_warning`** (a self-grading model inflates scores); the tenant judge logs it if the two ever collapse to one id, with a test forcing that case. |
| E4 | CI security step is `\|\| true` because the tenant `.agent-rfc/security/` pack is incomplete (see G5). | ✅ **Fixed** (with G5/G10) — pack authored with real content; CI runs `--strict` with no `\|\| true`. |

---

### D. What worked (worth preserving)

- **`parse_llm_json` + Pydantic composes exactly right with the recovery
  tiers.** The errors it raises are precisely what `run_with_recoverable_step`
  (F1) and `run_with_self_correction` (F2) consume. No adapter needed.
- **`ToolRegistry` strict + YAML allowlist:** deny-by-default worked first
  try; F4 needed no framework changes.
- **`MemoryVectorStore` + hash embedder:** deterministic RAG in CI with no
  model download — the reason the testbed runs offline.
- **`input_guardrail` counts** were directly usable as compliance evidence
  (the only friction is G3's plumbing).
- **`BaseAgentWorkflow`** delivered HITL/recoverable/self-correction
  without the tenant writing a single signal handler.

---

### Recommended order

1. ~~**G1** (High) — fallback now, Anthropic streaming next; fix D2 with it.~~ ✅ done
2. ~~**G4** (`runtime/testing.py`) — unblocks every future tenant, small.~~ ✅ done
3. ~~**G3** + **G2**~~ ✅ done (D2/D3 docs updated with them)
4. ~~**G9** — decide the prompt-guard mode semantics~~ ✅ done (option C + harness enforcement check)
5. ~~**G5** — one vendoring step; unblocks tenant strict CI.~~ ✅ done
6. ~~**G6** — packaging~~ ✅ done (24 dual-import blocks removed across both repos)
7. ~~**G10**~~ ✅ done (option a: declared hook, runtime-bound)
8. **G7/G8**, then D1/D4 in the next docs pass.

Tenant-side: E1 fixed; E2–E4 tracked in `KYC_Sentinel/DEVLOG.md`.

### Verification (2026-07-21)

| Suite | Before | After |
|---|---|---|
| Framework `scripts/test/` + `runtime/test/` | 170 passed | **252 passed**, 14 skipped |
| KYC Sentinel `test/` | 25 passed | **35 passed** (on the shipped double; + classifier tests) |
| `demo.py all` | 8 controls fire | 8 controls fire |

Also clean: `py_compile` sweep, `check_bare_except.py` on every changed
runtime module, and the SPECS §16 tree drift check.

**Behaviour changes to flag at release** (CHANGELOG [Unreleased] carries
these): `complete_stream` no longer raises for non-streaming providers —
callers gating on TTFT must assert `ttft_ms is not None`; and a
budget-breached call now lands on the first *free* rung of the degrade
chain rather than the next paid one, which changes which model serves a
degraded request.

**Caveat:** `ai-tenant-init` itself was never executed (no machine install
in this environment) — the tenant was bootstrapped by hand, so the
provisioning path remains unverified end-to-end. G5 was found by reading
it, not by running it.

## Observability audit — what AgentSmith emits, and what it does not

*Folded in from `docs/REVIEW_LOG.md` on 2026-09-18.*

**Audited:** 2026-08-24, against `runtime/`, `portal/`, and `templates/agent-rules.yaml` pillar 3.
**Scope:** the production runtime a tenant executes. Where the demo scripts differ, it is called out — the difference is itself a finding.

This is a gap register, not a design doc. Every ❌ is a claim the framework does not currently support; every ⚠️ is one it supports conditionally, with the condition stated. Items fixed during the audit are marked ✅ **fixed** with the commit rationale.

---

### 1. The pillar 3 claim

> *Every span must carry: `agent.name`, `agent.role`, `agent.owner_id`, `tenant.id`, `llm.model_name`, `project.name`, `environment`.*

✅ **Fixed 2026-08-24.** It was not enforced, and half of it was not implemented in
the runtime at all. The table below is the audited state; what replaced it follows.

| Attribute | Production runtime | Demo scripts | Enforced? |
|---|---|---|---|
| `tenant.id` | ⚠️ conditional | ✅ | ❌ |
| `llm.model_name` | ✅ on gateway calls | ✅ | ❌ |
| `agent.role` | ❌ never written | ✅ per span, by hand | ❌ |
| `agent.name` | ❌ never written | ✅ | ❌ |
| `agent.owner_id` | ❌ never written | ✅ | ❌ |
| `project.name` | ❌ never written | ✅ resource + root span | ❌ |
| `environment` | ❌ never written | ⚠️ resource only | ❌ |

`agent.role`, `agent.name`, `agent.owner_id` and `project.name` appear **only** in
`scripts/local_agent_stack.py` and `scripts/multi_agent_system.py` — the demo and dev
harnesses — set by hand on each span. `runtime/tracing.py` and `runtime/llm_gateway.py`,
which is what tenants actually run, never write them.

`tenant.id` is conditional: `runtime/tracing.py`'s `_stamp` writes it under `if tenant_id:`.
Omit the kwarg and the span has no tenant, with no error and no warning. Same in
`record_tool_call`.

**Nothing enforces the contract.** No span processor injects the attributes; no test asserts
callers supply them. `runtime/test/test_tracing.py` asserts `tenant.id == "acme"` *when it was
passed* — that tests the helper, not the pillar. Pillar 3 is in the same position the `SEC-*`
controls were in before their runners were bound: a documented claim with nothing checking it.

#### ✅ Fixed — made structural, not disciplinary

The attributes are split by how they actually vary:

- **Per-process → OTel `Resource`** (`runtime/tracing.py:resource_attributes`):
  `service.name`, `project.name`, `environment`, `agent.owner_id`. Fixed at provider
  construction; every span inherits them and no call site can omit one.
- **Per-step → contextvars + `AgentIdentityProcessor.on_start`**
  (`runtime/tenancy.py`): `tenant.id`, `agent.role`, `run.id`. Bound once at the
  activity boundary; every span started inside — including the gateway's and
  `ToolRegistry`'s — is stamped without anyone passing a kwarg.

`agent.role` **cannot** be a Resource attribute here, and that is the finding rather
than a detail. KYC's worker registers six activities on one task queue, and the
framework's reference worker three; a Resource would stamp every span with one role,
making five of six confident lies. An absent attribute is a gap you can see in a
query — a wrong one is aggregated with real data.

`tenant.id` cannot be one either, for a subtler reason: KYC is `isolation: dedicated`
so it *is* constant per process there, but the framework default is a shared pool
partitioned by tenant (docs/DESIGN.md › Tenancy Model (Independent Repositories)). A Resource attribute would be correct for the
tenant it was built against and silently wrong for every other — which is the
failure mode this framework has already had once, when the security harness graded
its own pack.

**Resolution.** `tenant.yaml` had declared `tenant.id` since the scaffold shipped and
nothing read it — `llm_gateway.py` opens that exact file for
`gateway.routing_overrides` and walked past the id. So callers supplied their own, and
KYC Sentinel ended up with the value in **four** places: two in `agents/gateway.py`,
one as a `getattr` fallback in `pipeline.py`, one in `agents/tools.py`.
`runtime/tenancy.py:resolve_tenant_id()` reads the declaration — explicit argument →
`AGENT_TENANT_ID` → `tenant.yaml` → **raise**. All four copies are deleted.

The refusal is deliberate. `tenant.id` partitions the budget ledger, the audit log and
cross-tenant isolation; an unresolved tenant quietly becoming `unknown` would merge two
tenants' spend and two tenants' audit trail and look fine doing it.

**Not derived from the repo name**, though it was considered and would have worked
here: KYC is single-tenant so its tenant equals its repo. On the shared-pool default
one repo serves many tenants, so a repo-derived id would collapse them; production
containers have no `.git` and no `GITHUB_REPOSITORY`, so it would resolve in CI and
fall back exactly where the audit trail matters; and it would make a compliance
identifier mutable by renaming a directory. The repo name *is* the right default for
`project.name`, where nothing partitions on it — that is where it now lives.

**The runner.** `runtime/test/test_pillar3_conformance.py` asserts the property over
**emitted spans**, not over the helper that emits them. That distinction is what let
the old assertion pass while the contract was broken: it checked `tenant.id == "acme"`
on a call that had just passed `tenant_id="acme"`.

**And the tenant now has tracing at all.** KYC installed no `TracerProvider`, so every
`agent_span()` in the framework's own E2E testbed was a no-op and no span had ever
reached Phoenix from it. `configure_tracing()` is one call that assembles Resource,
identity processor, redactor and exporter; `worker.py` calls it. A documented
three-step recipe had produced zero correct setups.

### 2. User request logging

| Item | Status | Where |
|---|---|---|
| Request ID | ⚠️ `agent_runs.run_id` per gateway call; no ID crossing service boundaries | `llm_gateway.py` |
| Session ID | ❌ no concept | — |
| User query | ⚠️ deliberate — scrubbed by profile | `trace_redactor.py` |
| Timestamp | ✅ `started_at` / `finished_at` | `agent_runs` |
| Model used | ✅ `llm.model_name` | span |
| Token usage | ✅ **fixed** — see below | span + `agent_runs` |
| Latency | ✅ `agent.duration_ms`, run duration | span, `agent_runs` |
| Response status | ✅ `running` / `success` / `degraded` / `failed` | `agent_runs` |

#### ✅ Fixed: token usage was computed and discarded

`CompletionResult` has carried `input_tokens` / `output_tokens` since the gateway was written,
and **not one of the four references reached a span or a database column**. Cost could be
charted but never attributed to a prompt: you could see spend rise and not see which call
caused it.

Now on the span as `llm.usage.input_tokens` / `output_tokens` / `total_tokens`, and persisted
to `agent_runs.input_tokens` / `output_tokens` / `cost_usd`.

**The nullability is the point.** A streamed call reports no usage in v1 and the result
carries `0/0` for it. Writing that `0` would make *"used no tokens"* and *"nobody counted"*
the same number on any dashboard that sums them — undercounting every streamed run while
looking complete. So:

- the span carries `llm.usage.reported` (bool) and omits the token attributes when false;
- the columns are **nullable**, and the ingest route coerces non-numeric input to `NULL`
  rather than `0`;
- the upsert `COALESCE`s, so the run-start write (no usage yet) and a later heartbeat cannot
  blank a figure already recorded.

Also added: `llm.gateway.cost_estimated`. The streamed path bills the `try_reserve()` figure
derived from `max_tokens` — a ceiling, not a measurement — and an estimate must not read like
one.

#### Remaining gaps

**Session ID and a cross-service request ID.** `run_id` is per gateway call. There is no
identifier that survives User → API → worker → portal, so you cannot reconstruct one user
interaction that spanned several calls. This is the same gap as §5.

**User query.** Deliberately absent by default; `trace_redactor` scrubs free text by
`ENVIRONMENT` profile, with a HITL escrow that keeps the full payload for flagged production
spans. That is the right default for a PDPL/GDPR posture. Recommendation: keep it, and
document the escrow as the sanctioned path rather than letting tenants disable redaction to
debug.

---

### 3. Prompt & context logging

**The weakest category, and the one where degradation root-causes actually live.**

| Item | Status |
|---|---|
| System prompt version | ✅ **fixed** — `prompt.system.sha256` |
| Prompt template version | ✅ **fixed** — `prompt.template.id`, chosen at the call site |
| User prompt | ⚠️ redacted by profile; escrowed for HITL-flagged spans |
| Retrieved RAG chunks | ✅ **fixed** — ids and scores, see §6 |
| Conversation history | ❌ `conversation_memory` is untraced |
| Tool outputs | ❌ `record_tool_call` records name / allowed / duration / error only |

`docs/PRODUCT_BACKLOG.md` already records that there is no prompt-template engine and that
prompts are inline f-strings. So there is **no version to log** — the gap is upstream of
observability.

#### ✅ Fixed — hash first, engine later

`runtime/prompt_identity.py` emits `prompt.system.sha256`, `prompt.system.chars`,
`prompt.template.id` and `prompt.message_count`, stamped by the gateway's
`_stamp_llm_span`. The digest is of the system turn, so it changes when and only
when a human edits the prompt; the text itself is never recorded. The redactor
lists `prompt.system.sha256` as untruncatable — a truncated digest silently stops
joining, which is worse than an absent one.

The recommendation as written, kept because it is the reasoning the fix was
built on:

Do not wait for the template engine. Emit `prompt.template.id` (a stable name chosen at the
call site) and `prompt.template.sha256` (of the template *before* interpolation). That gives
you "answers degraded when this hash changed" for near-zero cost, works with inline f-strings
today, and survives the eventual move to a real engine unchanged.

For retrieval, a count is not evidence. `agent.tool.result_count = 3` tells you nothing when
the wrong three came back. Emit chunk **ids and scores** — that is what distinguishes "the
retriever failed" from "the model ignored good context", which is the single most common
question asked of a RAG system.

---

### 4. Agent & tool tracing

| Item | Status |
|---|---|
| Which tool was called | ✅ child span per call, nested under the step |
| Execution time | ✅ `agent.tool.duration_ms` |
| Errors | ✅ `agent.tool.error` |
| Allow/deny outcome | ✅ `agent.tool.allowed` |
| Input / output | ❌ |
| Retry attempts | ✅ **fixed** |
| Decision path | ⚠️ `llm.gateway.degrade_reason` only |

`record_tool_call` is genuinely good on the security axis: recording the **allow/deny
outcome** of an allowlist check is rare and it makes `SEC-TOOL-001` observable rather than
merely asserted.

#### ✅ Fixed — retries are visible

`llm.gateway.attempts` on every call — recorded as 1 when there was no retry, so "this call
did not retry" is a fact rather than the absence of one. A `llm.retry` span **event** per
attempt carries the attempt number, the sleep, and the provider's actual message; a
`agentsmith.llm.retries` counter carries a COARSE reason (`rate_limit`, `timeout`,
`server_error`, `transient`) because a metric attribute holding free text creates a time
series per distinct string.

Driven through tenacity itself in the test rather than a stand-in, so the wiring —
`before_sleep`, the statistics dict, the attribute name — is what is verified.

**Still open:** tool input/output. Redaction applies, so it should route through
`trace_redactor` the same way prompts do rather than adding an unscrubbed channel.

---

### 5. Model performance metrics

| Item | Status |
|---|---|
| Prompt latency / total response time | ✅ span durations |
| First-token latency | ⚠️ `llm.gateway.ttft_ms`, **stream path only** |
| Input / output tokens | ✅ **fixed** (§2) |
| Cost per request | ✅ `llm.gateway.cost_usd`, now flagged when estimated |
| Error rate | ✅ **fixed** — `agentsmith.llm.calls` with an `outcome` dimension |
| Hallucination feedback | ⚠️ offline only — the eval suites; shadow-eval samples spans |
| Cache hit ratio | ✅ **fixed** — `agentsmith.llm.cache` with a `hit` dimension |

TTFT on the non-stream path is unmeasurable without a synthetic first token and is already
documented as such — that one is honest.

#### ✅ Fixed — a meter alongside the tracer

`runtime/metrics.py`. Counters for calls, cache hit/miss and cost; histograms for duration,
TTFT and token counts. Both, not either: spans answer "what happened in this request", and
they are the wrong instrument for "what fraction of requests failed" — that answer is
sampled, expensive to scan, and gets worse as traffic grows. `outcome` is a dimension on the
call counter, so the error rate is a division rather than a scan.

The cache hit ratio was the clearest case: the gateway already knew whether it hit and only
logged it, so no backend could compute the ratio at all.

`configure_metrics()` is separate from `configure_tracing()` on purpose — a deployment can
reasonably want metrics to Prometheus and traces to Phoenix, and coupling them would force
both or neither.

#### ⚠️ → ✅ The correction: none of the above was reaching anything

**Found 2026-08-25.** The section above was true about the instruments and wrong about the
system. `configure_metrics()` **had no caller anywhere** — not `runtime/worker.py`, not KYC
Sentinel's worker, not `examples/oil-price-agent`. Its only three mentions in the repo were
its own definition, its own docstring, and the paragraph immediately above this one.

With no MeterProvider installed, `opentelemetry.metrics.get_meter()` returns a `_ProxyMeter`
whose instruments buffer for a real provider that never arrives. Nothing raises and nothing
logs. So every correctly-placed, correctly-attributed `record_llm_call`, `record_cache`,
`record_retry` and `record_retrieval` wrote into nothing, and the four numbers this section
exists to deliver were computable nowhere — while the section read ✅.

`runtime/test/test_metrics.py` was green throughout because it installs its own
`MeterProvider` and `InMemoryMetricReader` in a fixture. It proves the instruments record
**when a provider exists**; nothing proved one ever did. That is the same pairing that let
pillar 3 pass while unenforced (§1) — a control with no enforcer, and a test of the helper
rather than the contract.

**Fixed:** `configure_telemetry()` installs both providers in one call, with exporters
resolved from the environment, and `runtime/worker.py`, the example worker and KYC's worker
all call it. `runtime/test/test_telemetry_wiring.py` asserts in a **subprocess** that a fresh
process ends up with a real SDK meter and non-proxy instruments — plus a control test that
the same process WITHOUT the call gets proxies, so the assertion is not free — and sweeps
every worker entrypoint for the call itself, because the defect was an absent call rather
than wrong code.

#### ✅ Fixed — one OTLP endpoint resolver, not four

Wiring metrics surfaced a second thing. Four places turned an endpoint variable into an OTLP
URL — `scripts/local_agent_stack.py`, `scripts/multi_agent_system.py`, KYC's `worker.py` and
`portal/lib/tracing.ts` — and only the last was correct. Every Python copy ended
`f"{endpoint.rstrip('/')}/v1/traces"`; the portal's detects a base that already names the path,
because this repo's own convention (docs/UserManual.md, `docker-compose.yml`, docs/DESIGN.md › Installation Procedure,
the then `ai-dashboard-start` shell function) puts a full `…/v1/traces` URL in the variable the OTLP spec defines as a
base. `local_agent_stack.py` falls back to exactly that variable and appended anyway.

The guard was written once, in TypeScript, and the Python sibling reading the same variable in
the same repo never got it — the "fix applied at one call site and not its identical
neighbours" shape, across a language boundary.

`runtime/otlp.py` is the one copy now, ported from the portal's rather than invented fifth. It
also handles a case the portal's could not have: a base naming a DIFFERENT signal, which must
not yield `/v1/traces/v1/metrics`. `portal/lib/tracing.ts` cannot import Python, so the two are
**pinned** by a test that parses the TypeScript for its variable order and its suffix guard
rather than restating them.

---

### 6. Distributed tracing

✅ **Partially fixed 2026-08-25.** It was the largest structural gap: no `inject`,
no `extract`, no `traceparent` anywhere in the codebase.

For the chain your architecture implies:

```
User → API → Orchestrator → Vector DB → Embedding → LLM → Database
```

only the LLM hop is instrumented, and until this audit it was stitched to its parent **only
when the tenant remembered to wrap the call**. The worker's run-status POST to the portal
carries no trace context, so the portal's work is a *separate trace*. `agent_runs.trace_id` is
a manual correlation column, not W3C propagation. `vector_store.query` and `embeddings` emit
no spans at all.

*(All four are now closed — see the two fixed sections below. The paragraph above is left as
written because it is the finding, and a finding that is quietly edited into its own fix
stops being evidence of anything.)*

#### ✅ Partially fixed: an LLM call is no longer absent from the trace

`_record_span_attributes` wrote onto `trace.get_current_span()` behind `if span is None:
return`. `get_current_span()` **never returns None** — with nothing active it returns a
`NonRecordingSpan` whose `set_attribute` is a silent no-op. So the guard never fired, and on
any path not already inside an `agent_span` the entire LLM call vanished from the trace:
model, cost, tokens, latency, all dropped without a signal.

Worth stating precisely, because it shaped the fix: **repairing the guard alone would have
changed nothing** — a no-op write and an early return lose the attributes equally. What
changes it is the fallback. With no parent span the gateway now emits its own `llm.<role>`
span, created with the real `start_time` so its duration is honest. Without a start time it
declines to invent one: a span reading as instantaneous is worse than an absent one, because
it drags every latency percentile computed from it toward zero.

`record_tool_call` deliberately declines to emit lone root spans, and that remains correct —
a step makes several tool calls and orphan roots would be noise. An LLM call is the opposite
case: one per step, and the unit every dashboard is keyed on.

#### ✅ Fixed — the request now survives the process hop

1. **`traceparent` on the run-status POST.** `runtime/tracing.inject_context()` adds the W3C
   header to the worker's call, and `/api/runs/ingest` parses it by hand. That hand parser is
   kept now that the portal *is* instrumented, because it is the one path that still works
   with tracing switched off. An all-zero trace id is the invalid one the spec reserves and is
   rejected rather than stored.
2. **`agent_runs.trace_id` is populated.** It was NULL for every run ever recorded:
   `_report_run_status` accepted a `trace_id` argument that not one of its nine call sites
   passed, so the portal's trace link had nothing to link to. It defaults to the active trace.
3. **The retrieval hop emits spans.** `vector_store.query` (both backends) and the
   sentence-transformers `embed` were entirely invisible, so "the retriever was slow" and
   "the model was slow" were the same picture. Spans carry hit **identities and scores**, not
   just `result_count` — a count of 3 says nothing when the wrong three came back, which is
   the most common question asked of a RAG system. Retrieved TEXT is deliberately excluded:
   it is the likeliest place for PII to enter a span and the redactor runs later.

#### ✅ Fixed — the portal is in the trace, not merely linked from it

The last open item. `agent_runs.trace_id` let a portal row link *to* a trace; the portal's own
work — three Postgres round-trips per ingest, an outbound Phoenix query that can hang for the
full five seconds its `AbortSignal` allows — appeared in no trace at all, including the one it
was serving.

`portal/instrumentation.ts` registers a provider, and that single act does more than add the
spans below: Next.js instruments its own request handling only when a provider is registered,
and it calls `propagation.extract` on the incoming headers before the handler runs. So the
worker's `traceparent` becomes the **parent** of the portal's request span rather than a
string copied into a column.

Verified against a running build rather than asserted — a worker's header in, the exported
OTLP payload out:

```
POST /api/runs/ingest/route   trace=99887766…eeff  parent=1122334455667788   ← the worker's span
  portal.runs.ingest          trace=99887766…eeff  tenant.id=span-proof-3
  portal.db.SELECT            trace=99887766…eeff  tenant.id=span-proof-3
  portal.db.INSERT            trace=99887766…eeff  tenant.id=span-proof-3
```

What that run changed: the first version bound the tenant one block too late, and the trace
showed the SELECT that looks a tenant up and the INSERT that creates it exporting with **no
`tenant.id`** — the two spans that are entirely about a tenant. Identity is now bound at the
first line that knows one.

- **Every query is traced, without a call site opting in.** `lib/db.ts` returns a pool whose
  `query` opens a span, rather than a helper the twenty-eight existing call sites would each
  have to remember. `db.statement` carries the *parameterised* text — code, not data — and the
  values are never recorded: unlike the worker's spans, nothing redacts a portal span. The
  callback and Cursor forms of `pg.query` return something other than a promise and are passed
  straight through untraced, rather than silently changing what a caller gets back.
- **Pillar 3 holds on the portal too**, split the same way: `service.name`, `project.name`,
  `environment` and `agent.role: ops-portal` on the Resource; `tenant.id` and
  `portal.actor.role` stamped per span by `PortalIdentityProcessor` from the active context.
  `portal.actor.role` is the human's RBAC role and is deliberately *not* called `agent.role` —
  an operator is not an agent, and one attribute meaning two things is pillar 15.
- **An operator action is attributable.** `portal.dlq.replay` and `portal.dlq.discard` record
  which role acted on which entry. The replayed payload is not recorded: it is operator-edited
  tenant data on its way to a tenant's webhook.
- **The endpoint trap.** This repo's own convention sets `OTEL_EXPORTER_OTLP_ENDPOINT` to a
  full `…/v1/traces` URL — fine for the Python exporter, which is handed it directly. The JS
  exporter appends `/v1/traces` to what it is given, so the same value everything else here
  uses would have POSTed to `/v1/traces/v1/traces` and dropped every span on a 404 that
  surfaces nowhere. `resolveTracesEndpoint()` detects the suffix instead of assuming it.

**Still open:** a collector fan-out (Phoenix for LLM semantics, Tempo/Jaeger for infra search)
is now possible but not configured — both sides currently export to one endpoint.

---

### 6a. Two coupling surfaces, and only one was versioned

**Added 2026-08-26.** Everything above treats AgentSmith and a tenant as one
system. They are not: they have different owners and different release cadences.
IT operations ships the framework and this portal; the business ships the tenant
app and pins a framework version so IT's releases cannot move underneath it.
That separation is the design — the pin is what makes it work — and it has a
consequence the audit had not accounted for.

There are two coupling surfaces:

- **The library surface** — `runtime/` imported into the tenant's own process.
  The pin governs it, the compatibility matrix tracks it, the business upgrades
  on its own schedule. Fine.
- **The wire surface** — span attributes, the run-status POST, `agent_runs`
  columns, `dlq_entries`, the replay webhook. This is what actually delivers the
  monitoring in §§1–6. IT upgrades it unilaterally. It carried **no version at
  all**.

So the portal could not tell which telemetry shape it was reading. A tenant
pinned to v1.2.0 emits no `prompt.system.sha256` (no `prompt_identity`), no
metrics (no `metrics.py`), and `tenant.id` only where a caller remembered the
kwarg (no identity processor) — in `agent_runs` a NULL, which is the same NULL a
current tenant writes when its provider reported no usage or its exporter is
misconfigured. One value, two meanings, on the product whose users are IT ops.
Pillar 15, at fleet scale.

`framework.version` was declared in `.agenticframework/tenant.yaml` and read by
nothing — the same shape as `tenant.id` and `budget.monthly_usd_cap` before those
were closed. It could not have answered this regardless: what matters is the
version of the code that is RUNNING, not the one the repo says it wants.

#### ✅ Fixed — the version is on both wires, and it means something

`agentsmith.framework.version` on the OTel **Resource**, and `frameworkVersion`
on the run-status POST into a nullable `agent_runs.framework_version`.

The Resource is the correct home for this one, and §1 argues the opposite for
its neighbours — deliberately. `agent.role` and `tenant.id` vary *within* one
worker process, so a Resource would make most spans confident lies. The
framework version is fixed for the life of the process. That is the whole test,
and it is the only pillar-3-adjacent attribute that passes it.

**A source checkout reports `1.2.0+src`.** `AGENTSMITH_DIR` — how tenant CI and
local development run — puts a checkout on `sys.path` whose `pyproject.toml`
still names the last release while `main` runs far ahead. This working copy
reports `1.2.0+src` while carrying two dozen unreleased changelog sections; a
bare `1.2.0` would be a confident lie of exactly the kind the version exists to
prevent. `+src` is SemVer build metadata, orders equal, and says the number does
not bound what the process contains.

**`portal/lib/wireContract.ts` turns the version into an answer.** `emits()`
returns **yes / no / unknown** — three states, because two is how this codebase
keeps producing this defect — and `explainAbsent()` renders *"not reported by
AgentSmith 1.2.0"* where the version is the reason, and stays **silent** where
the absence is a genuine fault the caller must speak to in its own words.
`unknown` covers a `+src` build and an unparseable string, which are neither.

The ingest route accepts a version it has never heard of. A tenant ahead of the
portal is ordinary when the business upgrades first, and rejecting it would
silence exactly the tenants whose shape the portal most needs to know.

The tenant list now carries an **AgentSmith** column and a fleet count, with the
same three states: a version, `< 1.3.0` for a tenant whose runs carry none, and
`—` for a tenant that has never reported a run. The third is not the second — no
runs is not an old framework.

**The contract is written down**, as a *Wire Contract* table beside the
compatibility matrix in `CHANGELOG.md`: which field each version emits, so IT
knows what it must keep accepting and for how long. That table is what makes
"IT upgrades freely" true rather than hoped-for.

**Still open:** the same treatment for `dlq_entries` and the replay webhook.
`portal/lib/dlq.ts` already probes for the `reason` column at runtime, which is
the right instinct arrived at ad hoc — it should read from the wire contract
instead of asking the database what shape it is.

---

### 7. Tooling posture

You are OTel-native with Phoenix, and that is the right spine.

| Tool | Verdict |
|---|---|
| **OpenTelemetry** | ✅ keep as the wire format. Everything below should feed it, not replace it. |
| **Phoenix (Arize)** | ✅ right for eval, hallucination analysis and trace inspection. The shadow-eval loop already feeds it. |
| **LangSmith / Langfuse** | ⚠️ not recommended *alongside* OTel. Both bring their own span models; adopting one means two vocabularies and a lossy bridge. Choose them instead of OTel or not at all. |
| **MLflow Tracing** | ⚠️ overlaps Phoenix. No reason to run both. |
| **Prometheus / Grafana** | ✅ metrics now exist AND are exported — `configure_telemetry()` installs a MeterProvider and resolves `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`. Point it at a collector that fans out to Prometheus; no second instrumentation. |
| **Datadog / Azure Monitor** | ⚠️ viable as an OTLP sink if the org already pays for one; not a second instrumentation. |
| **Jaeger / Tempo** | ⚠️ only after §6 propagation exists, and via collector fan-out rather than double instrumentation. |

---

### Priority

1. ~~Enforce pillar 3~~ ✅ done — Resource + `on_start` processor, `resolve_tenant_id()`,
   a conformance test over emitted spans, and a tenant that installs tracing at all.
2. ~~Fix the dead span guard~~ ✅ done — and the fallback that makes it matter.
3. ~~Token capture~~ ✅ done, span and database, with "not measured" preserved.
4. ~~Context propagation~~ ✅ done — `traceparent` injected and parsed, `trace_id`
   populated, retrieval and embedding spans emitted.
5. ~~Prompt hash~~ ✅ done — `prompt.system.sha256`, `prompt.template.id`,
   `prompt.system.chars`, `prompt.message_count`, with the digest untruncatable.
6. ~~OTel Metrics~~ ✅ done — counters and histograms for the rates and ratios, **and a
   provider that makes them leave the process.** The instruments landed first and were
   proxied into nothing for as long as no entrypoint called `configure_metrics()`; see the
   correction in §5. One `configure_telemetry()` installs both signals, and one
   `runtime/otlp.py` resolves both endpoints for all four callers that used to do it
   separately.
7. ~~Retry visibility~~ ✅ done — `llm.gateway.attempts`, a span event per retry carrying the
   provider's message, and a counter with a bounded reason.

---

*Fixed items are covered by `runtime/test/test_gateway_span_usage.py` (span attributes,
including that unreported usage is absent rather than zero),
`portal/test/agentRuns.test.ts` (persistence, including that a later write carrying no usage
does not blank a recorded figure), `runtime/test/test_pillar3_conformance.py` (§1, asserted
over emitted spans rather than the helper), `runtime/test/test_telemetry_wiring.py` (§5, that
a fresh process ends up with a real meter and not a proxy) and
`runtime/test/test_otlp_endpoint.py` (the single endpoint resolver, pinned against the
TypeScript copy it cannot import). All run in CI.*
