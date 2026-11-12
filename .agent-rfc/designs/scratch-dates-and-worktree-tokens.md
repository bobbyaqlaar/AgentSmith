---
status: active
scope:
  - .github/scratch-tenants/build.sh
  - .github/scratch-tenants/date-fixtures.sh
  - scripts/test/test_scratch_tenants.py
  - scripts/agent_tokens.py
  - scripts/test/test_agent_tokens.py
---
# The scratch tenant's evidence is dated when it is built, and a worktree's commits carry their tokens

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R24 and P2-R4, two minors the
owner asked for before the release. Follows `.agent-rfc/designs/compliance-profile-holds.md` (the drill dated at
build time, #116) and `.agent-rfc/designs/coding-agent-tokens.md`.

## Problem

- **P2-R24.** The `dubai-gov` scratch tenant's 25 attestations are dated 2026-11-08 in its fixture. Since R15 a
  recurring signature expires on the catalogue's period, so `OB-LOG-REVIEW` (30 days, blocks production) lapses on
  2026-12-08 and the weekly Scratch tenants run fails from 14 December with no change to the code. #116 dated the drill
  at build time and left the signatures, which are the same kind of fixture.
- **P2-R4.** The token ledger lives under `git rev-parse --absolute-git-dir`, which in a linked worktree is
  `.git/worktrees/<name>`. A session whose hooks run in the main checkout records there; its commits in a worktree
  read the worktree's own directory, find nothing, and carry `Agent:` alone. All 11 commits of #115 and #116 were made
  that way.

## Approach

- **P2-R24.** One script, `.github/scratch-tenants/date-fixtures.sh <dir>`, dates a profile's evidence when the tenant
  is built: each drill's `at`, and each attestation's `attested_at`, to now, with `expires_at` left as written (null,
  so the catalogue's period decides). `build.sh` calls it in place of its inline drill loop. A test runs the script on
  a copy of the fixture and holds every date to the run's own time, and asserts the production verdict's signatures
  would still be live a year on from the fixture's written date only because of it.
- **P2-R4.** The ledger moves under `git rev-parse --path-format=absolute --git-common-dir`, which every worktree of a
  repository shares; entries are already one per session, so worktrees do not mix sessions. A ledger left in a
  worktree's own directory by the old code is not read (it holds only sessions that could not be matched anyway).

## Pillars

- P1 applies — P2-R24 and P2-R4 are the requirement; `.agent-rfc/designs/scratch-dates-and-worktree-tokens.md` is the plan.
- P2 applies — `.github/scratch-tenants/date-fixtures.sh` replaces the inline loop in `.github/scratch-tenants/build.sh`; `scripts/agent_tokens.py` changes one path.
- P3 n/a — no spans or evaluations.
- P4 applies — `scripts/test/test_scratch_tenants.py` runs the dating script; `scripts/test/test_agent_tokens.py` commits from a linked worktree; hand mutants after.
- P7 n/a — no model.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 n/a — no untrusted content.
- P12 n/a — no secrets.
- P13 applies — `.github/scratch-tenants/build.sh` keeps asserting the production verdict passes; only the fixture's dates move, never the check.
- P14 applies — `.github/scratch-tenants/profiles/dubai-gov/agenticframework/attestations.jsonl` stays as written; its dates are set at build time, so the fixture no longer ages.
- P15 applies — `scripts/agent_tokens.py`: a commit with a measurement now carries it, instead of reading as "not measured".
- P16 applies — `CHANGELOG.md` says a ledger in a worktree's own directory is left behind; the next session-start hook writes the shared one.

## Deviations

none

## Dependencies

none

## Levers

- `grep-for-siblings` — the signatures beside the drill #116 dated (P2-R24).
- `fixture-truth` — a fixture's dates are set when it is used, not when it was written.
- `environment-parity` — the main checkout and its worktrees read one ledger (P2-R4).
- `test-that-cannot-fail` — hand mutants.
