# Review: accountability-chain

Gap 2 of `docs/PRODUCT_BACKLOG.md`, after the owner's instruction of 2026-11-09 to fix the gaps.

## Pass 1 — findings: 2

Against `docs/review-levers.md`.

1. **Nothing held the gateway to sending the commit.** The model and reader were tested, and the one line that connects them was not. Fixed: `test_the_gateway_sends_the_commit_with_each_run`, proven by removing that line.
2. **A short hash from a run would not have found its commit.** The count compared for equality. Fixed: `$2 LIKE app_commit || '%'`; the value is hex by then, because the ingest refuses anything else. The commit page already resolves a short hash in its URL.

## Pass 2 — findings: 0

- Python: `scripts/test/test_app_commit.py` 20 passed; the Ops contract, telemetry, environment-variable, workflow-wiring, gate-table and repository-tree suites pass.
- Portal: `npm test`, `tsc`, a production build, and the whole `test:db` lane against a throwaway Postgres, with `schema.sql` applied twice to prove it is re-runnable.
- Nine hand mutants, all caught: any value read as a commit; the contract or the portal taking anything; the gateway not sending it; the trace omitting it; the deploy not setting it; a later report blanking it; another app's runs counted; a short hash unmatched.
- On a production build against seeded data, the Ops page lists runs with links, a short hash redirects to the full commit, a run with none says "not reported", and the commit page counts its runs and links back.

Not proven until a real deployment carries it: the tenant's deploy step has to pass `APP_COMMIT` to the running app. The manual says so, and a run without it says "not reported". Recorded on the backlog against Stage 2.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one reader, `version.app_commit`, used by the gateway, the trace resource and the compliance record.
Group 2 · Quality / safety — [x] checked — a hash pattern on both sides of the contract; nothing else reaches a link or query.
Group 3 · Architecture / hygiene — [x] checked — additive everywhere; the deprecated route is unchanged.
Group 4 · Process — [x] checked — design first; CHANGELOG, manual, backlog, and both contracts updated.
Group 5 · Intuitive UI — [x] checked — rendered on a production build against seeded data; a table with an overflow wrapper at phone width, and "not reported" distinct from a commit.
Group 6 · Signal integrity — [x] checked — a missing commit is NULL and shown as that; a value that is not a hash is refused rather than stored.
Group 7 · Auth & session integrity — [x] checked — the Ops token still alone decides whose run it is; a run's commit cannot name another app, and counts are per app.

Tests added: `scripts/test/test_app_commit.py`; six cases in `portal/test/opsIngestDb.test.ts`; two in `contract/ops/v1/cases.json`.
Mutation-checked: yes, by hand; nine mutants, all killed.
Fixtures re-pinned: `contract/ops/v1/message.schema.json`, `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; mypy; `tsc`; the portal build; the process gate against the commit.

Levers reviewed: `implemented-not-invoked`, `failure-is-not-a-result`, `test-that-cannot-fail`.

KG query: kg:1107dc4c2c95
