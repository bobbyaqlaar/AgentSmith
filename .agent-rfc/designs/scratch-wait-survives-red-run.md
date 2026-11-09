---
status: active
scope:
  - .github/workflows/scratch-tenants.yml
  - scripts/test/test_scratch_tenants.py
---
# The scratch wait step survives a red tenant run

## Problem

GitHub runs a `run:` step under `bash -e`. The wait step in `.github/workflows/scratch-tenants.yml` calls `gh run watch --exit-status` and reads `rc=$?` on the next line, so a red tenant run aborts the step on the watch itself. Nothing after it runs. The step ends `exit code 1` with no message, and `expect-ungraded.sh` is never reached. Seen on run 42578775473, after `.agent-rfc/designs/scratch-profile-expects-ungraded.md` shipped.

## Approach

`gh run watch … || rc=$?` with `rc=0` before it, in both jobs that wait. The diagnostics that were already written then run as intended.

A test runs the real step text under `bash -e` against a fake `gh`, because a test of the script alone is what missed this.

## Pillars

- P1 applies — `.agent-rfc/designs/scratch-wait-survives-red-run.md` is the plan; the log of run 42578775473 is the requirement.
- P2 applies — two lines in `.github/workflows/scratch-tenants.yml`; no new file or dependency.
- P3 n/a — a CI step; no application code path.
- P4 applies — `scripts/test/test_scratch_tenants.py` runs the step under `bash -e`; mutation-checked by hand.
- P7 applies — `.github/workflows/scratch-tenants.yml` keeps `set -uo pipefail`; the fix is written for the `-e` the runner adds.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 n/a — nothing new reads untrusted content.
- P12 n/a — no secrets involved.
- P13 applies — `.github/workflows/scratch-tenants.yml` still fails on a red run, now with its reason; `scripts/test/test_scratch_tenants.py` holds that.
- P14 n/a — no fixture or baseline changes.
- P15 applies — `scripts/test/test_scratch_tenants.py` holds that a red run is reported as one and never read as a pass.
- P16 applies — reverting is one commit; `.github/workflows/scratch-tenants.yml` only.

## Deviations

none

## Dependencies

none

## Levers

- `implemented-not-invoked` — the script existed and the step never reached it; the test runs the step.
- `grep-for-siblings` — both jobs that wait are fixed.
- `failure-is-not-a-result` — a red run is reported with its reason.
