# Review — portal-intake-pull

Design: `.agent-rfc/designs/portal-intake-pull.md`
Levers: `docs/review-levers.md`

Built in two commits under one design. This record covers **2a** — the contract
and the portal side — and gains a section when 2b, the CLI, is built.

## Pass 1 — findings: 3

1. **`guards-must-be-able-to-fail` — the race test did not race.** Removing the
   `consumed_at IS NULL AND expires_at > now()` guard from the consume `UPDATE`
   left all eight database tests green. The handler checked the row it had just
   read before opening the transaction, and that pre-check caught every repeat;
   five `Promise.all` consumes evidently did not interleave between read and
   write. The guard is what protects two portal instances from both consuming,
   and nothing tested it. Fixed by removing the pre-check, so the `UPDATE`'s own
   conditions are the only gate: now the mutation fails three tests, including
   the plain sequential "used once, then refused". The code is shorter for it.

   Worth recording how it nearly went unseen: my first attempt at the mutation
   was a `sed` that did not match, the `&&` chain stopped, and the output was
   silence — which reads like a pass. It was re-run as an exact string replace
   that asserts it applied.

2. **A green check that could not see the change.** The `docs/DESIGN.md`
   repo-tree drift check passed — and it reads `git ls-files`, so every new file
   was invisible to it while untracked. Re-run with 2a staged: still green, and
   its counts did not move, so `contract/`'s sub-tree is not one it inspects.
   That is a fact about the check, recorded rather than assumed.

3. **A tool changed a line I did not mean to touch.** Registering the three new
   test files by re-serialising `portal/package.json` with `json.dumps` re-escaped
   the `›` in its unrelated `description`. Reverted and redone as a text edit;
   the diff is now the two script lines. The registration itself matters: those
   scripts list every file explicitly, so an unregistered test never runs.

## Pass 2 — findings: 2

1. **`single-source-of-truth` — two clocks judged one expiry.** `unusable()`
   compared `expires_at` with the Node process's `Date.now()`; the consume
   `UPDATE` compares it with Postgres's `now()`. Under clock skew an intake could
   read as live and then fail to consume, and the fallback would have labelled
   that "the intake changed — retry". Both reads now select
   `expires_at <= now() AS expired`, so Postgres decides everywhere, and
   `portal/test/intakes.test.ts` pins that `lib/intakes.ts` consults no process
   clock.

2. **`pin-unremovable-duplicates` — two limits existed twice, unpinned.** The
   architecture pattern and the 500-character item limit are in both
   `portal/lib/intakes.ts` and `contract/intake/v1/record.schema.json`. The
   contract test pinned the enums, the tenant-id pattern and three limits, not
   these two. `ARCHITECTURE` is exported and both are pinned.

## Pass 3 — findings: 0

Re-read `portal/lib/intakes.ts`, the three routes, `portal/middleware.ts`, the
schema, the four test files and the two contract files against the levers after
the Pass 2 fixes.

- `consistent-auth-gates` — the create route is `portal/app/api/admin/apps/route.ts`'s
  two-step `can()` verbatim; the machine routes authenticate inside the handler as
  `/api/dev/ingest` does.
- `validate-on-the-receiving-side` — the portal validates what an author sends; what
  it serves back is what it wrote from validated input. The CLI's re-validation is 2b.
- `denied-vs-missing` — 401 for no or unknown token, 404 for an id the token does not
  open, 410 `consumed` and 410 `expired` with different words.
- `every-line-earns-its-place` — the one remaining defensive branch, the 409 after a
  refused `UPDATE`, is what `unusable()` needs to be total; its comment says the
  `UPDATE`'s conditions make it unreachable.
- Checked live, not only in tests: the built portal, started against a throwaway
  database, answered all seven requests as designed under Next's own matcher —
  `/api/dev/scaffold/:id` with no credentials got the handler's 401 and no
  basic-auth challenge; `/api/dev/scaffolding` got the middleware's challenge.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the token shape (`hashToken`, `bearerToken`), `APP_ID`, `Parsed`, `ISOLATION_VALUES`, `withTransaction` and the `config_change` / `tenant_created` audit types are reused; the two Python-owned sets are mirrored once and pinned by `portal/test/catalogs.test.ts`.
Group 2 · Quality / safety — [x] checked — 14 validation and contract tests, 8 database tests, 6 matcher tests; four mutations run by hand and each caught (matcher anchor, stack drift, consume guard, token-decides id check); the live check above.
Group 3 · Architecture / hygiene — [x] checked — handlers are Next-free, as `portal/lib/devIngestHandler.ts` is, so the database test drives what the routes run; the tenant id is deliberately not a foreign key, and no `CHECK` duplicates a set the catalog test pins.
Group 4 · Process — [x] checked — design written and gate-validated before code; two passes of findings recorded with what caught each, including the two checks that passed while seeing nothing.
Group 5 · Intuitive UI — [x] gap — no screen in this slice; the form is slice 4. Refusals name the field and say what to do. Not handled, and for slice 4's form to decide: nothing warns when an intake names a tenant id that is already a registered app, or that another open intake already names.
Group 6 · Signal integrity — [x] checked — consumed and expired are different 410s; one clock decides expiry; a 404 for another intake's id carries none of its contents.
Group 7 · Auth & session integrity — [x] checked — a new path skips sign-in, so `portal/test/middleware.test.ts` is its boundary and the first test of that list at all; the token is per intake, hashed at rest, shown once with `no-store`, never on a command line, single-use under concurrency and 24-hour; creating one needs `admin.apps` over the tenant id.

Tests added: `portal/test/intakes.test.ts` (14), `portal/test/intakesDb.test.ts` (8), `portal/test/middleware.test.ts` (6), two tests in `portal/test/catalogs.test.ts`, all registered in `portal/package.json`.
Mutation-checked: by hand, four mutations, each caught — not in `scripts/mutation_check.py`, which drives pytest only; putting portal mutations there needs node and Postgres in that job, which this design does not cover. Declared, not assumed.
Fixtures re-pinned: none stale — `contract/intake/v1/fixture.json` is new and pinned from the portal side now, from the CLI in 2b.
Gates run: `npx tsc --noEmit`, `npm test` (15 files), `npm run test:db` (7 files, fresh Postgres), `npm run build`, the live check, the `DESIGN.md` repo-tree drift check with 2a staged, and the Python suite — 1999 passed, 10 skipped, plus the 152 tests that read the touched files re-run against their final state.

Levers reviewed: `consistent-auth-gates`, `validate-on-the-receiving-side`, `denied-vs-missing`, `single-source-of-truth`, `pin-unremovable-duplicates`, `guards-must-be-able-to-fail`, `every-line-earns-its-place`, `implemented-not-invoked`, `use-existing-apis`, `docs-match-behaviour`, `search-before-writing`, `small-verified-slices`.

KG query: kg:8b3830a1e4fc
