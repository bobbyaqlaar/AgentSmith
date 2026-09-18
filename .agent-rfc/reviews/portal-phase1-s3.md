# Review — portal phase 1, S3: the Dev ingest

Design: `.agent-rfc/designs/portal-phase1.md` (S3).

**Built evidence (2026-09-18):**

- **Failing tests first.** `portal/test/devIngest.test.ts` (validation, 13) and
  `portal/test/devIngestDb.test.ts` (token → validation → storage against a real Postgres, 7) were
  written before `lib/devIngest.ts`, `lib/devStore.ts`, `lib/ingestTokens.ts` and
  `lib/devIngestHandler.ts`; neither imported on the first run.
- **The contract, with real data.** `process_gate.py ci --json` over AgentSmith's own last eight
  commits, posted through `handleDevIngest` into a throwaway Postgres: 200, eight rows, the right
  verdicts, design titles and pass counts. The fixtures in the tests are shaped like the gate's
  output; this run shows the gate's actual output is what the portal accepts.
- **The migration is idempotent.** `npm run db:migrate` twice on a fresh database, both clean;
  the existing `test:db` suites pass against the migrated schema.
- **Mutation checks (each reverted):** fifteen — an unknown schema accepted, the commit count,
  subject and list lengths unlimited, any verdict, an unchecked hash, an unsafe run URL, list
  items unchecked, a bad time accepted, an unchecked pillar kind, no body-size limit, a missing
  token accepted, a revoked token resolving, duplicate rows on a repost, the ingest run not
  recorded. Fourteen caught on the first run; the survivor is finding 4.

## Pass 1 — findings: 4

- `implemented-not-invoked`, `failure-mode-visibility` — **finding:** the storage transaction ran
  on a checked-out client, and only the pool's `query` is traced — the portal's first
  multi-statement write would have been its first invisible one. `withTransaction` in
  `lib/db.ts` spans the whole transaction (`portal.db.transaction`, named), and is the one place
  that calls `connect()`.
- `one-catalog`, `pin-unremovable-duplicates` — **finding:** the verdict list now exists in three
  places that cannot share code: the gate that writes it (Python), the validator (TypeScript) and
  a `CHECK` on `dev_commits.verdict` (SQL). The gate has `DEV_VERDICTS` and refuses to write a
  record outside it; `scripts/test/test_dev_record.py` parses the TypeScript list and schema
  number against it; `portal/test/catalogs.test.ts` pins the `CHECK`. Same for
  `tenants.repo_provider` against `REPO_PROVIDERS`.
- `environment-parity` — **finding:** the bearer-token parser was first added to
  `lib/bearerAuth.ts`, which imports Next — the database test could not load it outside Next. It
  lives in `lib/ingestTokens.ts`, with the lookup it serves, and the design's P12 answer says so.
- `ambiguous-signals` — **finding:** mutation "missing token accepted" survived. A missing
  header still fails at the lookup, so the status was 401 either way — but the message changed
  from "a Bearer token is required" to "unknown or revoked token", which sends a CI operator to
  the portal when the fix is the CI secret. The test now asserts each 401's message.

## Pass 2 — findings: 0

Every lever over the final diff, the README's machine-endpoint list and data-source table, and
the CHANGELOG's migration note included. Considered and declined:

- Accepting part of a body. A partly stored range would advance "last received" over commits
  that were never stored; the design says refuse whole, and the transaction makes it so.
- Rejecting the old `tenants.repo_*`-less rows. Existing apps have no repository yet; the
  columns are nullable and Admin › Apps (S6) fills them.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen in this slice
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] checked

Tests added/updated:      portal/test/devIngest.test.ts (13), devIngestDb.test.ts (7),
                          catalogs.test.ts (+2), scripts/test/test_dev_record.py (+1)
Mutation-checked:          yes — fifteen, each reverted; one survivor became finding 4
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:dad15f8350f7
Gates run locally:         npm test, npm run test:db (throwaway Postgres), tsc --noEmit,
                          next build, the real-record run above
Declared gaps:             no page reads these tables yet — S5; no CI sends yet — S7
```
