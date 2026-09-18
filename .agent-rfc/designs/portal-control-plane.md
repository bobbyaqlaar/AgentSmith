---
status: approved
scope:
  - portal/**
  - scripts/process_gate.py
  - scripts/gate_models.py
  - runtime/workflows/base_workflow.py
  - workflow-templates/**
---
# The portal is the control plane: a Dev workspace and an Ops workspace

UI specification, approved by the owner on 2026-09-18. The gate reads only `active` designs, so
this document authorises no edit itself: each phase is built under its own design
(`.agent-rfc/designs/portal-phase1.md`, …), scoped to what that phase touches.

## Decisions (owner, 2026-09-18)

1. AgentSmith is the governance layer across the lifecycle of an app or agent, from design to
   operate (README).
2. **One application, two workspaces** — Dev and Ops — with one sign-in. An Administration area
   serves both.
3. **Seven roles.** Self-approval of a design deviation is allowed: an approval records who is
   accountable for the deviation, so a production defect can be traced back to it.
4. **Passkeys** at every sign-in, and again for a high-risk HITL decision. Nowhere else.
5. **Single organisation, many apps.** Multi-customer SaaS is a possible later step; nothing here
   may make it impossible, and nothing here builds it.
6. **Git stays the record.** The portal holds each app's repository link and shows what git
   holds. An approval made in the portal is committed to the app's repository directly.
7. GitHub is supported in full. GitLab is link-only for now.
8. Order: the Dev workspace first, then HITL, then administration and production approvals.
9. Roles combine: one person may be Developer and Design approver — on a small project, all of
   the development roles — and may move between them over time.
10. Logs are stored in Postgres.
11. HITL decisions work on a phone.

## Problem

The portal covers operations only: apps (called "tenants"), cost, incidents, runs, the
dead-letter queue, the audit log and widget tokens. Everything that happens before production —
designs, pillar answers, deviations and their approvals, reviews, gate verdicts, bypasses — lives
in each repository, readable only by someone who clones it and knows where to look. A HITL
decision cannot be made in the portal at all; KYC Sentinel records them with a script. And
nothing connects a production incident to the change that caused it.

## Shape

### One application, three areas

| Area | URL root | Who sees it |
|---|---|---|
| **Dev workspace** | `/dev` | Developer, Design approver, Administrator, Super user |
| **Ops workspace** | `/ops` | Operator, HITL reviewer, Release approver, Administrator, Super user |
| **Administration** | `/admin` | Administrator, Super user |

- The header carries a workspace switcher showing only the areas the signed-in user may enter.
  A user with one area lands in it and sees no switcher.
- Today's pages move under `/ops`. Their old URLs redirect permanently.
- **"App", not "tenant", everywhere in the UI.** In a later SaaS, a tenant is a customer
  organisation; using the word for an app now would collide. The database keeps `tenant_id` until
  a migration is worth its cost; the UI and new APIs say `app`.
- **An organisation id on every new table**, with one row today. It costs a column now and saves
  a rewrite if SaaS happens. No multi-organisation sign-in or isolation is built.

### Roles

One catalogue, in `portal/lib/authz.ts`, replacing today's viewer/operator/admin. A user holds
one or more roles; every role except Administrator and Super user is granted **per app**.

| Role | May |
|---|---|
| **Developer** | Read the Dev workspace for their apps. Approve a deviation in a design for their apps, their own included. |
| **Design approver** | Everything a Developer may, for their apps. Also approve an **allowlist entry** — an exemption from a mechanical pillar check (`P2`, `P3`, `P7`, `P10`, `P12`). |
| **Operator** | Read the Ops workspace for their apps; replay and discard dead-letter entries. |
| **HITL reviewer** | See and decide the HITL queue for their apps. Nothing else in Ops. |
| **Release approver** | Approve a production promotion for their apps. Read the Ops workspace for them. |
| **Administrator** | Every workspace action for every app. Manage users (except Administrators and Super users), apps, tokens, integrations. |
| **Super user** | Everything an Administrator may. Manage Administrators and Super users, recover a user's passkey access, rotate the portal's signing key, set organisation policy. |

- **Roles combine, and change.** One person may hold Developer and Design approver on the same
  app — on a small project, every development role — and an Administrator may change a user's
  roles at any time. Nothing requires two people.
- **Self-approval is allowed.** The approval record names the approver, and that name is the
  point: it is who answers for the deviation. It also records **the role the approval was made
  under**, because roles change: a trace-back months later must show that the approver held the
  right to approve at the time, not only today.
- **Denied is not missing.** A user without access to an app sees "You do not have access to
  <app>" with the Administrator to ask; a user asking for an app that does not exist sees "No app
  called <app>". Two screens, two next actions.

### Sign-in: a passkey every time

- **Passkeys (WebAuthn) with user verification** are the only way in. Password (basic auth)
  sign-in is retired.
- **Enrolment.** An Administrator invites a user by email and roles. The invitation link works
  once, for 24 hours, and registers a passkey. A user may register several (laptop, phone,
  security key) and name each.
- **The first Super user** is created on the portal's server by a command run at a terminal
  (`agentsmith portal bootstrap`). It prints a one-time enrolment link. Like `agentsmith approve`,
  it cannot be done from a browser, so no web request can create the first account.
- **Single sign-on stays optional.** Where the organisation uses OIDC, it supplies identity
  (email, name); the passkey is still required at every sign-in.
- **Recovery.** A user who has lost every passkey asks a Super user, who revokes the old
  credentials and issues a new enrolment link. Both actions go to the audit log.
- **Sessions** last 8 hours and end on sign-out, revocation, or a role change.
- **Step-up.** A high-risk HITL decision asks for the passkey again, and the assertion is bound
  to that decision (see the HITL queue section).

## Dev workspace — phase 1

Everything here is read from the Dev ingest (see Contracts). **The Dev database is a cache of
git**: it can be rebuilt from repository history, and every page says when its data was last
received.

### Apps (`/dev`)

The landing page: one row per app the user may see.

| Column | Shows |
|---|---|
| App | Name, linking to the app page |
| Repository | Provider icon and `owner/name`, linking out |
| Last gated commit | Short hash (linking to the provider), subject, verdict chip: passed · failed · escaped |
| Active designs | Count |
| Awaiting approval | Deviations with no approval — the number the Developer acts on |
| Sweep findings | Unrepaired bypasses |
| Last received | "Last received 3 min ago" — freshness of the ingest, per app |

States:
- **No apps registered** (empty): "No apps yet" and, for an Administrator, "Register an app".
- **App registered, nothing received** (a different fact): the row shows "No data received —
  CI has not sent a gate result" and a link to the setup instructions.
- **GitLab app**: "Gate data is not available for GitLab repositories yet" — unavailable, not
  zero.
- **Ingest older than 24 hours** is marked stale in amber; nothing is shown as current that is not.

### App › Changes (`/dev/apps/<app>`)

A timeline of gated commits, newest first, filterable by verdict and by author.

Each entry: subject; author; time; short hash linking to the provider; **verdict** with its
errors expanded on click; **design** and **review** links, as permalinks at that commit (files
move; a link at a commit does not break); the knowledge-graph scope (`kg:…` and the number of
files); a pillar summary (applies · n/a · gap counts). Commits before the app adopted the gates
are listed as "before adoption — not checked", not hidden.

### App › Designs (`/dev/apps/<app>/designs`)

Active designs first, then done. Each: title, status, scope globs, pillar summary, deviations
(approved · awaiting), and the commits that cited it.

### Design detail (`/dev/apps/<app>/designs/<slug>`)

- **Pillars** — a table of all fourteen: kind (applies · n/a · gap), the answer, and for a gap
  its backlog id.
- **Deviations** — each with its text, and either its approval (approver, time, the commit that
  recorded it) or **Approve** for a user who may.
- **Review** — every pass with its findings count, and whether the sign-off is complete.
- **Commits** — the commits that cite this design, with verdicts.
- A link to the design file at the latest commit.

### Approving a deviation — phase 2

Needs passkey sign-in and the GitHub App, so it ships with them.

1. **Approve** opens a panel showing the whole deviation text, the design at its commit, and the
   statement: "I approve this deviation and am accountable for it."
2. **Confirm approval** is disabled while the request is in flight, and says "Recording in git…".
3. The portal commits the approval record to the app's default branch (see Contracts).
4. Outcomes, each its own rendering:
   - **Recorded** — "Approved by <name> at <time>, recorded in <short hash>", linking to the
     commit.
   - **Not recorded** — "GitHub rejected the commit: <reason>. Nothing was approved." The
     approval does not appear anywhere as done.
   - **Already approved** by someone else meanwhile — shows theirs; no second record.
   - **The deviation changed since the page loaded** (its text hash differs) — "This deviation
     was edited after you opened it. Review the new text." No record is written.

There is no Reject. A deviation that should not stand is removed by editing the design; the
record of that is the commit that edits it.

### Approvals (`/dev/approvals`)

An inbox of deviations awaiting approval across the user's apps, and for a Design approver,
allowlist entries awaiting approval. Oldest first, each with app, design, deviation id, author
and age. The count in the header is the same number.

### App › Gates (`/dev/apps/<app>/gates`)

The commit gate's failures on the default branch, whether each has been repaired (the
`Repairs:` commit), and a link to the CI run that sent them. Each CI gate step's own latest
result needs GitHub's API, so it arrives with the GitHub App in phase 2.

### Trace-back (`/dev/apps/<app>/commits/<sha>`) — the accountability chain

For one commit: its designs and their deviations with approvals; which deployments shipped it;
and from phase 4, which production runs and incidents came from those deployments. From an
incident in the Ops workspace the chain runs the other way: run → deployment → commit → design →
deviation → approver.

This needs every run to carry the app's commit (see Contracts). Until it does, the page says
"Production runs do not report their commit yet" — not an empty list.

## Ops workspace — phases 3 and 4

Today's pages keep their behaviour, under `/ops`: Apps (cost, incidents, runs, suggested
promotions, widget token), Dead-letter queue, Audit log.

### HITL queue (`/ops/hitl`) — phase 3

Pending decisions across the reviewer's apps.

| Column | Shows |
|---|---|
| App, workflow | Links to the workflow's trace in Phoenix |
| Risk | low · medium · high, as the app declared it when it paused |
| Summary | What is being decided, as the app wrote it |
| Waiting | How long, and when the gate times out |

Sorted by time-out, soonest first. A decision past its time-out shows "Timed out at <time> —
the workflow took its time-out path", and cannot be decided.

**Decision page.** The evidence the app supplied (already redacted by the app's own PII rules),
the trace link, and **Approve** / **Reject**. A reason is required for Reject and optional for
Approve.

- **High risk** asks for the passkey again. The assertion signs this decision — app, workflow,
  gate, choice, and a hash of the evidence shown — so it cannot be replayed onto another.
- Reject asks for confirmation ("This ends the application's review with a refusal").
- States after submit: **Sending** → **Delivered to the app** → **Confirmed by the workflow**,
  or **Not delivered — <reason>**, with Retry. A decision is never shown as made until the
  workflow confirms it.
- **Already decided** by someone else, or timed out meanwhile: the page shows that outcome and
  who made it. No second decision is sent.

### Production approvals (`/ops/releases`) — phase 4

Promotions awaiting approval: the pull request `agentsmith tenant promote` opens from staging to
production. Each shows the commits included, their gate verdicts, the deviations they carry
(linking to the Dev workspace), and the eval results. **Approve** submits an approving review on
the pull request through the GitHub App. It needs the Release approver role; it does not ask for
a passkey (decision 4).

### Monitoring — phase 4, and one open decision

- **Traces** — recent traces per app, linking out to Phoenix. The portal does not rebuild a trace
  viewer.
- **Incidents** — today's history entries, each with its trace-back link.
- **Logs** — phase 5, stored in Postgres (see Contracts). Until an app sends logs, its page
  states "This app does not send logs yet" — never an empty list that looks like "no errors".

## Administration (`/admin`)

Built in step with the phases that need it.

- **Users** (phase 2) — invite; assign roles per app; disable; revoke sessions; list and revoke
  passkeys. An Administrator cannot change an Administrator or a Super user.
- **Apps** (phase 1) — register an app: name, repository URL, provider (GitHub · GitLab), default
  branch. Issue and rotate its **ingest token**: shown once, stored hashed. Budget cap, Phoenix
  endpoint, HITL webhook URL and secret (phase 3).
- **Integrations** (phase 2) — the GitHub App: installed or not, on which repositories, and the
  permissions it holds.
- **Organisation** (Super user) — session length, the portal signing key (rotate), and the
  governance registry version the portal reads.
- **Audit** — every administrative action, sign-in, approval and HITL decision, in the existing
  tamper-evident audit log.

Rotating a token or the signing key, revoking a passkey and disabling a user each ask for
confirmation and say what stops working.

## Contracts

### Dev ingest — phase 1

`POST /api/dev/ingest`, sent by the app's CI after the process-gates job, authenticated by the
app's ingest token.

- **The gate produces the payload.** `process_gate.py ci --json` emits the verdict it already
  computes, per commit. The portal never re-derives a verdict (`one-verdict`).
- Per commit: hash, parent, subject, author, time, verdict, errors, notes; the design (path,
  status, scope, pillar kinds, deviations with a hash of each text and any approval id); the
  review (path, passes with findings counts, sign-off complete, `KG query`); sweep findings.
- **Idempotent** on (app, commit): a re-run replaces the stored copy and never duplicates it.
- Validated on arrival (schema, sizes); a malformed payload is refused with its reason, and the
  app's "Last received" does not advance.
- `workflow-templates/` gains the step, so a new tenant sends from its first push.

### An approval made in the portal — phase 2

- The record extends today's `Approval`: `channel: "portal"`, the approver's identity, the
  role they approved under, the design's commit, the deviation text hash, a key id, and a **signature by the portal's signing
  key** over the canonical record.
- **The gate verifies the signature offline**, with the public key committed in the app's
  repository. A record the portal did not sign fails, however it got into the file.
- **The GitHub App commits it to the default branch directly**, with message
  `chore(approval): <design> <deviation>`.
- **The commit gate must accept that commit.** `.agenticframework/**` is gated in tenant repos, so
  an approval-only commit would be refused for lacking design and review trailers. The gate learns
  one rule: a commit whose only change is appending signed, valid records to `approvals.jsonl`
  needs no trailers. Anything else in that commit, or a record that does not verify, and the
  normal rule applies.

### HITL — phase 3

- **Pending**: when `run_with_hitl_gate` pauses, the runtime posts app, workflow, gate id, risk,
  summary, evidence, time-out and trace id to the portal. Risk is the app's declaration; the
  portal does not guess.
- **Decision**: the portal posts the decision to the app's HITL webhook, signed with the app's
  webhook secret — the pattern dead-letter replay already uses. The app's worker signals the
  workflow.
- **Confirmation**: the worker posts the outcome back. Only then is the decision shown as made.

### Logs — phase 5

- **The portal receives logs over OTLP/HTTP** (`POST /v1/logs`, the OpenTelemetry standard),
  authenticated by the app's ingest token. An app's existing OpenTelemetry setup points its log
  exporter there; no collector is required, and an organisation that runs one can forward to the
  same endpoint.
- **Stored in Postgres**, in a table partitioned by day: time, app, severity, body, attributes,
  trace id and span id. The trace id links each line to Phoenix and to the run.
- **Retention** is 30 days by default, set per organisation; old partitions are dropped whole.
- **Redaction happens in the app, before export**, by the same rules as traces
  (`runtime/trace_redactor.py`). The portal stores what it receives and does not un-redact.
- **Limits are stated, not discovered.** Postgres serves this at the volume of one organisation's
  apps. The page shows the rows stored and the oldest retained day. An ingest over the
  per-app rate limit is refused with 429 and counted, so dropped logs are a number on the page,
  not a silence.

### Runs carry their commit — phase 4

`agent_runs` gains `app_commit`, reported by the runtime from the deployed build. NULL means the
app is too old to report it — a different fact from an app that failed to. It is a wire-contract
addition (see `portal/lib/wireContract.ts`), within the major version.

## Phases

| Phase | Ships | Needs |
|---|---|---|
| 1 | Workspace shell and switcher, the seven roles on today's sign-in, the Dev workspace read-only, Admin › Apps, Dev ingest, `ci --json` | — |
| 2 | Passkey sign-in and enrolment, Admin › Users and Integrations, deviation and allowlist approvals committed through the GitHub App, the gate's signed-approval rule | Phase 1; a GitHub App registered by the owner |
| 3 | HITL queue, step-up for high risk, HITL contracts in the runtime | Phase 2 |
| 4 | Production approvals, traces list, trace-back through `app_commit` | Phase 3 |
| 5 | Logs: OTLP/HTTP ingest, Postgres storage, the logs page with search by app, severity, time and trace | Phase 4 |

## Screens: rules every page follows

- **Empty, unavailable and zero are three renderings** (`failure-is-not-a-result`). Each page
  above names which one applies where.
- **Every number someone could act on says when it was measured** — counts, costs, ages
  (`stale-data-is-labelled`).
- **Every write disables its control while in flight** and shows what it is doing
  (`no-double-submit`).
- **Every one-way action confirms first** and says what it ends (`irreversible-needs-confirmation`).
- **Keyboard and screen reader**: every control reachable by keyboard, every icon-only control
  labelled, focus returned to the list after a decision.
- **Viewports**: designed for 1280 px and up. **The HITL queue and decision page work on a phone
  (360 px and up)**, passkey step-up included — a phone is where most people's passkeys already
  are. On a phone the queue is a list of cards, the evidence folds into sections, and Approve and
  Reject sit at the bottom of the screen within thumb reach, never side by side with nothing
  between them. Every other page is usable at 768 px and read-only below it.
- **The existing component language**: the current header, table, card and chip styles, light and
  dark. No new colours or spacing values; the verdict and risk chips reuse the portal's existing
  status colours.

## Open questions

None. The three raised on 2026-09-18 are answered in decisions 9–11.

## Pillars

- P1 applies — this specification precedes any code: `.agent-rfc/designs/portal-control-plane.md`; each phase is activated separately.
- P2 applies — new dependencies are one WebAuthn server library in `portal/package.json` (phase 2) and Ed25519 verification in the gate; each is named and approved when its phase starts.
- P3 applies — every portal route already emits spans through `portal/lib/tracing.ts`; new routes use it.
- P4 applies — each phase's tests are written first; the ingest and the approval rule are tested against the gate's own output in `scripts/test/`.
- P7 applies — payloads are validated on arrival; the Python side uses the Pydantic models in `scripts/gate_models.py`.
- P8 applies — ingest freshness and HITL delivery states are the operator's signals, shown on the pages that use them.
- P9 n/a — the portal orchestrates no agents.
- P10 n/a — the portal makes no model calls.
- P11 applies — ingest payloads, HITL evidence and webhook responses are data from other systems: validated in `portal/lib/`, rendered as text, never as markup.
- P12 applies — ingest tokens and webhook secrets are shown once and stored hashed; the signing key never leaves the server; `portal/lib/bearerAuth.ts` stays the one bearer check.
- P13 applies — portal approvals are signed and verified by the gate offline, so a portal compromise cannot forge an approval the gate accepts: `scripts/gate_models.py`.
- P14 applies — the Dev database is a cache of git and can be rebuilt; nothing is authoritative in it.
- P15 applies — "no data received", "unavailable for GitLab", "not recorded" and "timed out" are distinct states on the pages above.
- P16 applies — a failed approval commit or undelivered HITL decision is shown as not done, with the reason and a retry, in `portal/`.

## Deviations

none

## Dependencies

Named per phase above; none is added by this specification.

## Levers

- `one-verdict` — the gate's verdict is sent, not recomputed by the portal.
- `single-source-of-truth` — git holds designs, reviews and approvals; the portal caches them.
- `consistent-auth-gates` — one role catalogue, one check, on every route.
- `denied-vs-missing`, `failure-is-not-a-result`, `stale-data-is-labelled`, `no-double-submit`, `irreversible-needs-confirmation` — specified per page above.
- `two-owners-two-cadences` — the ingest and HITL contracts cross between the portal and apps on their own release cycles; each carries a version.
- `declared-vs-enforced` — an approval is enforced by the gate's signature check, not by trusting the portal.
