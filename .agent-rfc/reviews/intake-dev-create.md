# Review — intake-dev-create

Design: `.agent-rfc/designs/intake-dev-create.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

1. **A security sweep failed the route, and was right to by its own rule.**
   `portal/test/authz.test.ts`'s "every HANDLER that reads an operator's Access
   also scopes it to tenants" refused `POST /api/dev/intakes`: "a permission check
   with no app lets a user act on apps outside their grants". No handler before
   this one asked a permission with no per-app check at all — `/api/audit` asks
   app-less and then scopes when a tenant is named. The design had not anticipated
   it. The sweep cannot see that `createIntake` refuses every registered app, which
   is stronger than scoping to the caller's apps, so the design was amended first
   and the sweep gained an `APP_LESS` table rather than a silencing: one entry, for
   one handler and one permission, with its reason. Proved narrow with three
   mutations, each of which fails the sweep — the exempt route asking a different
   permission app-less, an entry naming no handler, and a different route
   (`POST /api/admin/apps`) dropping its per-app check.

2. **The race test was checked before it was trusted — and this time it races.**
   Slice 2's consume race test passed with its guard removed. This one was mutated
   the same way before anything was recorded: with the advisory lock removed, five
   concurrent creates for one id issued more than one intake and the test failed.
   Both refusals and the audit role were mutated too; every one was caught.

## Pass 2 — findings: 0

Re-read `portal/lib/authz.ts`, `portal/lib/intakes.ts`, the route and the three
test files against the levers.

- `declared-vs-enforced` — `design_approver` is now `[...DEVELOPER, "dev.allowlist"]`,
  and a test pins that it holds every Developer permission, as the role table says.
- `consistent-auth-gates` — `dev.create` is documented in `can()`'s docstring beside the
  other app-less permissions, and in the `APP_LESS` table with its reason.
- `denied-vs-missing` — 403 for a role without `dev.create`; 409 for a taken id, naming
  whether a registered app or an open intake holds it, and the intake's number and expiry.
- Considered and accepted: an old-form scoped `admin` (`{"role":"admin","tenants":[…]}`)
  maps to `administrator` over its listed tenants and now holds `dev.create` app-less.
  Consistent with the Developer case, and the same refusal applies.
- **Checked live under real middleware and real grants**: a Developer granted only
  `acme` issued an intake for `globex-new` (201); an Operator was refused (403); after an
  Administrator registered `acme`, the Developer's intake for it was refused (409,
  registered), and a second for `globex-new` was refused (409, intake 93 open); an
  Administrator issued one (201). The audit rows read `dev | developer | globex-new` and
  `admin | administrator | admin-new`.

## Sign-off

Group 1 · DRY & shared code — [x] checked — `design_approver` is derived from `DEVELOPER` instead of copied; `roleFor`, `getTenant`'s table and the existing app-less pattern are reused.
Group 2 · Quality / safety — [x] checked — 3 authz tests and 4 database tests added; the advisory lock, both refusals and the audit role each mutated by hand and caught; the sweep's exemption mutated three ways and caught; the live check above.
Group 3 · Architecture / hygiene — [x] checked — the refusal lives in `createIntake`, inside the transaction that inserts, so no route can create an intake without it.
Group 4 · Process — [x] checked — the design was amended before the sweep was, when the sweep failed; owner's decision and reasoning carried as given.
Group 5 · Intuitive UI — [x] gap — no screen until slice 4. The 409 messages say which kind of taken and what to do: use the open intake, or wait for it to expire.
Group 6 · Signal integrity — [x] checked — a taken id is a 409 with its reason, not a 400 or a 403; the audit names the role that authorised the intake.
Group 7 · Auth & session integrity — [x] checked — a check is widened on purpose and stated in P13: Developers and up, for any id no app holds. The one route-scoping exemption is named, narrow, and proved; the token's own rules are unchanged.

Tests added: `portal/test/authz.test.ts` (3 tests, and the `APP_LESS` exemption with its stale-entry check), `portal/test/intakesDb.test.ts` (4 tests; every existing call now passes a role).
Mutation-checked: by hand — the advisory lock, the registered-app refusal, the open-intake refusal and the audit role, each caught; the sweep's exemption three ways, each caught. Not in `scripts/mutation_check.py`, which drives pytest only.
Fixtures re-pinned: none.
Gates run: `npx tsc --noEmit`, `npm test` (15 files), `npm run test:db` (7 files, fresh Postgres), `npm run build`, the live multi-user check, and `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `declared-vs-enforced`, `parameterize-dont-clone`, `consistent-auth-gates`, `denied-vs-missing`, `out-of-order-and-repeated`, `validate-on-the-receiving-side`, `guards-must-be-able-to-fail`, `docs-match-behaviour`.

KG query: kg:990f943d3dbb
