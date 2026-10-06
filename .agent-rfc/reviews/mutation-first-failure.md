# Review — mutation-first-failure

Design: `.agent-rfc/designs/mutation-first-failure.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 0

Read the change against the levers it names and the four results `run_suite` reports.

- **The verdict cannot move.** `-x` is added only to the mutated run; pytest stops only after a
  test has failed, which is already the condition for "caught". A survivor fails no test and runs
  every one — `test_a_surviving_mutation_still_runs_every_test` asserts the whole log, both runs.
- **The baseline is untouched.** `test_a_baseline_runs_every_test_even_after_a_failure` asserts no
  `-x` on it, and the "baseline already failing" result is unchanged.
- **Restoring the target** happens in `finally` as before; `test_a_caught_mutation_stops_at_its_first_failing_test`
  asserts the file is byte-for-byte back.
- **Line buffering** is set in `main()` only, guarded by `hasattr`, so a test that imports the
  module or calls a function under pytest's capture is unaffected.
- `--timeout=120` still applies per test; a hang is still a reported failure, not a stall.

The three new tests and the 13 existing scope tests: 16 passed.

## Pass 2 — findings: 0

Measured on the suite CI runs, same machine, same tree: `gate_contract` (8 mutations) took
**546 s** before the change and **150 s** after — every mutation caught both times. Reverting the
`-x` by hand fails `test_a_caught_mutation_stops_at_its_first_failing_test`, so the guard can fail.
On the staged tree: the scope tests and every test reading `git ls-files` (91 passed), `ruff check .`,
mypy 1.14.1 (no issues in 48 files), the Repository Structure tree check.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one argument on the existing runner; no second runner.
Group 2 · Quality / safety — [x] checked — three new tests: caught stops early, a survivor runs everything, a failing baseline does not stop; a hand mutation removing `-x` is caught.
Group 3 · Architecture / hygiene — [x] checked — no dependency; line buffering only in `main()`.
Group 4 · Process — [x] checked — design before code; measured before and after; CHANGELOG entry under Unreleased.
Group 5 · Intuitive UI — [x] checked — CI's step log now timestamps each suite and mutation as it happens.
Group 6 · Signal integrity — [x] checked — caught, survived, stale target and baseline failing stay four results; stopping early never turns one into another.
Group 7 · Auth & session integrity — [x] n/a — no credential or session.

Tests added: three in `scripts/test/test_mutation_check_scope.py`.
Mutation-checked: by hand — the mutation run without `-x` is caught.
Fixtures re-pinned: none.
Gates run: scope tests and every `git ls-files` test on the staged tree (91 passed); `ruff check .`; mypy 1.14.1; the tree check; `gate_contract` timed through `run_suite`, before and after; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `every-line-earns-its-place`, `guards-must-be-able-to-fail`, `failure-mode-visibility`, `run-the-gates-ci-lists`.

KG query: kg:f45635f21dcd
