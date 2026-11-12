---
status: active
scope:
  - .github/workflows/self-test.yml
  - agentsmith/test/test_compliance_runtime.py
  - scripts/test/test_compliance_port.py
  - scripts/security/runners/agent_workflow.py
  - scripts/test/test_agent_workflow_injection.py
  - contract/security/v1/cases.json
  - scripts/test/test_security_contract.py
---
# The compliance database tests run in CI, and a whole event object is untrusted text

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R23 and P2-R6 (P2-R5's sibling),
two minors the owner asked for before the release. Follows `.agent-rfc/designs/review-pass2-majors.md`.

## Problem

- **P2-R23.** `agentsmith/test/test_compliance_runtime.py` skips its database tests unless `COMPLIANCE_TEST_DSN` is
  set, and no workflow sets it. They prove the record chain, stop and resume, a resume that cannot be recorded, the
  sidecar's gate round trip and the store path's decision matching, and they are the evidence `OB-RECORD` and
  `OB-STOP` cite. In CI they never ran: green whether they pass or not.
- **P2-R6.** SEC-CIAGENT-001 reads named fields (`…issue.title`, `…comment.body`). An agent's prompt given
  `${{ github.event.pull_request }}`, or `${{ format('{0}', github.event.issue) }}`, receives the whole object as JSON,
  title and body included, and passes.

## Approach

- **P2-R23.** The Self-Test job that runs `pytest agentsmith/test/` already starts Postgres for the idempotency tests;
  it gains `COMPLIANCE_TEST_DSN` pointing at that database, and `AGENTSMITH_REQUIRE_DB=1`. With that variable set, a
  missing DSN fails a test instead of skipping eight, so the job cannot quietly lose its database again. Only this job
  sets it: other jobs that may import the file (mutation shards) keep skipping. A test holds the workflow to both
  variables and the service.
- **P2-R6.** The untrusted pattern gains each event object an outsider writes into, named with nothing after it:
  `github.event` itself, and `issue`, `pull_request`, `discussion`, `comment`, `review`, `review_comment`, `release`,
  `workflow_run`, `head_commit`, `commits`, `pages` and `pull_request.head` under it. A field of one (`…issue.number`)
  is unchanged. An object cannot be excused by an author guard: it carries more than its author wrote (labels, branch
  names). One contract case.

## Pillars

- P1 applies — P2-R23 and P2-R6 are the requirement; `.agent-rfc/designs/db-tests-in-ci-and-event-objects.md` is the plan.
- P2 applies — `.github/workflows/self-test.yml` gains two variables; `scripts/security/runners/agent_workflow.py` one pattern; no dependency.
- P3 n/a — no spans or evaluations.
- P4 applies — `agentsmith/test/test_compliance_runtime.py`, `scripts/test/test_compliance_port.py` and `scripts/test/test_agent_workflow_injection.py`; hand mutants after.
- P7 n/a — no model.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 applies — `scripts/security/runners/agent_workflow.py`: event text an outsider writes, however it is addressed.
- P12 n/a — no secrets (the CI database's password is the service's throwaway one, already in the workflow).
- P13 applies — `.github/workflows/self-test.yml`: the tests behind two release obligations run, and cannot silently stop running.
- P14 applies — `scripts/test/test_security_contract.py` pins the case count (39 to 40).
- P15 applies — `agentsmith/test/test_compliance_runtime.py`: "skipped" in the job that must run them is a failure, not a pass.
- P16 applies — `CHANGELOG.md` says what SEC-CIAGENT-001 newly reports and how to pass (give the number, fetch the text as data).

## Deviations

none

## Dependencies

none

## Levers

- `run-the-gates-ci-lists` — the tests CI is meant to run, run (P2-R23).
- `test-that-cannot-fail` — a skip where a run is required now fails.
- `grep-for-siblings` — the object holds the fields the check already names (P2-R6).
- `test-the-contract` — the case goes in the security contract.
