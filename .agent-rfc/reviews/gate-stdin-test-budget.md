# Review — a contract decision's test bounds the wait, not the gate's work

Design: `.agent-rfc/designs/gate-stdin-test-budget.md`. Found on PR #78: 7.05s against a limit of 7s, on a job that had passed on `main`.

**Built evidence:**
- `test_a_contract_decision_answers_when_nobody_closes_stdin` no longer asserts elapsed time, and still asserts the expired wait's message.
- `_gate_with_open_stdin`'s twenty-second `hold` raises if the gate has not answered.

## Pass 1 — findings: 0

- **The guard can still fail:** `hook_payload` 5/5, including "the payload read waits for an EOF the caller may never send", caught through `hold`.
- **`stop` keeps its limit:** it reads no range, so its time measures the read. It has not flaked.
- **`hold` is not the same fragility at a larger size:** it is three times the observed time on a loaded runner, and it only fails if the gate has not answered at all.

## Pass 2 — findings: 2

1. `environment-parity` — **Pass 1's claim that `stop` reads no range was wrong.** Its sweep does: nineteen seconds on the rename's commit. Found by
   running the suite on that branch. **Fix:** see below.
2. `guards-must-be-able-to-fail` — **`hold` had the same fragility as the limit it replaced.** `ci --decision` passed twenty seconds on that branch while
   answering correctly. **Fix:** `_gate_with_open_stdin` runs in a scratch repository, and the elapsed assertion is restored, since it now measures the read.

## Pass 3 — findings: 0

- **The gate was never hanging:** with stdin held open, on the rename's commit, `ci --decision` allows in 11.6s, against 9.4s with stdin closed.
- **Its linear cost is not a defect here:** 967 git calls for one commit of about 400 files, at a commit gate with no time limit of its own.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — one assertion removed.
Group 2 · Quality / safety — [x] checked — `hook_payload` proves the test still fails on the defect.
Group 3 · Architecture / hygiene — [x] n/a — no dependency or structural change.
Group 4 · Process — [x] checked — design before the edit; CHANGELOG Unreleased.
Group 5 · Intuitive UI — [x] n/a — no screen or message changes.
Group 6 · Signal integrity — [x] checked — a slow runner no longer reads as a defect in the read.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: none — one test narrowed to the property it claims.
Mutation-checked: `hook_payload` 5/5.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: ruff, `test_process_gate.py`'s stdin tests, `hook_payload`, check-kg, repo-tree, artifacts and the process gate.

Levers reviewed: `guards-must-be-able-to-fail`, `environment-parity`.

KG query: kg:e10e917addaf
