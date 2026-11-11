# Review: compliance-profile-holds

## Pass 1 — findings: 3

Against `docs/review-levers.md`, after the fixes.

1. **The launcher's new inline Python was one line in single quotes,** which the launcher's own test refuses (a quote inside would close the shell's quoting). Rewritten as a block ending on its own line; `bash -n` and the test pass.
2. **A vector write refused mid-batch returned its connection to the pool with the earlier rows of the batch uncommitted but not rolled back.** Now rolled back before raising.
3. **The two MCP mutants first "died" because the mutation script was given both test files as one quoted path,** so pytest failed on a missing file, not on the mutant. Rerun with the right path: both killed. The other mutants were run with separate paths.

## Pass 2 — findings: 0

- `agentsmith/test/test_compliance_runtime.py` (65 run, 7 skipped without `COMPLIANCE_TEST_DSN`), `scripts/test/test_compliance_checks.py` and `scripts/test/test_compliance_port.py`: every new test fails on `origin/main`. The existing gate tests now deliver their decision while the gate waits, as a reviewer would, instead of before it asks.
- The scripts suites matching compliance, security, conformance, contract, the runner setting, the shell gate and MCP: 626 passed. All of `agentsmith/test`: 885 passed, 17 skipped.
- 24 hand mutants across `compliance.py`, `base_workflow.py`, `vector_store.py`, `cli.py`, `compliance_checks.py`, `compliance_port.py`, `mcp_pin.py` and `gate_shell.py`, all killed.
- Decided, not fixed: with no language suite of the app's own the Arabic check is `not_applicable`, not `fail`. The evals job already refuses those suites; a `fail` here would add no fact and would turn the `dubai-gov` scratch tenant red for a reason its expectation script does not recognise. The design says so.
- Not run: the purge, stop and vector statements against Postgres (they are read and exercised against a recording fake); the new template steps for npm and Go on a runner (YAML parses; the Python step and the final "Something was scanned" step are run by the tests); Temporal itself (the gate runs against the module's stand-in, as before).

## Sign-off

Group 1 · DRY & shared code — [x] checked — one `_append` for every record; one `FRAMEWORK_KINDS`; one terminal confirmation for resume and purge.
Group 2 · Quality / safety — [x] checked — a change without its record does not happen; a decision answers only its own request.
Group 3 · Architecture / hygiene — [x] checked — workflow code computes its digest without importing the database module; a test holds the two equal.
Group 4 · Process — [x] checked — design first; manual, security map and CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen here (the portal's are in `portal-compliance-holds`).
Group 6 · Signal integrity — [x] checked — each check reads what the evidence does; "cannot judge" is not "pass".
Group 7 · Auth & session integrity — [x] checked — the vector write is tenant-scoped; `requested_by` is an email.

Tests added: 13 in `agentsmith/test/test_compliance_runtime.py` (plus 3 purge cases), 17 in `scripts/test/test_compliance_checks.py`, 5 in `scripts/test/test_compliance_port.py`.
Mutation-checked: yes, by hand; 24 mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; `bash -n` on the launcher; the knowledge-graph check; the process gate against the commit.

Levers reviewed: `gate-integrity`, `early-exit-keeps-the-record`, `grep-for-siblings`, `declared-vs-enforced`, `test-that-cannot-fail`, `guards-must-be-able-to-fail`, `one-catalog`, `docs-match-behaviour`, `consistent-auth-gates`, `aggregates-name-their-scope`, `validate-on-the-receiving-side`, `irreversible-needs-confirmation`.

KG query: kg:b486d2020bd9
