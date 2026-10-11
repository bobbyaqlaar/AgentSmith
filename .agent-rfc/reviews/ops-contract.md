# Review — ops-contract (C8)

Design: `.agent-rfc/designs/ops-contract.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 4

Over the whole branch after the build, each finding verified in code before it was changed.

1. **The deprecated history route could still redirect another tenant's replays** (`channel-precedence`,
   `declared-vs-enforced`). It stopped storing a secret, but still set `replay_webhook_url` for
   whichever tenant its body named, under the one token every tenant shared — so any holder could
   point another app's replays, a person's fix signed with that app's key, at an address of its
   choosing. It sets no URL now: the URL is the app's own to declare, with its own Ops token. A test
   drives the route itself (the test loader learned the portal's `@/` alias and Next's subpath files).

2. **A long error summary dropped the whole run report** (`failure-mode-visibility`). Over the
   contract's 4,000 characters the message failed validation, and the gateway logged that at debug —
   the run simply never reached the portal. The summary is bounded to the limit, and a report that
   still cannot be built is warned about once.

3. **The dead-letter table statement ran on every insert** (`every-line-earns-its-place`): a no-op
   `CREATE TABLE IF NOT EXISTS` still takes a brief lock, and concurrent reports would queue on it —
   the lesson `runtime/pg_pool.ensure_schema` already learned. Once per process now.

4. **The portal's "not configured" replay error still asked for a secret** (`docs-match-behaviour`):
   it now names the two things a replay needs — the worker's declared URL and the issued key — and
   the manual's heading that describes them.

## Pass 2 — findings: 3

Following pass 1's first finding to its siblings — every writer of where a fix is sent and what it is
signed with (`grep-for-siblings`).

1. **The replay key had a second, unaudited writer.** `POST /api/tenants` let a signed-in operator set
   `replayWebhookSecret` directly, beside the audited issue in Administration › Apps. A body carrying
   one is refused there now (400, naming where the key is issued).
2. **`upsertTenant` still took a secret** — only a test passed one. The parameter and its column are
   gone from it; the key's one writer is `setReplayWebhookSecret`, through `issueReplayKey`, and the
   type check holds every caller to that.
3. **The CHANGELOG overstated what the deprecated routes still allow** (`docs-match-behaviour`): until
   an operator unsets the shared token, `/api/runs/ingest` still lets a holder add runs under any
   tenant (never overwrite another's) and `/api/sync/history` set a display budget cap. Said there and
   in the portal README's API table, which also gains the Ops ingest and the two admin routes.

## Pass 3 — findings: 1

Over pass 2's fixes, and what an Ops token can now change on its own.

1. **A changed replay URL left no trace** (`failure-mode-visibility`). The app's own Ops token now
   decides where a person's signed fix is sent; a token that leaked could move it with nothing
   recorded. `updateTenantSettings` audits a change of the URL — from and to, actor `app:<id>` — in the
   same transaction as the change; resending the same URL records nothing. Tested both ways.

## Pass 4 — findings: 2

The full suite on the staged tree (`run-the-gates-ci-lists`) — 2406 passed, 2 failed — over what the
retirement left behind.

1. **The records still name the retired mode.** `test_docs_do_not_reference_an_unknown_check_mode`
   flagged `verify_system.py --check-history-sync` in the CHANGELOG, the archive and two earlier
   designs — accurate history, not instructions. A retired mode may be named in those records only
   (`_RETIRED`, `_HISTORY`), and a second test holds that it is really gone from the script; anywhere a
   reader is told what to run, it is still flagged.
2. **The live-portal job's two new setup steps carried no gate tag** (`test_every_blocking_check_…`):
   starting the portal and seeding the token are setup, not checks — listed in `_SETUP_STEPS` in place
   of the history-sync start step they replace.

## Pass 5 — findings: 0

Over pass 3's audit and pass 4's two fixes, and the branch once more: the replay URL change is audited
inside the settings transaction and rolls back with it; the retired-mode excuse is scoped to records
and conditional on the mode being gone; the setup steps run nothing a gate would. No further finding.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one sender (`runtime/ops_contract.send`) for run status, dead letters and settings; the Ops ingest writes through the stores that already existed (`upsertAgentRun`, `dlq_entries`, tenants); one route factory for both token scopes and one credential panel for all three kinds; the message and replay schemas generated from the models; the dead-letter DDL's two copies held equal by a test.
Group 2 · Quality / safety — [x] checked — 21 tests in `test_ops_contract.py`; portal `opsContract.test.ts` (27) and `opsIngestDb.test.ts` (13); conformance: AgentSmith's sender 5/5, the live portal 26/26, its replay webhook 4/4, and senders that follow a redirect or carry the secret shown failing; 7 mutations in `ops_contract`, all caught.
Group 3 · Architecture / hygiene — [x] checked — no dependency added; a tenant needs no share of the portal's database; the deprecated shared-token routes stay for deployed runtimes, narrowed, until an operator unsets the token.
Group 4 · Process — [x] checked — design before code, the owner's four decisions recorded, amended seven times while building; five review passes; backlog C8 Built and the evals-data feature logged; archive entry; CHANGELOG (Added, Security, Deprecated, Removed, Wire Contract); README ports table; portal README API table; User Manual; DESIGN; the validation checklist's gate table regenerated; protocol declared as reference documentation.
Group 5 · Intuitive UI — [x] checked — Administration › Apps shows an Ops token and a replay signing key beside the ingest token, each issued once with where to put it, rotation confirmed before it breaks anything; the portal's replay error names the two steps a replay needs.
Group 6 · Signal integrity — [x] checked — the token decides the tenant; an id another app holds is 409, never written over; a worker's report fails open and says so once; a CI sender fails on configuration and warns on an outage; the deprecated routes' remaining reach is stated, not hidden.
Group 7 · Auth & session integrity — [x] checked — one credential per channel (CI token, Ops token, replay key), scoped so none stands in for another; no secret in a message or in tenant.yaml; the replay key has one audited writer; a changed replay URL is audited; neither sender nor replay follows a redirect.

Tests added: `scripts/test/test_ops_contract.py` (21); `portal/test/opsContract.test.ts`, `portal/test/opsIngestDb.test.ts`; the replay-redirect test in `dlqCostWidget.test.ts`; the budget-key test moved onto the settings sender; the retired-mode tests.
Mutation-checked: `ops_contract` 7/7.
Fixtures re-pinned: `contract/ops/v1/` new (fixture, cases, schemas); `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` on the staged tree (2410 passed, 10 skipped); portal `npm test`, `npm run test:db` against a throwaway Postgres 16, `npx tsc --noEmit`, `npm run build`; `ruff check .`; `mypy` (1.14.1); the repo-tree check; py_compile; redaction for both profiles; `--check-hooks`; `--check-kg`; the delivery evidence pack; the Ops receiver conformance against the built portal, as the self-test runs it.

Levers reviewed: `declared-vs-enforced`, `channel-precedence`, `two-owners-two-cadences`, `single-source-of-truth`, `test-the-contract`, `implemented-not-invoked`, `failure-mode-visibility`, `grep-for-siblings`, `docs-match-behaviour`, `every-line-earns-its-place`, `run-the-gates-ci-lists`.

KG query: kg:a72fc35fa3da
