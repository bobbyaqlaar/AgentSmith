---
status: done
scope:
  - portal/app/dev/layout.tsx
  - portal/app/dev/intakes/**
  - portal/components/IntakeForm.tsx
  - portal/lib/intakeCatalog.ts
  - portal/lib/intakes.ts
  - portal/app/api/dev/intakes/**
  - portal/package.json
  - portal/tsconfig.json
  - portal/test/**
---
# Starting a tenant from the portal: the form

## Problem

Slice 4, the last of the portal-intake plan. Slices 1–3 shipped the pieces:
`--ide` recorded (`7aa6dfb`), the intake record and `tenant init --from`
(`9d5120f`, `a44e586`), and `dev.create` for Developers with an id that must be
new (`f237891`). Today an intake can only be created by an API call. There is no
screen.

Two things the screen has to get right were found while designing it:

1. **A token shown once, plus slice 3's refusal, is a trap.** If the author
   closes the tab before copying the token — or the create response is lost —
   the token is gone for good, and the open intake holds the tenant id for 24
   hours: every retry answers "intake N already names it". On an API this was a
   corner case. On a form it is the commonest mistake anyone will make.
2. **The client cannot import `portal/lib/intakes.ts`.** It imports `node:crypto`
   and the database pool, so the stack, IDE and limit constants the form needs
   to render its choices live in a module the browser cannot load.

## Approach

### The journey

1. In the Dev workspace, a **"Start a tenant"** link appears for anyone holding
   `dev.create` — added to `AreaNav` the way `/ops` adds "Audit log" for
   `admin.audit`.
2. **`/dev/intakes/new`** — the form. The tenant id; the stack; then the options,
   each with a one-line hint (isolation, architecture, agentic, IDEs); then the
   first RFC: an objective, acceptance criteria one per line, files to modify one
   per line.
3. **On success the form is replaced by the issued panel** — `IngestTokenPanel`'s
   language: amber, "Copy this now — it is not shown again", a Copy button. It
   gives the author exactly what to run, in order, on their own machine:

       mkdir <tenant> && cd <tenant> && git init
       export AGENTSMITH_PORTAL_URL=<this portal's origin>
       agentsmith tenant init --from <id>

   and says the CLI will ask for the token — paste it there, which keeps it out
   of shell history — and when the intake expires, in local time.
4. **If they lost it:** the 409 for an intake THEY issued says so and offers
   **Replace it** — withdraw that intake and issue a new one for the same id.

### The pieces

- **`portal/lib/intakeCatalog.ts`, client-safe.** `INTAKE_STACKS`, `INTAKE_IDES`,
  `INTAKE_LIMITS` move here from `portal/lib/intakes.ts`, which re-exports them so
  no import changes; plus `INTAKE_ARCHITECTURES` (below) and `linesOf(text)`, the
  one place a textarea becomes a list — trimmed, blank lines dropped.
- **Architecture becomes a select, and the portal checks the id.**
  `INTAKE_ARCHITECTURES` mirrors `templates/architectures.yaml`'s five style ids
  and display names, pinned by `portal/test/catalogs.test.ts` reading the YAML,
  the way it reads `runtime/cli.py`'s stacks. `parseIntakeInput` then refuses an
  id not in it, so a typo is caught where it is typed rather than at
  `tenant init`. This reverses a slice-2 decision ("a copy here would be a third
  catalogue"): a select cannot render without the list, and a pinned mirror is not
  a free-floating copy.
- **Replace, creator only.** `POST /api/dev/intakes` accepts `replace: <intake_id>`.
  Inside the existing locked transaction: the open intake for that tenant id must
  be that id AND have been issued by the same actor; it is withdrawn — its
  `expires_at` set to now, so a CLI holding its token gets the existing "expired —
  ask for a new intake" — audited as `config_change` / `intake_withdrawn`; then the
  new one is issued as usual. Anyone else's open intake still answers 409, without
  the offer. No new column: an expiry in the past is already what "unusable, ask
  again" means to every reader.
- **The issued panel holds the token in component state only** — never the URL,
  never storage — and "Start another" clears it.

**Deliberately not done:** no list of open intakes (a later screen, if wanted); no
way to replace someone else's intake; no draft saving.

## Pillars

- P1 applies — `.agent-rfc/designs/intake-form.md`, the last slice of the owner's
  four-slice plan; the replace flow is the one addition, raised before building.
- P2 applies — `portal/components/AppForm.tsx` (collect, let the server validate,
  say what it said) and `portal/components/IngestTokenPanel.tsx` (a token once, its
  Copy button, the secrets to set) are the patterns; their class constants are
  reused, not redefined. `AreaNav`'s conditional link, `can()`, `createIntake`'s
  lock. No dependencies.
- P3 applies — `portal/lib/intakes.ts`: the replace runs in `createIntake`'s
  transaction, under the route's automatic span, and is audited. The page is a
  server component behind the existing middleware.
- P4 applies — `portal/test/intakes.test.ts`: `linesOf`, the architecture refusal,
  `replace`'s shape. `portal/test/intakesDb.test.ts`: the creator replaces their own
  open intake and the old token gets 410 expired; another actor cannot; replacing
  the wrong id cannot; the audit names `intake_withdrawn`. `portal/test/catalogs.test.ts`
  pins `INTAKE_ARCHITECTURES` to `templates/architectures.yaml`. The screen is checked
  in a real browser: the full journey at desktop and phone widths, by keyboard alone,
  with the token never in the URL. Portal mutations by hand, as before.
- P7 applies — `portal/components/AppForm.tsx`'s rules: `"use client"` only on the
  form, the page a server component; no `any`; types derived from the catalog arrays.
  And `portal/tsconfig.json` gains `erasableSyntaxOnly`: the portal's tests run under
  Node's strip-only TypeScript, which rejects syntax `tsc` accepts (a constructor
  parameter property broke them while this was built). The whole portal already
  compiles under it, so `tsc` now refuses what the test runner would.
- P8 n/a — no new telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — `portal/lib/intakes.ts`'s `parseIntakeInput` stays the control; the
  form only collects. React escapes everything it renders, and nothing the author
  typed is rendered back except inside the inputs.
- P12 applies — `portal/components/IngestTokenPanel.tsx`'s rules for the token: shown
  once, copy button, never in the URL or storage, cleared on "Start another"; the
  instructions keep it off the command line and out of shell history.
- P13 applies — `portal/app/api/dev/intakes/route.ts` gains a way to end an open
  intake early. It is narrower than any existing permission: only the actor who
  issued it, only the one named, only while it is open, and only by issuing its
  replacement in the same transaction. Nothing else loosens.
- P14 applies — `portal/test/catalogs.test.ts` gains the architecture pin; the
  contract is unchanged (its `architecture` is still a shape, and every id in the
  mirror matches it).
- P15 applies — `portal/components/AppForm.tsx` shows one error line for every failure;
  the new `IntakeForm` keeps three outcomes apart instead: the
  portal refused the input (its message, at the form), the id is taken (409 — with
  "Replace it" only when it is the author's own), and the portal could not be
  reached ("nothing was created", so they know a retry is safe).
- P16 applies — `portal/lib/intakes.ts`: a lost token or a lost response is
  recoverable by the author in one click, without an administrator and without the
  24-hour wait; a replace that fails withdraws nothing, because the withdrawal and the
  new issue are one transaction.

## Deviations

none

## Dependencies

none

## Levers

- `intuitive-journey` — designed from the nav link to a running scaffold, including
  the commands in order and the step people will get wrong.
- `failure-is-not-a-result` / `denied-vs-missing` — refused, taken and unreachable are
  three renderings; a user without `dev.create` sees "you need the Developer role", not
  a missing page.
- `no-double-submit` — the submit button is disabled from click to response, and the
  handler returns early while busy: a second create would otherwise get 409 for the
  first one and could overwrite the panel showing its token.
- `keyboard-and-screen-reader-operable` — native controls with labels and hints tied by
  `aria-describedby`; the outcome announced through `role="status"` / `role="alert"`,
  as `AppForm` does.
- `works-at-real-viewport-sizes` — one column, `max-w-xl`, checked at phone width.
- `matches-the-existing-component-language` — `AppForm`'s and `IngestTokenPanel`'s
  classes and amber token panel, not new ones.
- `pin-unremovable-duplicates` — the architecture ids exist in YAML and TypeScript;
  pinned.
- `irreversible-needs-confirmation` — Replace withdraws an intake: the button says so
  ("Replace — the earlier token stops working").
