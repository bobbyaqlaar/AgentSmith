# Review: portal-compliance-holds

## Pass 1 — findings: 2

Against `docs/review-levers.md`, after the fixes.

1. **The requester's trim was untested.** A mutant that dropped `trim()` survived: the test's padded value failed the email pattern either way, so it read "nobody may decide" with or without the trim. Added a case where trimming decides the answer (another reviewer may decide a padded requester's request).
2. **A sibling the review did not name: the sidecar took any `requested_by`.** The workflow path now refuses one that is not an email, and the sidecar's `/v1/gate/request` did not. It now answers 400 with the reason; two tests.

## Pass 2 — findings: 0

- `npm test` (26 files, the three that were never run among them) exits 0; `npx tsc --noEmit` is clean. Each new portal test fails on `origin/main`'s code: the checklist (4 of 17), the lockout, the queue (the export did not exist), the scripts check (2), the controls helper (missing).
- `scripts/test/test_compliance_port.py`, `scripts/test/test_compliance_checks.py` and `agentsmith/test/test_compliance_runtime.py`: 141 passed, 7 skipped without `COMPLIANCE_TEST_DSN`.
- 14 hand mutants (`complianceState` 4, `signInPolicy` 2, `hitl` 1, `submitOnce` 3, `compliance_port` 2, `runtime_server` 1, plus the trim mutant rerun), all killed.
- The controls are React components with no component test harness in the portal; their logic is in `lib/submitOnce.ts`, which is tested, and `tsc` checks the components and the page's new prop. Not clicked in a browser: the portal needs a database and a session to render the app page.
- Decided, not done: `OB-AUDIT-COVERAGE` now fails in AgentSmith's own evidence, because it cites a route, and ESLint is not added. Both are open in the backlog.
- `npm run test:db` was not run (it needs Postgres); `PENDING`'s new condition is held by a text test and was read against `db/schema.sql` (`compliance_records.record_id`).

## Sign-off

Group 1 · DRY & shared code — [x] checked — one `submitOnce` for both controls; `expiresAt` mirrors the port's `expires` and says so.
Group 2 · Quality / safety — [x] checked — no lock is ever evicted; nobody decides a request whose requester cannot be compared.
Group 3 · Architecture / hygiene — [x] checked — a dead script removed; tests every script runs.
Group 4 · Process — [x] checked — design first; manual and CHANGELOG updated.
Group 5 · Intuitive UI — [x] checked — one action shown, its busy label, a confirmation for a stop and a rejection, an error that says the action did not happen.
Group 6 · Signal integrity — [x] checked — `release:` evidence must be a test CI runs.
Group 7 · Auth & session integrity — [x] checked — the lockout holds at the cap; self-approval cannot slip through a non-email requester.

Tests added: `portal/test/hitl.test.ts`, `portal/test/submitOnce.test.ts`, `portal/test/scripts.test.ts`; cases in `complianceState.test.ts`, `signInPolicy.test.ts`, `scripts/test/test_compliance_port.py` and `agentsmith/test/test_compliance_runtime.py`.
Mutation-checked: yes, by hand; 14 mutants, all killed.
Fixtures re-pinned: `portal/package.json` scripts; `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; `npm test`; `tsc`; the knowledge-graph check; the process gate against the commit.

Levers reviewed: `declared-vs-enforced`, `guards-must-be-able-to-fail`, `out-of-order-and-repeated`, `implemented-not-invoked`, `gate-integrity`, `run-the-gates-ci-lists`, `no-double-submit`, `irreversible-needs-confirmation`, `failure-is-not-a-result`, `validate-on-the-receiving-side`, `docs-match-behaviour`.

KG query: kg:60da23be1df9
