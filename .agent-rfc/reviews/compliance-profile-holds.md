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

Scope at an earlier sign-off: kg:b486d2020bd9

## Pass 3 — findings: 1

After #115 merged, the Scratch tenants workflow on `main` (run 43079148397) failed for `python-dubai-gov` only.

1. **The R18 drill fix broke the `dubai-gov` scratch tenant.** Its fixture drill (`.github/scratch-tenants/profiles/dubai-gov/agenticframework/drills/scratch.json`) was dated `2099-01-01`: exactly the evidence R18 says should not count, used to keep the scratch tenant green for ever. The production check now ignores it, so `OB-RESTORE-DRILL` failed and `build.sh` stopped. No test on the PR could see it: only the scratch workflow builds that tenant, and it runs on `main`. Fixed: `build.sh` stamps each fixture drill with the build time after copying the profile files; the fixture now says `1970-01-01`, so a build that skipped the stamp fails rather than passes.

## Pass 4 — findings: 0

- `build.sh python-dubai-gov … dubai-gov`, run locally with this checkout's `agentsmith` on PATH: exits 1 with `OB-RESTORE-DRILL no passing restore drill` without the fix (the failure on `main`), and exits 0 with it ("the app passes, and passes no longer with its gate removed").
- `bash -n` on `build.sh`.
- Searched the scratch tenants, fixtures, templates and tests for other dates in the future: none.

## Sign-off (after the scratch-tenant failure)

Group 1 · DRY & shared code — [x] n/a — one build step.
Group 2 · Quality / safety — [x] checked — the scratch tenant no longer relies on evidence the profile refuses.
Group 3 · Architecture / hygiene — [x] checked — the fixture cannot pass on its own date.
Group 4 · Process — [x] checked — found on `main` after merge; reproduced locally before fixing.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — the green scratch run now means a drill dated today passes.
Group 7 · Auth & session integrity — [x] n/a.

Tests added: none; the scratch build itself is the test, run locally both ways.
Mutation-checked: the fix removed (stash) reproduces the failure.
Fixtures re-pinned: `.github/scratch-tenants/profiles/dubai-gov/agenticframework/drills/scratch.json`; `.agent-rfc/fixtures/knowledge_graph.json` if it changed.
Gates run: the scratch build; the knowledge-graph check; the process gate against the commit.

Levers reviewed: `fixture-truth`, `gate-integrity`.

KG query: kg:cbaac984cd17
