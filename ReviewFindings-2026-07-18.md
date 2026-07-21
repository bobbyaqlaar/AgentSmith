# Docs ↔ Code Sync & Code Quality Review — 2026-07-18

**Method:** automated cross-reference of every file path, `ai-*` command, and CLI flag
cited in README / UserManual / OPERATIONS / SPECS / CHANGELOG / FIXES / docs/ against
`git ls-files` and actual argparse definitions; duplicate-function scan across
`scripts/` + `runtime/`; perf-pattern scan of hot paths (gateway, hooks, portal);
`py_compile` sweep and fixtures JSON validation (both pass clean).

## Verified in sync (no action needed)

All 15 `ai-*` shell commands in docs exist in `install-ai-stack.sh` and vice versa.
All `verify_system.py --check-*`, `run-security-checks.py`, and `run-evals.py` flags
cited in docs exist in code. Git hygiene is good: no build artifacts tracked
(`.next`, `.venv`, `node_modules`, `*.tsbuildinfo`, `.DS_Store` all ignored). The
installer copies `scripts/` rather than embedding heredocs, so no installer/repo
duplication. Portal uses a shared pg pool and `Promise.all` on the dashboard.
`scripts/_shared.py` consolidation exists and the scripts↔runtime duplication
boundary is documented as deliberate. On-prem doc references to `scripts/up.sh`
etc. are correct (they refer to the rendered tenant `deploy/onprem/` tree).

## A. Doc ↔ code drift

| # | Severity | Finding |
|---|---|---|
| A1 | Medium | `runtime/agent_logger.py` cited in **OPERATIONS.md:1628** and **templates/onprem-deploy/README.md** (item 4) — the file is `scripts/agent_logger.py`. No runtime copy exists. |
| A2 | Medium | **SPECS.md §16 Repository Structure** claims to be "the only copy" but omits P12+ artifacts: `runtime/` is missing `environment.py`, `moderation.py`, `prompt_guard.py`, `provider_dispatch.py`, `structured_output.py`, `tool_registry.py`, `requirements-runtime.txt`, `test/`; `scripts/` is missing `_shared.py`, `check_bare_except.py`, `delivery_evidence.py`, `delivery_model.py`, `eval_judge.py`, `run-security-checks.py`, `security/`, `shadow-eval.py`, `sync-portal-history.py`, `test/`; `fixtures/` is missing `security/`; `docs/` is missing `security-framework-map.md`, `team-observability.md`, `session-handoff/`; `.agent-rfc/` is missing `security/`. The self-test CI only diffs top-level entries, so sub-tree drift accumulates silently — exactly what happened. |
| A3 | Medium | **SPECS.md §5.4** is stale vs P12: `run-evals.py` row lists suites `golden, fairness, hallucination` (missing `adversarial`, which the code and CHANGELOG ship); `verify_system.py` row lists 7 CI flags (missing `--check-security` and `--check-delivery-model`, both implemented). The §16 tree's `run-evals.py` comment has the same missing-suite issue. |
| A4 | Low | **SPECS.md §5.5** runtime inventory lists only 6 of ~20 runtime modules. It defers to §25, but as an "inventory" it no longer inventories — either complete it or demote it to a pointer. |
| A5 | Low | `scripts/security/runners/moderation_hook.py` is the only source file not named anywhere in the docs (referenced only via `control_registry.json` runner id). One line in `docs/security-framework-map.md` SEC-MOD-001 row fixes it. |

## B. Redundant code

| # | Severity | Finding |
|---|---|---|
| B1 | Medium | `_luhn_valid` has **two divergent implementations inside `runtime/`**: `input_guardrail.py` strips all non-digits (`\D`); `trace_redactor.py` strips only spaces/hyphens then requires `isdigit()`. A card number with unusual separators can be caught pre-call but survive post-call redaction (or vice versa). Same package — no vendoring boundary excuse; unify into one helper with the more permissive normalization. |
| B2 | Low | `_load_sync_state` / `_save_sync_state` copied byte-for-byte in `shadow-eval.py` and `sync-portal-history.py` (variant defaults in `sync-ui-feedback.py`) despite `scripts/_shared.py` existing precisely for this. |
| B3 | Low | `_load_dotenv` duplicated in `run-evals.py`, `verify_ttft.py`, `verify_sovereign_endpoint.py` — move to `_shared.py`. |
| B4 | Low | `run-security-checks.py` defines its own `_repo_root` while sitting in the same directory as `_shared.py` which exports it. |

## C. Performance

| # | Severity | Finding |
|---|---|---|
| C1 | **High** | `runtime/llm_gateway.py` `_PostgresBudgetBackend` opens a **fresh psycopg2 connection per operation** (`try_reserve`, `add_spend`, `get_spend`) — 2–3 TCP+auth round-trips added to **every LLM call** in the hottest path of the runtime. `idempotency.py` and `dead_letter.py` use the same connect-per-call pattern. SQL atomicity is correct; only pooling is missing. |
| C2 | Medium | `map_codebase.py` re-parses the **entire** repo AST on every commit and checkout (post-commit + post-checkout hooks). It already records per-file `mtime` but never uses it to skip unchanged files. The FIXES "cherry-pick, don't rebase" lesson is a symptom of this cost. |
| C3 | Low | `portal/lib/issues.ts` `syncHistoryEntries` awaits one INSERT per entry; batch into a single multi-VALUES statement (input is bounded, so low impact). |
| C4 | Low | `sync-ui-feedback.py` persists `synced_span_ids` as an ever-growing JSON list re-loaded each run; cap it or key off `last_sync` timestamp. |

## D. Hygiene

| # | Severity | Finding |
|---|---|---|
| D1 | Low | `.claude/settings.local.json` is untracked and not gitignored (shows in `git status`). Add to `.gitignore` (`.claude/settings.json` stays tracked). |
| D2 | Info | Local disk: `.venv` 1.7 GB, `portal/.next` 155 MB, `portal/node_modules` 286 MB — all correctly ignored; prune only if disk pressure. |

## Action plan

**P1 — this week (correctness/perf in production path)** ✅ DONE 2026-07-21
1. **C1 ✅:** `runtime/pg_pool.py` — per-DSN `ThreadedConnectionPool` with ping-validated borrows, pool-exhaustion fallback to direct connect, and a proxy whose `close()` releases to the pool (so every existing `finally: conn.close()` call site stayed untouched; only the three `_connect` methods changed). `PG_POOL_MAX` env (default 5). Tests: `runtime/test/test_pg_pool.py` (fake psycopg2, no live DB).
2. **B1 ✅:** `runtime/luhn.py` — single `luhn_valid` (strips all non-digits), imported by both `input_guardrail.py` and `trace_redactor.py`. Tests: `runtime/test/test_luhn_parity.py` incl. an identity assertion so the two controls can never drift again. Full `runtime/test/` suite: 71 passed, 13 skipped (pre-existing optional-dep skips).

**P2 — next docs pass (drift removal)** ✅ DONE 2026-07-21
3. **A1 ✅:** `runtime/agent_logger.py` → `scripts/agent_logger.py` in OPERATIONS.md and templates/onprem-deploy/README.md.
4. **A2/A3/A4 ✅:** SPECS §16 tree updated (P12 runtime/scripts/fixtures/docs entries + new `pg_pool.py`/`luhn.py` + this file); §5.4 gained rows for the 10 undocumented scripts, the `adversarial` suite, and both missing `verify_system` flags; §5.5 now inventories all runtime modules. `self-test.yml` drift diff extended to second-level entries of `scripts/`, `runtime/`, `docs/`, `fixtures/` (verified locally: 31 top-level + 64 second-level entries pass; the old check was top-level-only, which is exactly where P12 drifted).
5. **A5 ✅:** `scripts/security/runners/moderation_hook.py` named in the SEC-MOD-001 evidence column.

**P3 — opportunistic cleanup (low risk, do alongside other changes)** ✅ DONE 2026-07-21
6. **B2/B3 ✅:** `_load_sync_state`/`_save_sync_state`/`_load_dotenv` now live in `scripts/_shared.py`; local copies deleted from all 6 consumers. **B4 ✓ (amended):** `run-security-checks.py`'s `_repo_root` turned out to be a *false* duplicate — file-relative (install location), not cwd-relative like `_shared`'s — so it was renamed to `_install_root()` with the rationale documented instead of being swapped.
7. **C2 ✅:** `map_codebase.py` skips files whose stored `last_modified` matches current mtime (also eliminating the per-upsert graph save each node triggered); `AGENT_KG_DEFER=1` guard added to both hooks. Verified in a scratch repo: full parse → all-skip → single re-parse on touch → purge on delete. FIXES lesson updated (rebase is safe with the guard).
8. **C3/C4/D1 ✅:** `syncHistoryEntries` batches into chunked multi-VALUES upserts (with in-batch dedupe, since ON CONFLICT rejects same-key twice per statement); `synced_span_ids` bounded to newest 5000; `.claude/settings.local.json` gitignored. Verification: 125 Python tests + 7 portal tests pass, `tsc --noEmit` clean, hooks `bash -n` clean, `check_bare_except` clean.

**Not run here:** the pytest/vitest suites (host `.venv` is macOS-native; sandbox is Linux). Run `pytest` + `npm test` in `portal/` after P1 changes.
