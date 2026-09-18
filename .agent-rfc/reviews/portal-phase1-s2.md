# Review — portal phase 1, S2: seven roles

Design: `.agent-rfc/designs/portal-phase1.md` (S2).

**Built evidence (2026-09-18):**

- **Order of work, stated.** The implementation of `portal/lib/authz.ts` was written before its
  tests, against the process this repo holds itself to. The tests were written next and the
  mutation run below stands in for the failing-first run that was skipped: every rule the tests
  claim was broken on purpose and seen to fail them.
- **Compatibility was designed from today's routes, not today's role names.** Each write route
  was read before mapping: the old `operator` could replay and discard dead-letter entries, mint
  widget tokens and upsert its own tenants' settings. The new Operator holds exactly those four
  permissions, so an old `operator` entry maps onto it with nothing gained or lost. The old
  `viewer` has no counterpart among the seven, and stays a legacy role accepted only in the old
  form. A scoped old `admin` stays scoped.
- **Every call site moved**: twelve files; `tsc --noEmit` clean; `next build` passes, Edge
  middleware included.
- **Mutation checks (each reverted):** fourteen — app scope ignored, prototype-named roles
  accepted, an org-wide grant scoped, `viewer` allowed in the new form, a scoped old `admin`
  widened to every app, Operator losing app settings, the HITL reviewer reading Ops, the
  Administrator holding organisation settings, a malformed header grant kept, an unknown old role
  defaulted, an unlisted SSO identity given `viewer`, areas ignoring permissions, the retired
  headers not stripped, the tenant upsert unscoped. Thirteen caught on the first run; the survivor
  is finding 3.

## Pass 1 — findings: 3

- `guards-must-be-able-to-fail` — **finding:** `isAnyRole` tested `value in ROLE_PERMISSIONS`,
  which is also true for `constructor`, `toString` and the rest of `Object.prototype`. A forged
  header naming one would have passed as a role and crashed the first permission lookup — a 500
  on every request from a caller who can reach the middleware. Own properties only now; test
  `a role named after an Object.prototype property is not a role`. Found in this change's own
  code before commit — the old check used `includes` and was safe.
- `ambiguous-signals` — **finding:** four routes stamped `access.role` on their spans. With
  grants, a user holds several roles, and "the role" of the actor is the one whose grant allowed
  this action on this app. `roleFor(access, permission, app)` answers that, and the spans use it.
- `test-that-cannot-fail` — **finding:** mutation "retired headers not stripped" survived:
  stripping lived inside the middleware, which the suite cannot import without Next. It is now
  `stripAccessHeaders` in `lib/authz.ts`, called by the middleware and tested directly.

## Pass 2 — findings: 0

Every lever over the final diff, the documentation included (the design document's access
section, the manual's Ops Portal setup, the portal README, `.env.example`). Considered and
declined:

- Letting an Administrator grant name a list of apps. The specification makes Administrator and
  Super user organisation-wide; a scoped one is refused at start-up. The old form's scoped
  `admin` is the exception, kept only because it exists in running configurations.
- Moving users to the database now. That is phase 2, with passkeys; configuration stays in the
  environment until then.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen changes in this slice
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] checked

Tests added/updated:      portal/test/authz.test.ts (28), portal/test/catalogs.test.ts
Mutation-checked:          yes — fourteen, each reverted; one survivor became finding 3
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:8e29af19ccb3
Gates run locally:         npm test, tsc --noEmit, next build
Declared gaps:             none
```
