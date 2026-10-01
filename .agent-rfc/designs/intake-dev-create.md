---
status: done
scope:
  - portal/lib/authz.ts
  - portal/lib/intakes.ts
  - portal/app/api/dev/intakes/**
  - portal/test/**
---
# A developer can start a tenant: `dev.create`

## Problem

Slice 3 of the portal-intake plan. Creating an intake (`POST /api/dev/intakes`,
shipped in `9d5120f`) needs `admin.apps` — the narrowest existing permission
that could hold it, chosen so slice 2 was usable end to end and this slice would
be a deliberate widening on its own review. The owner decided the target on
2026-09-30: a `dev.create` permission, held by `developer`.

The owner's reasoning, which this slice implements rather than reopens: starting
a tenant on the machine the author already uses is not a circumspect act — anyone
with that machine can create any repository on it. What deserves care is a
CHANGE to a repository that already exists. An intake creates nothing in any
repository; the author's own machine pulls it and scaffolds a new one.

Three things in the code shape how to do that:

1. **The app does not exist yet, so a per-app check cannot pass for a scoped
   grant.** The route today asks `can(access, "admin.apps", tenantId)`, which for
   a new id only an `"*"` grant satisfies. `portal/lib/authz.ts` already has the
   answer for permissions with no app to ask about: `admin.audit`, `admin.users`
   and `admin.org` are asked app-less. `dev.create` is the same kind.
2. **Asked app-less, it must not reach an app that DOES exist.** Otherwise a
   developer granted only `["acme"]` could file an intake named `globex` for an
   app they cannot see, and scaffold a second repository claiming its id. Today
   nothing refuses an intake for a registered id — slice 2's review recorded it
   as a gap for later.
3. **`docs/DESIGN.md`'s role table says "Design approver | Developer's, and …"**,
   but `ROLE_PERMISSIONS.design_approver` is a hand-copied list, not derived from
   `developer`. Adding `dev.create` to `developer` alone would make that sentence
   false without any test noticing.

## Approach

- **`dev.create` in `PERMISSIONS`**, "create a tenant intake", asked app-less —
  added to the docstring's list of permissions that are. `developer` gains it;
  `design_approver` is rebuilt as `[...DEVELOPER, "dev.allowlist"]` so the
  superset holds by construction, and a test pins `design_approver ⊇ developer`.
  `administrator` and `super_user` gain it through the derivations they already
  have. No other role changes.
- **The route asks `can(access, "dev.create")`**, app-less, in place of the
  two-step `admin.apps` check.
- **An intake can only name a tenant that does not exist yet.** `createIntake`
  refuses, with 409, a tenant id that is a registered app ("already registered —
  an intake starts a new tenant; changing an existing one is not this") or that an
  open intake already names (unconsumed and unexpired — "intake N names it until
  <time>"). The open-intake check and the insert run under a transaction-scoped
  advisory lock on the tenant id, so two people filing the same id at once cannot
  both succeed. This closes slice 2's Group 5 gap, and it is what makes the
  app-less check safe: an intake never names an app the caller could lack a grant on.
- **The route-scoping sweep gets one named exemption.** `portal/test/authz.test.ts`'s
  "every HANDLER that reads an operator's Access also scopes it to tenants" fails
  this route, correctly by its rule: no handler before it asks a permission with
  no per-app check at all (`/api/audit` asks app-less and then scopes when a
  tenant is named). The sweep cannot see that `createIntake` refuses every app
  that exists, which is stronger than scoping to the caller's apps. It gains an
  `APP_LESS` table keyed by file and handler, each entry naming the one permission
  that handler may ask app-less and why; the handler must ask exactly that
  permission app-less, and an entry that matches no handler fails, so the table
  cannot go stale or grow quietly.
- **The audit records the role.** `intake_issued` gains `role`, from `roleFor` —
  which exists for exactly this: with several grants, the role that authorised
  THIS action is the true answer. Now that more than one role can issue an intake,
  the audit has to say which did.

**Deliberately not done:** no new grant shape, no per-app `dev.create`, no
change to who may READ or CONSUME an intake (the token decides that, unchanged),
no form (slice 4).

## Pillars

- P1 applies — `.agent-rfc/designs/intake-dev-create.md`, carrying the owner's
  2026-09-30 decision (`dev.create`, on `developer`) and his reasoning as given.
- P2 applies — `portal/lib/authz.ts` already has app-less permissions, `roleFor`,
  and derived role lists (`ADMINISTRATOR`); this adds one permission and derives one
  more list. `getTenant` (`portal/lib/tenants.ts`) answers "is this id registered".
  No dependencies.
- P3 applies — `portal/lib/intakes.ts` already spans nothing at creation beyond the
  route's automatic span; the audit row is the record, now with the role. No new path.
- P4 applies — `portal/test/authz.test.ts`: `developer` holds `dev.create` app-less;
  `operator`, `hitl_reviewer`, `release_approver` and `viewer` do not;
  `design_approver ⊇ developer`; `administrator` and `super_user` hold it.
  `portal/test/intakesDb.test.ts`: a registered id is refused; an id with an open
  intake is refused; once that intake is consumed or expired, the id is free again;
  two concurrent creates for one id leave exactly one; the audit row names the
  role. Portal mutations run by hand, as in slice 2 — `scripts/mutation_check.py`
  drives pytest only.
- P7 applies — `portal/lib/authz.ts`'s pattern: the permission is a member of the
  `PERMISSIONS` tuple, so `Permission` admits it by type and a misspelling does not
  compile; no `any`.
- P8 n/a — no telemetry change.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — reads no new untrusted content; the body is validated by
  `parseIntakeInput`, unchanged.
- P12 n/a — no credential changes; the intake token is unchanged.
- P13 applies — `portal/app/api/dev/intakes/route.ts` gets WEAKER on purpose, so
  say exactly how. Before: an administrator with an `"*"` grant. After: anyone
  holding `developer` or `design_approver` on any app, for any tenant id that is not
  registered and has no open intake. The owner decided this; what makes it safe is
  that an intake writes into no repository — it produces files only on the machine
  of whoever holds its token — and that the new refusal keeps it away from every
  app that exists. Compensations: the audit names the actor and the role; the token
  is single-use and 24-hour, unchanged. A security sweep gets weaker too, and is
  narrowed rather than switched off: one exemption, for one handler and one
  permission, whose compensating control — the refusal of registered ids — is
  tested in `portal/test/intakesDb.test.ts`. Declared gap: a developer can file intakes
  for any number of new ids. Nothing rate-limits it, and nothing needs to yet — each
  is a row that expires in a day.
- P14 n/a — no fixtures or baselines; the contract is unchanged.
- P15 applies — `portal/lib/intakes.ts` answers a taken id with 409 and says which
  kind — registered, or named by an open intake, with its number and expiry — not a
  400 for a well-formed body, and not a 403, which would read as a permission
  problem.
- P16 applies — `portal/lib/intakes.ts` refuses before writing: the lock, the two
  checks and the insert are one transaction, so a refusal leaves nothing behind and
  the author's retry is the same request once the id is free.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — "Design approver | Developer's" was declared in the role
  table and enforced by nothing; derived, it holds by construction, and a test pins it.
- `parameterize-dont-clone` — `design_approver` stops being a copy of `developer`'s list.
- `consistent-auth-gates` — `dev.create` is asked the way the other app-less permissions
  are, and documented beside them.
- `denied-vs-missing` — a taken id is a 409 with its reason, not a 403 or a 400.
- `out-of-order-and-repeated` — two creates for one id at once leave exactly one.
- `validate-on-the-receiving-side` — the registered-id check is the portal's; the CLI's
  receiving-side checks are unchanged.
