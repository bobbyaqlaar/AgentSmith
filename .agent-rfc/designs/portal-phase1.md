---
status: active
scope:
  - scripts/process_gate.py
  - scripts/gate_models.py
  - scripts/test/test_process_gate.py
  - scripts/test/test_dev_record.py
  - portal/**
  - workflow-templates/**
  - .github/workflows/self-test.yml
  - .github/workflows/scratch-tenants.yml
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Portal phase 1 — the Dev workspace, read-only

Phase 1 of `.agent-rfc/designs/portal-control-plane.md`, the specification the owner approved on
2026-09-18. That document holds the what and why; this one holds how phase 1 is built.

## Problem

The portal shows operations only. Every fact about how a change was designed, reviewed and gated
sits in its repository. Phase 1 makes those facts visible across every app, without the portal
becoming a second record, and puts the portal into the shape later phases build on: one
application, three areas, seven roles.

## Approach

Seven slices, each committed on its own with its own review record
(`.agent-rfc/reviews/portal-phase1-s<N>.md`).

### S1 — the gate writes what it decided (`process_gate.py ci --json FILE`)

- `ci` gains `--json FILE`. The same run that prints the verdict writes one record per commit in
  the range, so the portal is sent **the verdict the gate reached**, never a re-derivation
  (`one-verdict`). Without the flag nothing changes.
- A record: hash, parent, subject, author name and email, commit time; `adopted`, `gated`;
  `verdict` — `passed`, `failed`, `passed_with_notes` (report-mode findings), `not_gated`,
  `before_adoption`; `errors`, `notes`; `repairs` (the hashes a `Repairs:` trailer names).
- When the commit names a design and it resolves: path, title, status, scope, each pillar's kind
  (`applies` · `n/a` · `gap` · `deviation`), and each deviation's id, a SHA-256 of its text and
  its approval id. When it names a review: path, each pass's findings count, whether the sign-off
  is complete, and the `KG query` hash. A record that does not resolve says so — `null` with the
  reason — rather than being omitted.
- `"schema": 1` on the document. The portal refuses a schema it does not know.

### S2 — seven roles (`portal/lib/authz.ts`)

- **Grants replace role + scope.** `Access` becomes a list of grants, each a role and the apps it
  covers (`"*"` or a list). A user may hold several: one person may be Developer and Design
  approver on the same app.
- **Permissions are the one catalogue.** Each role maps to permissions — `dev.read`,
  `dev.approve`, `dev.allowlist`, `ops.read`, `ops.dlq`, `ops.hitl`, `ops.release`, `admin.apps`,
  `admin.users`, `admin.org` — and every check asks for a permission, never a role:
  `can(access, permission, app?)` and `appsWith(access, permission)`. Administrator and Super
  user hold their permissions on every app regardless of the grant's list.
- **Configuration** stays where it is in phase 1 (users move to the database in phase 2).
  `OPS_PORTAL_USERS` and `OPS_PORTAL_SSO_USERS` entries accept `grants: [{role, apps}]`.
- **Old configuration keeps working** — the compatibility obligation within a major version.
  An entry with the old `role` + `tenants` maps to exactly the permissions it has today:
  `viewer` → `ops.read`; `operator` → `ops.read` + `ops.dlq`; `admin` → Administrator. The
  single-user `OPS_PORTAL_USER` stays Administrator on every app. Old names are accepted, never
  offered: the portal logs one deprecation line at start-up naming the new form.
- **One trusted header.** Middleware strips any client-supplied copy and sets `x-af-grants`
  (the old two headers are retired together, so no route can read half of the old contract).
- Every existing call site moves to `can` / `appsWith`: `canWrite` becomes `ops.dlq`,
  `canAdmin` becomes `admin.apps`.

### S3 — the Dev ingest (`POST /api/dev/ingest`)

- **Schema** (`portal/db/schema.sql`, idempotent like the rest):
  - `orgs` — one row, `default`. New tables carry `org_id`.
  - `tenants` gains `repo_url`, `repo_provider` (`github` · `gitlab`), `default_branch`.
    The table keeps its name; the UI says "app".
  - `app_ingest_tokens` — app, SHA-256 of the token, created, created by, revoked.
  - `dev_commits` — app, commit, and the S1 record as columns plus `design` and `review` as
    JSONB; `received_at`. Primary key (app, commit).
  - `dev_ingest_runs` — app, received at, the CI run URL, commits received, schema.
- **Authentication:** `Authorization: Bearer <token>`, looked up by its SHA-256 among the app's
  unrevoked tokens. The app comes from the token, never from the body — a token for one app
  cannot write another's commits.
- **Validation on arrival** (`portal/lib/devIngest.ts`): schema version, types, lengths (a commit
  subject at most 1,000 characters, at most 500 commits per request, 2 MB per body). A malformed
  body is refused with its reason, and nothing is stored — not the valid half.
- **Idempotent:** upsert on (app, commit). The same CI run posted twice stores one copy.
- The route is excluded from the human middleware, like `/api/sync` and `/api/runs/ingest`.

### S4 — the shell: three areas

- `/dev`, `/ops`, `/admin`. The header's switcher lists the areas the user holds a permission
  in; a user with one area sees no switcher.
- Today's pages move: `/` → `/ops`, `/tenants/<id>` → `/ops/apps/<id>`, `/dlq` → `/ops/dlq`,
  `/audit` → `/ops/audit`. The old paths redirect permanently (`next.config.js`). `/` redirects to
  the first area the user may enter. The API routes keep their paths: CI jobs call them.
- "Tenant" becomes "app" in page text.

### S5 — the Dev pages

`/dev` (apps), `/dev/apps/<app>` (changes), `/dev/apps/<app>/designs`,
`/dev/apps/<app>/designs/<path>`, `/dev/approvals`, `/dev/apps/<app>/gates`,
`/dev/apps/<app>/commits/<sha>` — as the specification describes, with its states.

One change to the specification, recorded there: **App › Gates** shows the commit gate's
failures and their repairs, and links to the CI run that sent them. The specification also
promised each CI gate step's latest result; the ingest carries the process gate's verdict only,
and fetching step results means reading GitHub's API, which belongs with the GitHub App in
phase 2.

### S6 — Administration › Apps

`/admin/apps`: register an app (id, name, repository URL, provider, default branch), edit it,
issue and rotate its ingest token. A new token is shown once, with the exact secret name to set
in the app's CI; rotating revokes the old one after confirmation. Every action goes to the audit
log. Needs `admin.apps`.

### S7 — CI sends the record

- The process-gates job in `workflow-templates/` and AgentSmith's own `self-test.yml` run
  `ci --json dev-record.json`, then post it when `AGENTSMITH_PORTAL_URL` and
  `AGENTSMITH_PORTAL_INGEST_TOKEN` are set. When they are not, the step says so in one notice and
  succeeds: a tenant without a portal is not a failed build.
- A refused post (4xx) fails the step with the portal's reason; the portal unreachable (5xx,
  timeout) is a warning — the gate's verdict does not depend on the portal being up.
- Documentation: the manual's Ops Portal section and the design document's portal section
  describe the Dev workspace, the roles and the new configuration form.

## Pillars

- P1 applies — this design and `.agent-rfc/designs/portal-control-plane.md` precede the code.
- P2 applies — no dependency is added: validation is hand-written in `portal/lib/devIngest.ts`, SHA-256 comes from Node's `crypto`.
- P3 applies — the ingest route and the new pages run on the traced pool in `portal/lib/db.ts` and the spans in `portal/lib/tracing.ts`; the gate's `ci` is already traced.
- P4 applies — tests first per slice: `scripts/test/test_dev_record.py` for S1, `portal/test/authz.test.ts` for S2, `portal/test/devIngest.test.ts` for S3's validation and `portal/test/devIngestDb.test.ts` for its storage.
- P7 applies — the Python record is built from the Pydantic models in `scripts/gate_models.py`; the portal validates on arrival in `portal/lib/devIngest.ts`.
- P8 applies — "last received" per app is the freshness signal, stored in `dev_ingest_runs` (S3) beside the portal's other tables in `portal/db/schema.sql`.
- P9 n/a — no agents are orchestrated.
- P10 n/a — no model calls.
- P11 applies — commit subjects, design titles and error text come from repositories: validated in `portal/lib/devIngest.ts` (S3) and rendered as text, never markup; repository links go through `portal/lib/safeUrl.ts`.
- P12 applies — ingest tokens are shown once and stored as SHA-256 in `app_ingest_tokens`, looked up by hash in `portal/lib/ingestTokens.ts` the way widget tokens are.
- P13 applies — the portal is sent the verdict `scripts/process_gate.py` reached and cannot change it; `dev_commits` is a cache that can be rebuilt from git.
- P14 applies — the ingest's `schema` field pins the record's shape; `scripts/test/test_dev_record.py` pins what the gate emits.
- P15 applies — `before_adoption`, `not_gated` and `passed_with_notes` are distinct verdicts, pinned by `scripts/test/test_dev_record.py`; "no data received", "not available for GitLab" and "stale" are distinct states on the Dev pages (S5).
- P16 applies — a refused ingest stores nothing and says why; an unreachable portal warns without failing the gate, in `workflow-templates/`.

## Deviations

none

## Dependencies

None added. Node's `crypto` and the portal's existing `pg`; Python's standard `hashlib` and
`json`.

## Levers

- `one-verdict` — the gate's verdict travels; the portal renders it.
- `one-catalog` — roles and permissions live in `portal/lib/authz.ts` only.
- `consistent-auth-gates` — every page and route asks `can(access, permission, app)`.
- `validate-on-the-receiving-side` — the ingest validates before storing anything.
- `out-of-order-and-repeated` — the ingest is an upsert keyed on (app, commit).
- `two-owners-two-cadences` — the record carries a schema version; the portal refuses unknown ones.
- `failure-is-not-a-result`, `denied-vs-missing`, `stale-data-is-labelled` — on every Dev page.
- `environment-parity` — the tests run the same validator the route runs.
- `small-verified-slices` — seven slices, each reviewed and committed on its own.
