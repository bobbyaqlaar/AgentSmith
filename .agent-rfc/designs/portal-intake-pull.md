---
status: active
scope:
  - contract/intake/**
  - portal/db/schema.sql
  - portal/lib/intakes.ts
  - portal/app/api/dev/intakes/**
  - portal/app/api/dev/scaffold/**
  - portal/middleware.ts
  - portal/package.json
  - portal/test/**
  - runtime/cli.py
  - runtime/intake.py
  - runtime/architectures.py
  - runtime/test/**
  - scripts/test/**
  - scripts/mutation_check.py
---
# A tenant is created from a portal intake by pulling it, not by the portal pushing it

## Problem

The owner's portal-intake plan (slices 1–4) lets an author describe a new tenant
in the portal and create it on their own machine. Slice 1 shipped `--ide` and
recorded it (`.agent-rfc/designs/chosen-ide-is-recorded.md`). Nothing yet carries
an author's answers from the portal to `agentsmith tenant init`.

The owner decided the shape on 2026-09-30: the record lives in the portal's
Postgres, and the CLI fetches it over the network — a PULL. The portal never
writes into a repository, so the first commit is still made locally, still
content-addressed into `.agenticframework/scaffold.json`, and still vouched
(`scripts/process_gate.py` `manifest_problems`). The owner's argument, conceded
then and not reopened here: an intake written by an authenticated author in the
portal is no less trusted than the same words typed at that author's terminal.

Three facts in the code shape the design:

1. **Every existing machine credential presumes the tenant exists.**
   `app_ingest_tokens.tenant_id REFERENCES tenants(tenant_id)`, and the
   portal-wide `requireBearer` tokens (`portal/lib/bearerAuth.ts`) are one secret
   for every caller. An intake exists BEFORE its tenant, and a portal-wide secret
   on every developer laptop is the wrong blast radius.
2. **The two tenant-id rules differ, and the portal's is the narrower.**
   `portal/lib/apps.ts` `APP_ID` is lower-case, digits and dashes, ≤ 63;
   `runtime/cli.py` `TENANT_ID_PATTERN` also admits upper case, dots and
   underscores, ≤ 64. A tenant scaffolded under the CLI's rule can be one the
   portal then refuses to register as an app.
3. **No test covers `portal/middleware.ts`'s matcher.** It excludes five
   machine paths from human authentication, anchored `(?:/|$)` because plain
   prefix matching was once an auth bypass (`docs/PRODUCT_ARCHIVE.md` 2.6). A
   sixth exclusion would ship with no test proving its boundary.

## Approach

**Built and committed in two steps, one design, one review record:**
**2a** — the contract and the portal side; **2b** — the CLI side. Each commit
updates the review record. 2a is testable alone against the database; 2b is
testable alone against a local HTTP stub serving the contract's fixture.

### The record — `contract/intake/v1/`

A versioned JSON Schema, `record.schema.json`, with a `fixture.json`, following
`contract/gate/v1/`. Both sides test against it, so the wire format has one
definition:

| field | type | rule |
|---|---|---|
| `schema_version` | int | `1` |
| `intake_id` | string | the portal's id |
| `tenant_id` | string | `APP_ID` — the narrower rule, so the tenant can register |
| `stack` | enum | `runtime/cli.py` `STACKS` |
| `isolation` | enum | `ISOLATIONS` / `portal/lib/isolation.ts` `ISOLATION_VALUES` |
| `architecture` | string \| null | validated by `runtime/architectures.py`, CLI side only |
| `agentic` | bool | |
| `ides` | string[] | `gate_ides.GENERATED`; empty means "every verified IDE" |
| `rfc.objective` | string | required, 1–4000 chars |
| `rfc.acceptance_criteria` | string[] | required, 1–20 items, each 1–500 chars |
| `rfc.files_to_modify` | string[] | optional, 0–50 items, each 1–500 chars |

### The portal — commit 2a

- **Table `tenant_intakes`** in `portal/db/schema.sql`: the record's fields,
  `token_hash`, `created_by`, `created_at`, `expires_at`, `consumed_at`,
  `org_id`. `tenant_id` is deliberately **not** a foreign key to `tenants` — the
  tenant does not exist yet, which is the whole point.
- **Credential: one bearer token per intake**, prefix `asx_`, minted by the same
  code path shape as `portal/lib/ingestTokens.ts` — random, shown once in the
  create response with `Cache-Control: no-store`, only its SHA-256 stored,
  expiring after 24 hours. It authorises reading and consuming exactly one
  intake and nothing else.
- **The token decides, the id checks.** `portal/lib/ingestTokens.ts` states the
  rule: "the token alone decides which app a request writes to — never an id
  supplied alongside it." The owner's CLI shape is `--from <id>`, so the id is
  kept for humans but the route resolves the intake from the token and answers
  `404` if the URL's id differs — the same answer as an unknown id, so the route
  is no oracle for which ids exist.
- **Two routes, two nouns, no shared prefix:**
  - `POST /api/dev/intakes` — human, behind `portal/middleware.ts`. Creates an
    intake and returns `{intake_id, token, expires_at, command}`, where `command`
    is the exact line to run. **Gated by `admin.apps` in this slice.** Slice 3
    widens it to `dev.create`; starting at the narrowest existing permission
    keeps this slice usable end to end and makes slice 3 a pure, separately
    reviewed widening.
  - `GET /api/dev/scaffold/:id` and `POST /api/dev/scaffold/:id/consume` —
    machine, token-authenticated inside the handler, excluded in the matcher as
    `api/dev/scaffold(?:/|$)`. `GET` is idempotent and repeatable until the
    intake is consumed or expires. `consume` is single-use: `UPDATE … WHERE
    consumed_at IS NULL AND expires_at > now() RETURNING`, so two racing calls
    cannot both succeed.
- **Consume is a separate call, made by the CLI only after the scaffold
  succeeds.** A scaffold that fails half-way leaves the intake usable, so the
  author retries the same command instead of returning to the portal.
- **Audit, with existing event types.** Issuing the token is
  `config_change` / `details.action = "intake_issued"`, exactly as
  `portal/lib/apps.ts` audits `ingest_token_issued`, in the same transaction.
  Consuming is `tenant_created` / `details.action = "intake_consumed"`. Both carry
  `tenantId: null` and the intended id in `details`, because
  `audit_log.tenant_id REFERENCES tenants` and the tenant is not registered yet.
  No new event type, so no `CHECK` constraint to migrate on existing databases.
- **Closed sets mirrored, and pinned.** `portal/lib/intakes.ts` declares the
  stack and IDE sets. `portal/test/catalogs.test.ts` already reads the other side
  and compares for three sets; it gains these two, read from `runtime/cli.py` and
  `scripts/gate_ides.py`. `ISOLATION_VALUES` is reused, not copied.
- **The matcher gets its first test**, `portal/test/middleware.test.ts`: the new
  machine path is excluded, `POST /api/dev/intakes` is not, a lookalike
  (`/api/dev/scaffolding`) is not — and the five existing exclusions are pinned
  while it is there.
- **Registered in `portal/package.json`.** Its `test` and `test:db` scripts list
  every file explicitly, so a test file not added there never runs.

### The CLI — commit 2b

- **`agentsmith tenant init --from <id>`.** The tenant id positional becomes
  optional: exactly one of `<tenant_id>` or `--from` is given, because the
  record names the tenant. `<id>` must be digits before it reaches a URL, so
  `--from ../admin` is refused as an argument, not sent as a path. Reads
  `AGENTSMITH_PORTAL_URL` (already the documented name, from
  `scripts/send_dev_record.py`) and `AGENTSMITH_INTAKE_TOKEN`. The token is
  never an argument — an argument lands in shell history and in `ps` — and when
  the variable is unset at a terminal the CLI asks for it without echo
  (`getpass`), so the author need not `export` it into their history either.
  Off a terminal, an unset token is "not configured", named.
- **`runtime/intake.py`, standard library only,** because `runtime/` is vendored
  into tenants. It follows `scripts/send_dev_record.py`'s discipline exactly:
  `https`, or `http` only to `localhost`/`127.0.0.1`, checked before the token is
  sent; **redirects refused**, because `urllib` carries the `Authorization`
  header across one, so a redirecting address would hand the token to wherever
  it points; a bounded timeout; a response-size cap. Exit 2 when the author
  must change something (not configured, refused, invalid record — each named in
  words), exit 4 when the portal is unreachable or failing and the same command
  is the retry.
- **Validated on the receiving side, whatever the portal checked.** Every field
  is re-checked against the CLI's own constants — `validate_tenant_id`, `STACKS`,
  `ISOLATIONS`, the architecture catalogue, and slice 1's `--ide` validation —
  and then the portal's narrower `APP_ID` rule on top. The portal's validation is
  for the author's convenience; the CLI's is the control.
- **`--from` is exclusive with the fields it carries.** Combining it with
  `--stack`, `--isolation`, `--architecture`, `--agentic` or `--ide` is refused,
  rather than one silently winning.
- **The RFC is filled, not templated.** `runtime/architectures.py` gains the
  filled form of `render_scaffold_rfc`: the three sections from `rfc.*`, without
  the `⚠️ TEMPLATE` banner, at the same path, so Guardrail 4 is satisfied and the
  file is vouched like any scaffolded file.
- **Then consume — only once the intake has fully landed.** Only after
  `init_tenant` returns, and only if `.agent-rfc/001-scaffold.md` holds exactly
  what this intake renders. The scaffold never overwrites an RFC, so in a
  repository that already has one the intake's text is NOT written; consuming
  then would burn the only copy of it. In that case the CLI says so and leaves
  the intake live. The same comparison makes a re-run after a failed consume
  consume cleanly. If consume itself fails, the scaffold stands and the CLI
  says so: the intake expires by itself.

**Deliberately not done:** no portal form (slice 4), no `dev.create` (slice 3),
no re-issue of an expired token (a new intake is one form away), and no push of
anything from the portal into a repository.

## Pillars

- P1 applies — `.agent-rfc/designs/portal-intake-pull.md`, written before any code,
  with the owner's three decisions (Postgres, network pull, `dev.create` on
  `developer`) taken as given and the one departure — `admin.apps` until slice 3 —
  stated in Approach for the owner to overrule.
- P2 applies — `portal/lib/ingestTokens.ts` is the credential this copies the
  shape of; `scripts/send_dev_record.py` the client discipline; `contract/gate/v1/`
  the contract layout; `portal/test/catalogs.test.ts` the mirror-and-pin pattern;
  `ISOLATION_VALUES`, `APP_ID`, `validate_tenant_id`, the `config_change` and
  `tenant_created` audit types are reused, not re-declared. Knowledge-graph impact:
  two new modules (`portal/lib/intakes.ts`, `runtime/intake.py`), three routes, one
  table. No dependencies, direct or transitive: `node:crypto` and Python's
  `urllib`, both already used for the same purpose.
- P3 applies — `portal/instrumentation.node.ts` traces every portal route, so the
  three routes are spanned without new code, and both state changes are in the
  signed audit log with the actor. The CLI side emits no span, like
  `scripts/send_dev_record.py`: provisioning commands carry no tracing today, and
  adding it is not this slice.
- P4 applies — `portal/test/catalogs.test.ts` is extended, and beside it
  `portal/test/intakes.test.ts` (validation, token shape, the id-must-match rule), `portal/test/intakesDb.test.ts` (create, read, expiry,
  single-use consume under a race, audit rows), `portal/test/middleware.test.ts`,
  `portal/test/catalogs.test.ts` extended, `runtime/test/test_intake.py` (a
  local HTTP stub serving `contract/intake/v1/fixture.json`: happy path, every
  refused field, http-to-a-remote-host refused before the token is sent, oversize
  response, timeout, consume-after-success-only). Mutation: the receiving-side
  validation and the https check go into `scripts/mutation_check.py`.
- P7 applies — `portal/lib/authz.ts` is the pattern: in `portal/lib/intakes.ts` no
  `any`, types derived from the catalog arrays; route handlers async; Python: stdlib,
  typed signatures, no Pydantic model for data the CLI did not write (the
  `P7-pydantic` narrowing, G6b).
- P8 applies — `portal/instrumentation.node.ts` resolves the endpoint for the
  portal side; the CLI side emits nothing, so there is no endpoint to resolve.
- P9 n/a — no orchestration: one request, one scaffold, one request.
- P10 n/a — no LLM call on either side.
- P11 applies — `runtime/cli.py`'s `validate_tenant_id` is the first of the
  receiving-side checks. `runtime/intake.py` receives the only untrusted input in
  this slice, over a network. Every closed-set field is re-validated against the CLI's
  own constants, so a value the portal accepted is not trusted for that reason.
  `tenant_id` must pass both `TENANT_ID_PATTERN` and `APP_ID`; it is the one field
  interpolated into files (`{{TENANT_ID}}` in the workflows, `tenant.yaml`, the
  `HITL_ENCRYPTION_KEY_<TENANT>` name), and both patterns are allow-lists that
  admit no quote, space, `$`, `{` or newline. The free-text `rfc.*` fields go only
  into the Markdown body of `.agent-rfc/001-scaffold.md` — never into YAML, a
  workflow, a shell line or a format string — with sizes capped on both sides and
  control characters other than newline and tab stripped. They carry the same
  trust as the same words typed at the author's terminal, which is the owner's
  argument and the reason no `prompt_guard` pass is added. A leading `❌` in the
  objective cannot fail a tenant build: `.github/scratch-tenants/build.sh:95`
  scans the hook's output log, not file contents — pinned by a test rather than
  asserted.
- P12 applies — `portal/lib/ingestTokens.ts`'s rules hold for the new token: shown
  once, `Cache-Control: no-store`, only its SHA-256 at rest, compared by hash
  lookup, never logged, never in an audit `details`. The CLI reads it by variable
  name only (`AGENTSMITH_INTAKE_TOKEN`), never as an argument, and refuses to send
  it over plain http to a remote host. 24-hour expiry and single-use consume bound
  a leaked token to one intake, once, for a day.
- P13 applies — `portal/middleware.ts` gains an unauthenticated path, so say
  exactly what gets weaker and what proves the boundary. The new path reads and
  consumes one intake with that intake's own token; it cannot list, create, or
  touch any other row. The boundary is proven by `portal/test/middleware.test.ts`,
  which did not exist — the five existing exclusions had no test either. Nothing
  else loosens: creation needs `admin.apps`, the narrowest existing permission
  that could hold it. Declared gap: a token that leaks inside its 24 hours lets
  its holder scaffold that one tenant on their own machine — which produces files
  on their machine, not in anyone's repository, and consumes the intake so the
  author notices.
- P14 applies — `scripts/test/test_scratch_tenants.py` scenarios pass no `--from`,
  so none goes stale. `contract/intake/v1/fixture.json` is the new projection both
  sides pin; a change to the record is a `v2`, not an edit to `v1`.
- P15 applies — `scripts/send_dev_record.py` sets the precedent, and
  `runtime/intake.py` distinguishes, in words and in exit codes (2: change
  something; 4: retry the same command):
  not configured (no URL or token set), refused (401/404/410 — wrong token, wrong
  id, consumed or expired, each named), invalid record (the field and the rule),
  and unreachable (network, 5xx). An expired intake and a consumed one are
  different answers (`410` with a reason), because the fix differs. No outcome
  reads as success unless the scaffold was written.
- P16 applies — `runtime/cli.py` consumes only after `init_tenant` returns. A
  failed fetch or validation writes nothing, so the retry is the same command. A
  failed scaffold leaves the intake unconsumed, so the retry is the same command.
  A failed consume leaves a complete scaffold and an intake that expires by itself;
  the CLI prints that plainly and exits 0, because the author's work succeeded.
  A scaffold that could not write the intake's RFC — another RFC was already
  there — is not consumed, so the author resolves it and re-runs with the intake
  still live.

## Deviations

none

## Dependencies

none — `node:crypto` in the portal and `urllib` in Python, each already used for
the same job (`portal/lib/ingestTokens.ts`, `scripts/send_dev_record.py`).

## Levers

- `validate-on-the-receiving-side` — the CLI re-checks every field against its own
  constants; the portal's checks are for the author, not the control.
- `use-existing-apis` — the token shape, the audit event types, `ISOLATION_VALUES`,
  `APP_ID`, `validate_tenant_id`, `AGENTSMITH_PORTAL_URL` and slice 1's `--ide`
  validation are all reused; nothing parallel is declared.
- `single-source-of-truth` — the wire format is `contract/intake/v1/`, tested from
  both sides.
- `pin-unremovable-duplicates` — the stack and IDE sets must exist in TypeScript and
  in Python; `portal/test/catalogs.test.ts` reads one and compares the other. The
  http-to-remote refusal exists in `scripts/send_dev_record.py` and
  `runtime/intake.py`, which ship to different places; a test asserts they refuse
  the same URLs.
- `consistent-auth-gates` — the new route authenticates the way `/api/dev/ingest`
  does, inside the handler, and is excluded in the matcher the way the others are.
- `denied-vs-missing` — expired and consumed are different `410`s; an unknown id
  and a mismatched id are the same `404`.
- `implemented-not-invoked` — each new test file is registered in
  `portal/package.json`, which lists them explicitly.
- `when-the-fallback-fails` — P16's three failure points each name where control
  goes and what the retry is.
- `small-verified-slices` — two commits, each testable alone; the form and the
  permission stay in slices 3 and 4.
- `search-before-writing` — every mechanism here was found in the code before it
  was designed.
