---
status: active
scope:
  - .github/workflows/self-test.yml
---
# The CI gate now refuses the admin too

## Problem

On 2026-10-01 the owner turned on `enforce_admins` for `main`. Every
description of the protection still says the opposite: the comment on the
`process-gates` job in `.github/workflows/self-test.yml` ("`enforce_admins` is
off, so the owner can still push past it"), `docs/process-gates.md` › Limits,
stated, and two backlog items that exist only because it was off. Since the
2026-09-30 change those descriptions were also wrong about which checks are
required — they name one, `Process gates (design + review)`, where all seven
are.

The gap they describe was real and was demonstrated on the day: `a44e586`
reached `main` with a failing lint check, pushed past "7 of 7 required status
checks are expected".

## Approach

Documentation only — no behaviour changes; the setting is already on.

- The workflow comment states the rule as it now is: every change reaches `main`
  through a pull request whose head passed all seven checks, the owner included.
- `docs/process-gates.md` › Limits says the same, keeps what is still open
  (`strict` is off; no approving review is required, because the sole owner
  cannot approve their own pull request), and adds the one local command that
  runs the CI gate over exactly the range CI will see — CHANGELOG rule included,
  the rule that turned PR #20 red.
- The two backlog items move to `docs/PRODUCT_ARCHIVE.md` as one completed
  entry, with the evidence.

## Pillars

- P1 applies — `.agent-rfc/designs/enforce-admins-on.md`, written before the edit.
- P2 applies — `docs/process-gates.md` and the workflow comment are the existing
  descriptions; they are corrected in place, nothing new is added beside them. No
  dependencies.
- P3 n/a — no execution path changes; a comment and documents.
- P4 n/a — no behaviour to test: the setting lives in GitHub, read back with
  `gh api …/protection` (recorded in the review), not in this repository.
- P7 n/a — no code.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — reads no untrusted content.
- P12 n/a — no credential; branch protection is a repository setting the owner holds.
- P13 applies — `.github/workflows/self-test.yml` documents a control that got
  STRONGER: the admin bypass is gone. What stays weaker is stated, not dropped:
  `strict` is off, and no approving review is required. Declared gap: the refusal
  of a direct push is configured and read back from the API, not demonstrated —
  the attempt was declined by the session's permission check.
- P14 n/a — no baselines or fixtures.
- P15 applies — `docs/process-gates.md` keeps "assume the admin path bypasses
  everything" out of the new text only because the API now reports
  `enforce_admins: true`; it says that is a reading, not a demonstration.
- P16 n/a — no fallback path changes.

## Deviations

none

## Dependencies

none

## Levers

- `docs-match-behaviour` — four descriptions said the opposite of the setting, and
  three named one required check where there are seven.
- `declared-vs-enforced` — the rule was declared in the docs and not enforced on the
  admin; now it is enforced, and the docs say exactly that much and no more.
- `backlog-discipline` — two items closed by the change leave the backlog in the same
  pull request, with evidence.
