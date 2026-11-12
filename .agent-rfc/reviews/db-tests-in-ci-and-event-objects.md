# Review: db-tests-in-ci-and-event-objects

Each fix has a test that fails without it: `test_ci_runs_the_compliance_database_tests` in
`scripts/test/test_compliance_port.py` (no workflow set the DSN), `test_the_database_tests_run_where_they_are_required`
in `agentsmith/test/test_compliance_runtime.py` (fails with `AGENTSMITH_REQUIRE_DB=1` and no DSN, passes otherwise),
and twelve object cases plus the author-guard case in `scripts/test/test_agent_workflow_injection.py` (each passed the
old pattern).

## Pass 1 — findings: 1

Against `docs/review-levers.md`, by hand mutants (seven).

1. **The guard on the database tests could not be seen failing.** Turning `test_the_database_tests_run_where_they_are_required`
   into `assert True` survived: nothing ran it in the state it exists for. A test now runs it in a subprocess with the
   requirement set and no DSN, and expects red; and with no requirement, green.

## Pass 2 — findings: 0

- The seven mutants again (objects dropped; the lookahead removed, so a field of an object reads as the object; the
  `pull_request.head` object dropped; the bare `github.event` dropped; the DSN removed from the job; the requirement
  removed; the guard made vacuous): all killed.
- The CI job's environment reproduced locally: one Postgres 16 database shared by the idempotency and compliance tests,
  `DATABASE_URL`, `IDEMPOTENCY_BACKEND=postgres`, `COMPLIANCE_TEST_DSN` and `AGENTSMITH_REQUIRE_DB=1`, then
  `pytest agentsmith/test/`: 914 passed, 2 skipped (a dead-model check with nothing to check, and Bedrock without
  credentials), none of the compliance tests skipped.
- Why only that job requires the database: the curated mutation shards and other GitHub jobs may import the file
  with no database; there the database tests still skip.
- `.github/workflows` and `workflow-templates` scanned with the new pattern: no problem. `scripts/test/test_security_contract.py`:
  the provider passes all 40 cases. ruff clean.
- Siblings: `github.event_name` and `github.event.action` stay trusted (tested); an object cannot be guarded, since
  `_guarded` accepts only a four-part authored field.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the job's existing Postgres serves both test sets; one pattern for objects.
Group 2 · Quality / safety — [x] checked — the check reports more, never less; the job fails when its database is missing.
Group 3 · Architecture / hygiene — [x] checked — two variables in one job; one alternative in one pattern.
Group 4 · Process — [x] checked — design first; CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — a skip where a run is required is a failure.
Group 7 · Auth & session integrity — [x] checked — an object's author guard is not accepted.

Tests added: two in `scripts/test/test_compliance_port.py` (`test_ci_runs_the_compliance_database_tests`, `test_a_required_database_that_is_missing_fails_rather_than_skips`); one in `agentsmith/test/test_compliance_runtime.py`; seventeen cases in `scripts/test/test_agent_workflow_injection.py`; one contract case.
Mutation-checked: yes, by hand; seven mutants, all killed after pass 1.
Fixtures re-pinned: `scripts/test/test_security_contract.py` case count (39 to 40); `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; the CI job's environment reproduced; ruff; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `run-the-gates-ci-lists`, `test-that-cannot-fail`, `grep-for-siblings`, `test-the-contract`

KG query: kg:1a9521cf6d11
