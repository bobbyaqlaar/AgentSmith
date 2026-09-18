# Review — portal phase 1, S6: Administration › Apps

Design: `.agent-rfc/designs/portal-phase1.md` (S6).

**Built evidence (2026-09-18):**

- **Failing tests first.** `portal/test/apps.test.ts` (validation, 7) and
  `portal/test/appsDb.test.ts` (Postgres, 5) were written before `lib/apps.ts`; neither imported
  on the first run.
- **Looked at, and used.** In the throwaway instance, signed in as the test Administrator through
  the local proxy: the switcher gained Administration; the app list shows each app's repository
  and whether a token exists; on KYC Sentinel, **Issue token** showed the token once, with the two
  secret names and a link to the repository's secrets page; **Rotate token** asked first, in
  words that say what breaks, and **Cancel** put the panel back. The audit log shows the issue as
  `config_change`, actor `admin`, verified.
- **Mutation checks (each reverted):** twelve — any id accepted, an unsafe repository URL, a
  repository without a provider, an edit taking its id from the body, registration overwriting,
  rotation keeping the old token, the token written into the audit log, an edit not audited, the
  actor lost, the actor header not stripped, an SSO actor not normalised, revoked tokens counted as
  live. All caught.

## Pass 1 — findings: 4

- `declared-vs-enforced`, `early-exit-keeps-the-record` — **finding:** the audit log had no way
  to know who acted: `Access` carried grants and no identity, so every admin action would have
  been recorded against no one. The middleware forwards the signed-in actor (`x-af-actor`), and
  strips any client-supplied copy exactly as it does the grants.
- `early-exit-keeps-the-record` — **finding:** `appendAuditEvent` wrote on the pool, outside any
  transaction, so an action could commit and its audit entry fail, or the reverse. It takes the
  caller's transaction client now, and every Administration change writes its entry inside the
  same transaction as the change.
- `no-copy-paste` — **finding:** `lib/apps.ts` generated and hashed tokens with its own copy of
  the code in `lib/ingestTokens.ts`. `newIngestToken` is the one place tokens are made.
- `use-existing-apis` — **finding, declined as a schema change:** the audit catalogue has four
  event types behind a `CHECK` on an append-only table. Registration is recorded as
  `tenant_created` and every other change as `config_change`, with the action named in the
  details (`app_registered`, `app_updated`, `ingest_token_issued`, `ingest_token_revoked`) — no
  constraint altered on the audit table.

## Pass 2 — findings: 0

Every lever over the final diff and both pages, in both themes. Considered and declined:

- Deleting an app from Administration. The audit log references it and is append-only, so an app
  with history cannot be deleted — by design; the test that registers one leaves it in place and
  says why. Retiring an app is its own decision, not this slice.
- Confirming the dead-letter queue's **Discard**, which has no confirmation today. It is the same
  lever as the token panel's, but an Ops change of its own — a backlog item.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] checked
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] checked

Tests added/updated:      portal/test/apps.test.ts (7), appsDb.test.ts (5), authz.test.ts
                          (+1 actor, switcher test reworked)
Mutation-checked:          yes — twelve, each reverted; all caught
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:3580be478211
Gates run locally:         npm test, the DB suites on a throwaway Postgres, tsc --noEmit,
                          next build, the pages in the browser
Declared gaps:             none
```
