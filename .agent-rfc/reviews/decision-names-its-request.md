# Review: decision-names-its-request

Each fix has a test that fails without it: `test_a_decision_must_name_the_request_it_answers` and
`test_on_the_temporal_path_a_decision_about_another_request_does_not_answer` (the field did not exist, and a decision
on another request with the same digest was accepted), `test_on_the_store_path_a_late_decision_on_an_earlier_request_does_not_answer`
(database; the review's scenario: two requests, one input, a decision on the first), and
`test_a_resume_that_fails_leaves_no_resume_record` (the `resume` record committed before the delete failed). The
portal's message is a pure function, `decisionMessage`, held by `portal/test/hitl.test.ts`.

## Pass 1 — findings: 2

Against `docs/review-levers.md`, by hand mutants (seven), with `COMPLIANCE_TEST_DSN` set against Postgres 16 so the
database tests counted.

1. **The store path's digest comparison was no longer tested.** The old test that a request asked with other input is
   not answered now passes on the record id alone (the new request has a new id), so dropping the digest comparison
   survived. The store-path test now records a decision naming the right request with the wrong digest.
2. **A pending record without its id was not tested.** The workflow refuses a gate whose pending record comes back
   without an id or a digest; only the digest half had a test. Parametrised over both.

## Pass 2 — findings: 0

- The seven mutants again (store: any decision; store: digest ignored; Temporal: request id ignored; Temporal: missing
  id accepted; the field optional; resume recorded first; the portal omitting the id): all killed.
- `agentsmith/test` with the database plus `scripts/test/test_compliance_port.py` and
  `scripts/test/test_compliance_checks.py`: 992 passed, 10 skipped. Portal `npm test`: exit 0; `tsc`: clean. ruff and
  mypy 1.14.1: clean.
- Siblings: `replay_webhook_server` validates every decision with `HumanDecision` before recording or signalling it,
  so a decision without the field is refused there (400) on both backends. `set_stop`, `clear_stop` and `purge_runs` now
  all go through `_recorded_change`.
- Compatibility: `HumanDecision` forbids extra fields, so a newer portal adding a field breaks an older runtime. That is
  not a risk here, because the profile is new in 4.1.0 and the portal and the runtime ship together; it is a risk for
  the next field, and the protocol now says what a decision carries.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one `_recorded_change` for every change with a record; one `decisionMessage` for the portal.
Group 2 · Quality / safety — [x] checked — a decision answers only the request it names; a gate without the request's id fails closed.
Group 3 · Architecture / hygiene — [x] checked — one field on the wire, required; the manual and both protocols say so.
Group 4 · Process — [x] checked — design first; CHANGELOG, backlog, manual and compliance protocol updated.
Group 5 · Intuitive UI — [x] n/a — the reviewer's screen does not change.
Group 6 · Signal integrity — [x] checked — a `resume` record means the app was resumed.
Group 7 · Auth & session integrity — [x] checked — a reviewer's decision cannot be replayed onto a later request.

Tests added: six in `agentsmith/test/test_compliance_runtime.py` (one needs a database); one in `portal/test/hitl.test.ts`.
Mutation-checked: yes, by hand; seven mutants, all killed after pass 1.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above with `COMPLIANCE_TEST_DSN`; `npm test`; `tsc`; ruff; mypy; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `out-of-order-and-repeated`, `grep-for-siblings`, `merge-the-right-copy`, `two-owners-two-cadences`, `test-that-cannot-fail`

KG query: kg:15fddd8ef058
