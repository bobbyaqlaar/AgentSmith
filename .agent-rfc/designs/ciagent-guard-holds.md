---
status: active
scope:
  - scripts/security/runners/agent_workflow.py
  - scripts/test/test_agent_workflow_injection.py
  - contract/security/v1/cases.json
  - scripts/test/test_security_contract.py
---
# SEC-CIAGENT-001 accepts only a guard that restricts, and reads more of what an outsider writes

From the 4.1.0 release review, R9 and R10. Follows `.agent-rfc/designs/agent-workflow-injection.md` (done).

## Problem

R9: `_guarded` accepted an author guard when the condition named the field's `author_association`, a trusted role and no `!=`. `a == 'OWNER' || github.event_name == 'issues'` runs for everyone, and `!contains(fromJSON('["OWNER","MEMBER"]'), …author_association)` runs only for outsiders; both were accepted and the Security job was green.

R10: inside the floor the module's docstring describes, four sources passed: `toJSON(github)` (the whole context, the event inside it), `workflow_run.display_title`, `release.name|body`, label names; and a job- or workflow-level `env:` holding event text, given to an action step, which receives every level of the environment.

## Approach

- A condition restricts only when it contains no `||` and no `!` other than in `!=`. This is stricter than needed (a negated unrelated test joined by `&&` is refused too); a workflow that hits it can split the condition across `if:` on the job and the step. The check stays a floor.
- The untrusted-field pattern gains `toJSON(github)` with or without `.event`, `workflow_run.display_title`, `release.name`, `release.body`, `label.name` and `labels.*.name` on issues, pull requests and discussions.
- For a `uses:` step, every tainted variable in its step, job or workflow environment counts, named or not. A `run:` step still counts only the variables it reads.
- Two contract cases (an `||` guard, a negated guard) join `contract/security/v1/cases.json`, so any security provider is held to them.

## Pillars

- P1 applies — the review's R9 and R10 are the requirement; `.agent-rfc/designs/ciagent-guard-holds.md` is the plan.
- P2 applies — `scripts/security/runners/agent_workflow.py` changes in place; no new dependency.
- P3 n/a — the security runner emits no spans of its own; the harness's are unchanged.
- P4 applies — `scripts/test/test_agent_workflow_injection.py` gains a case for each guard shape and field; mutation-checked by hand.
- P7 n/a — no model changes.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model routing.
- P11 applies — `scripts/security/runners/agent_workflow.py` is this pillar's check for CI: event text an outsider writes must not reach an agent.
- P12 n/a — no secrets.
- P13 applies — `contract/security/v1/cases.json` holds every provider to the two guard cases; `scripts/test/test_security_contract.py` counts them.
- P14 applies — `scripts/test/test_security_contract.py` pins the case count, raised from 34 to 36.
- P15 applies — `scripts/test/test_agent_workflow_injection.py` holds that a condition that may not restrict is read as no restriction.
- P16 applies — `CHANGELOG.md` says what newly fails and how to restructure the guard.

## Deviations

none

## Dependencies

none

## Levers

- `guards-must-be-able-to-fail` — a guard is accepted only when it can only narrow (R9).
- `grep-for-siblings` — the other fields an outsider writes, and the other levels of environment (R10).
- `test-the-contract` — the cases go in the provider contract, not only the runner's tests.
- `test-that-cannot-fail` — hand mutants.
