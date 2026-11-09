# Review: trajectory-evals

Gap 9 of `docs/PRODUCT_BACKLOG.md`, after the owner's instruction of 2026-11-09 to fix the gaps.

## Pass 1 — findings: 3

Against `docs/review-levers.md`.

1. **Five places named the suites by hand,** in the request, scorecard, declared port and bars models. Replaced by one `EvalSuite` alias, so a seventh suite is one edit.
2. **`contract/rules/v1/extends.schema.json` also lists the suites,** for `extends.evals`. Regenerated, and added to the design's scope.
3. **The first trace reader guessed between one object and one per line from the text's shape.** Replaced by trying one object, then one per line, as the telemetry contract's own reader does.

## Pass 2 — findings: 0

- `scripts/test/test_trajectory_evals.py` covers each rule, repeated tools in `in_order`, both sources, start order over file order, both trace layouts, and four ways a trace cannot be read.
- `contract/evals/v1/cases.json` gains a passing and a failing case, and AgentSmith passes its own contract with them: 19 cases.
- Evals, rules and trajectory suites: 168 passed.
- Eight hand mutants, all caught: order ignored; `never` inverted; `max_calls` off by one; a path escaping the repository; an empty trace graded; start order ignored; an unreadable trace graded anyway; the floor ignored.

Not in this slice, and on the backlog: "approved before", which needs human decisions recorded on spans, and a template CI job for the suite.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one suite alias; the grader beside the suites the port already answers.
Group 2 · Quality / safety — [x] checked — a trace path is confined to the repository and parsed as data.
Group 3 · Architecture / hygiene — [x] checked — additive in every contract file; no existing suite's behaviour moves.
Group 4 · Process — [x] checked — design first; protocol, CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — an unreadable trace is `not_gradable`, never a pass; a broken run is named in the reason.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: `scripts/test/test_trajectory_evals.py`; two cases in `contract/evals/v1/cases.json`.
Mutation-checked: yes, by hand; eight mutants, all killed.
Fixtures re-pinned: the evals request, scorecard, providers and new dataset schemas; `contract/rules/v1/extends.schema.json`; `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; mypy; the process gate against the commit.

Levers reviewed: `failure-is-not-a-result`, `test-that-cannot-fail`, `implemented-not-invoked`.

KG query: kg:9be3811d32fa
