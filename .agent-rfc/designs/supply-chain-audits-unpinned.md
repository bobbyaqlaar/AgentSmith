---
status: active
scope:
  - workflow-templates/agentsmith-supply-chain.yml
  - scripts/test/test_compliance_checks.py
---
# The supply-chain template scans an app with no lock file

## Problem

`workflow-templates/agentsmith-supply-chain.yml` tries `requirements.lock`, then `requirements.txt`, and gives either to `pip-audit --disable-pip --no-deps`. That mode needs every requirement pinned, so a `requirements.txt` with ranges stops with `requirement fastapi is not pinned to an exact version`. Seen on the `python-dubai-gov` scratch tenant's first GitHub run. A tenant on the profile with no lock file gets a red job and no scan.

## Approach

The owner chose to scan rather than to require a lock (2026-11-09).

A lock keeps the exact-pin mode. A `requirements.txt` is handed to `pip-audit` without those flags, so it resolves the ranges and audits what it gets, including transitive packages. No requirements file stays a message and not a failure. A finding still fails the job.

## Pillars

- P1 applies — `.agent-rfc/designs/supply-chain-audits-unpinned.md` is the plan; the failing log of run 42568690998 on the scratch tenant is the requirement.
- P2 applies — `workflow-templates/agentsmith-supply-chain.yml` changes one step; `pip-audit==2.9.0` stays pinned and no package is added.
- P3 n/a — a CI step; no application code path.
- P4 applies — `scripts/test/test_compliance_checks.py` runs the step against a fake `pipx` in each case; mutation-checked by hand.
- P7 applies — the step runs under the `bash -e` a workflow's `run` uses, as `workflow-templates/agentsmith-supply-chain.yml` already does.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 n/a — no untrusted content is evaluated; the file names are fixed.
- P12 n/a — no secrets involved.
- P13 applies — `scripts/compliance_checks.py` still requires the workflow; a finding still fails the job.
- P14 n/a — no fixture or baseline changes.
- P15 applies — `scripts/test/test_compliance_checks.py` holds that a scanner failure fails the step, so an audit that did not run is not a pass.
- P16 applies — reverting is one commit; `CHANGELOG.md` names the change, and a tenant takes it with `agentsmith sync`.

## Deviations

none

## Dependencies

none

## Levers

- `failure-is-not-a-result` — a scanner that fails is a failed step.
- `test-that-cannot-fail` — the tests are mutation-checked by hand.
- `implemented-not-invoked` — the tests run the shipped step, not a copy of it.
