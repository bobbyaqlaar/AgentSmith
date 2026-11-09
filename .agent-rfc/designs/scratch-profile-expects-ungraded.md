---
status: done
scope:
  - .github/scratch-tenants/expect-ungraded.sh
  - .github/scratch-tenants/apps/python-dubai-gov/app/guards.py
  - .github/workflows/scratch-tenants.yml
  - scripts/test/test_scratch_tenants.py
---
# The scratch tenant on the profile expects its evals to be refused

## Problem

The first GitHub run of the `python-dubai-gov` scratch tenant (run 42567256220, attempt 2) went red in the tenant's own CI: `golden`, `hallucination` and `fairness` each report `not_gradable — no <suite> dataset`. That is the profile working: `with_profile_ports` removes the option to warn. The tenant has no eval data, and datasets alone would only move it to `no_verdict`, because the profile allows no cloud judge and this CI has no in-border model.

A job that is permanently red hides the next real failure.

The same run failed `SEC-MOD-001`, for a different reason: the tenant's moderation hook imported `agentsmith`, which its `requirements.txt` does not declare. It passed locally because that machine has the package. That is a fault in the fixture, so it is fixed and not expected.

## Approach

The owner chose to assert the refusal (2026-11-09).

`.github/scratch-tenants/expect-ungraded.sh` reads every job of the tenant's CI run that did not succeed, takes the suite from that job's failure log, and passes only when the set of ungraded suites is exactly the expected one. A job that failed for any other reason fails the check, by what its log says and not by its name. So does an expected suite that stopped being refused, which would mean the profile had weakened.

A matrix entry opts in with `expect_ungraded`. The other tenants keep the plain rule, and `AgentSmith gates` is held to green on this one too.

The hook declares its own result type, which is all `SEC-MOD-001` and the gateway read from it. A tenant whose code does import `agentsmith` pins `agentsmith-runtime`, as the manual says.

This proves the profile refuses unjudged evals. It does not prove a passing eval run, which needs an in-border judge.

## Pillars

- P1 applies — `.agent-rfc/designs/scratch-profile-expects-ungraded.md` is the plan; the failing log of run 42567256220 is the requirement.
- P2 applies — `.github/scratch-tenants/build.sh` is the shape the new script copies; no new dependency.
- P3 n/a — a CI step reading a finished run; no application code path.
- P4 applies — `scripts/test/test_scratch_tenants.py` drives the script against a fake `gh`; both directions are mutation-checked by hand.
- P7 applies — bash under `set -uo pipefail`, as `.github/workflows/scratch-tenants.yml` writes its steps.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — a job name from the API is printed but never evaluated; `scripts/test/test_scratch_tenants.py` feeds a failure with no reason.
- P12 applies — `GH_TOKEN` stays in the environment as `.github/workflows/scratch-tenants.yml` already sets it; the script neither reads nor prints it.
- P13 applies — `.github/workflows/scratch-tenants.yml` narrows the rule to one named tenant and three named suites; anything else still fails.
- P14 n/a — no fixture or baseline changes.
- P15 applies — `contract/evals/v1/protocol.md` separates a verdict from no answer; a run or log that cannot be read fails the check.
- P16 applies — reverting is one commit; `CHANGELOG.md` names the change.

## Deviations

none

## Dependencies

none

## Levers

- `failure-is-not-a-result` — an unreadable run or a failure with no stated reason is a failure.
- `test-that-cannot-fail` — the new tests are mutation-checked by hand in both directions.
- `implemented-not-invoked` — a test holds the workflow to calling the script for this tenant.
