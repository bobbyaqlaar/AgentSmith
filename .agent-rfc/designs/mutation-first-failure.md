---
status: done
scope:
  - scripts/mutation_check.py
  - scripts/test/**
---
# A mutation is caught by its first failing test — stop there

## Problem

Self-Test's "Python scripts/runtime/examples" job takes about 48 minutes, and 46 of them are one
step, `scripts/mutation_check.py` (measured on the C5 run, 2026-10-04: job 48m, the curated
mutation step 46m20s, mutmut 1m15s). Every pull request that touches what the slow suites watch
waits for it, and so does every local run of a suite.

`run_suite` breaks one line, then runs **every** test file in the suite, to the end, and calls the
mutation caught if any test failed. One failing test is enough to say so; the rest of the run is
paid for and thrown away — on every caught mutation, which is nearly all of them. The suites that
dominate (`tenant_adopt`, 25 mutations over six files of end-to-end tests that build real
repositories) pay it 25 times.

The step's log also cannot say which suite took the time: `print` is buffered under CI, so whole
groups of suites land at one timestamp (19:58:36, then 20:30:05, on that run).

## Approach

- **A mutation run stops at its first failing test** — `pytest -x`. A caught mutation ends as soon
  as one test fails; a mutation that **survives** still runs every test, so a survivor is found and
  reported exactly as before. The verdict cannot change, only the time to reach it.
- **The baseline run stays whole.** It must show every test in the suite passes before anything is
  mutated; stopping it early would hide a second failing test behind the first.
- **Output is flushed per line**, so CI's step log carries a timestamp per suite and per mutation,
  and the next "why is this slow" is read from the log rather than reconstructed.
- **Measured before and after** on the same suite, the same machine, and recorded in the review.

**Deliberately not done here:** naming, per mutation, the test that catches it so it runs first —
worth doing if `-x` is not enough, and a larger change (about 130 mutations to annotate);
parallel suites, which would need a working copy each because a mutation edits the tree.

## Pillars

- P1 applies — `.agent-rfc/designs/mutation-first-failure.md` records the measurement and the change before the code moves.
- P2 applies — `scripts/mutation_check.py` changes one argument list and its prints; no dependency is added and no suite is touched.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_mutation_check_scope.py` gains tests that a mutation run stops at the first failure, that a baseline run does not, and that a survivor still runs every test; the suite's own catch results are compared before and after.
- P7 n/a — no model, handler or type surface changes.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — reads only this repository's own files.
- P12 n/a — no credentials.
- P13 applies — `scripts/mutation_check.py` is a gate whose verdict must not weaken: `-x` stops only after a test has already failed, which is the condition for "caught"; a survivor's run is unchanged, and the baseline keeps running every test.
- P14 n/a — no fixture or baseline file changes.
- P15 applies — `scripts/mutation_check.py` keeps "caught", "survived", "stale target" and "baseline already failing" as four results; stopping early never turns one into another.
- P16 n/a — no fallback path changes.

## Deviations

none

## Dependencies

none

## Levers

- `every-line-earns-its-place` — test runs whose result is already decided are not run.
- `guards-must-be-able-to-fail` — a survivor still runs every test, and a test proves it.
- `failure-mode-visibility` — per-line flushing makes the slow suite visible in CI's own log.
- `run-the-gates-ci-lists` — the change is measured on the step CI actually runs.
