# Review: vector-ids-per-tenant-and-stop-state

Each fix has tests that fail without it. P2-R17, in `agentsmith/test/test_compliance_runtime.py`: the id space on the
profile, ids returned as the app wrote them, ids unchanged off the profile, a refusal that does not say whose the id
is, the claim against a real Postgres table (rows with no tenant, this tenant's unprefixed rows, another tenant's row
left alone, an id the tenant already holds skipped, and the `vector_claim` record), and `ops vector-claim` asking
before it moves anything. P2-R19, in `portal/test/hitl.test.ts`: the app's record decides the state; a newer portal
action reads "sent"; a stop the app refuses is not audited.

## Pass 1 — findings: 2

Against `docs/review-levers.md`, by hand mutants (ten), with `COMPLIANCE_TEST_DSN` set against Postgres 16.

1. **The id space could leak off the profile with no test noticing.** The off-profile test used no tenant; an app
   off the profile can still have one. Parametrised over both.
2. **A mutant hung instead of failing.** Running the claim on one connection and its record on another made the
   second wait on the first's row lock, and the runner had no timeout. The mutant was stopped, the file restored by
   hand and checked against every mutant's original text, and the runner now times out at four minutes, counting a
   timeout as killed. That shape (a record outside the change's transaction) is already pinned by P2-R16's database
   tests through `_recorded_change`, which the claim uses.

## Pass 2 — findings: 0

- Nine mutants again (no id space; the id space off the profile; the prefix not stripped; the claim overwriting an id
  already held; the claim taking other tenants' rows; `vector_claim` not reserved; the portal's own action deciding the
  state; "sent" ignoring time; the post outside the audit's transaction): all killed.
- `agentsmith/test` with the database: 919 passed, 10 skipped. Portal `npm test`: exit 0; `tsc`: clean. ruff and mypy
  1.14.1: clean. The stop-state queries ran against the portal schema in Postgres with a terminal stop recorded.
- Siblings: `query` is the only read and strips only this tenant's prefix; the in-memory store keeps one process's
  documents and has no tenants to separate. The R25 guard stays as a second line with a neutral message.
- Not run: the upsert against pgvector (no pgvector image here; pulling one is a download not yet agreed). The claim
  touches only `id` and `tenant_id` and ran against a real table; the upsert's statement is unchanged apart from the id
  it is given.
- Limits, stated: the prefix lives in the stored id, so a tenant id containing `:` would read oddly; tenant ids are
  limited to `[a-z0-9-]` by the portal's `APP_ID`. "Sent" compares two portal times (the action, and when the record
  arrived), so the app's clock never enters it.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one id rule for write and read; the claim reuses `_recorded_change`; the stop send mirrors `decideGate`.
Group 2 · Quality / safety — [x] checked — no tenant learns of another's ids; a stop the app refuses is not audited.
Group 3 · Architecture / hygiene — [x] checked — one `ops` subcommand beside `purge`, confirmed at a terminal the same way.
Group 4 · Process — [x] checked — design first; CHANGELOG, backlog and manual updated.
Group 5 · Intuitive UI — [x] checked — "Stopped", running, and "sent; the app has not recorded it yet" are shown apart.
Group 6 · Signal integrity — [x] checked — the stop state is the app's record, not the portal's intent.
Group 7 · Auth & session integrity — [x] checked — `denied-vs-missing`: a refused write reveals nothing about another tenant.

Tests added: eight in `agentsmith/test/test_compliance_runtime.py` (one needs a database); three in `portal/test/hitl.test.ts`; one updated for the new message.
Mutation-checked: yes, by hand; ten mutants, all killed or pinned elsewhere after pass 1.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above with `COMPLIANCE_TEST_DSN`; `npm test`; `tsc`; ruff; mypy; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `consistent-auth-gates`, `denied-vs-missing`, `provenance-and-precedence`, `failure-is-not-a-result`, `test-that-cannot-fail`

KG query: kg:3c33b236a750
