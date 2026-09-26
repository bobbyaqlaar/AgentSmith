---
status: done
scope:
  - scripts/test/**
  - scripts/gate_models.py
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Siblings of the three defects the last slice fixed

Owner, 2026-09-26: "The findings indicate more full passes until no more findings come up. Go for up
to 3 passes if no findings come up in the meantime."

## Problem

Every defect in the last slice had siblings, and I fixed one instance at a time: a glob reaching for
a directory in the wrong language (`portal/*.py`), then the same for shell, then extensionless shell.
So this pass hunts the three classes rather than more documentation:

1. **A sweep that does not reach what it claims.** 34 `ls-files` globs across the test suite;
   `examples/**/test*.py` in `scripts/test/test_no_tenant_repo_dependency.py` matches **nothing** —
   there are no test files under `examples/` — and its own guard,
   `assert len(sources) >= 40`, is satisfied by the other two globs, so the dead one is invisible.
   The same shape as `portal/*.py`: an aggregate floor hides a member that contributes zero.

2. **An anchored pattern whose non-match is reported as a different problem.** `_PASS` did this and
   is fixed. Its sibling is `_ANSWER` in `scripts/gate_models.py`: `pillar_kinds` drops a line the
   pattern does not match, and `check_pillars` then reports the pillar as unanswered. `- P3: applies
   — ...` (a colon where a space belongs) yields *"'## Pillars' does not answer P3"* and never quotes
   the line, so the author is told they omitted something that is on the page. Milder than `_PASS`,
   which pointed at other passes' numbers, but the same fault.

   Checked and **not** a sibling: `_KG_QUERY` is anchored the same way, and a line it cannot parse is
   reported as "records no 'KG query:' line" — which is what happened, and the message says what to
   write.

3. **A list paired by position rather than by key.** Swept: one `zip` in shipped code
   (`scripts/mutation_check.py`, `strict=True` over two fixed 2-tuples) and one parse-then-pair in a
   test (`scripts/test/test_framework_python_env.py:82`, which **asserts** the two lengths match
   before pairing — the pattern mine should have used). No siblings.

## Approach

- **Kill the class, not the instance.** One test asserts that every `ls-files` glob any test passes
  resolves to at least one tracked file. Three occurrences of this defect in two days is the argument
  for a guard over another fix. The dead `examples/**/test*.py` glob goes with it.
- **A malformed pillar answer is quoted.** `check_pillars` reports a line in `## Pillars` that begins
  `- P<digits>` and that `_ANSWER` did not parse, instead of letting the pillar read as unanswered.
  The pattern is unchanged; only the diagnosis is added, as with `_PASS_LOOSE`.

## Pillars

- P1 applies — this design precedes the code and its passes are recorded in `.agent-rfc/reviews/sibling-sweep.md`.
- P2 applies — no dependency; the glob guard uses `git ls-files` and `re`, which the tests already use.
- P3 n/a — no execution path added.
- P4 applies — `test_every_ls_files_glob_in_a_test_matches_something` and `test_a_malformed_pillar_answer_is_quoted_not_read_as_missing`, each run against a reverted fix.
- P7 applies — no new typed boundary; `check_pillars` in `scripts/gate_models.py` keeps its `list[str]` return.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the glob guard reads this repository's own test sources as data, never executing what it extracts (`scripts/test/test_no_tenant_repo_dependency.py`).
- P12 applies — no credential is read or written; neither change touches `scripts/gate_models.py`'s approval handling.
- P13 applies — nothing is weakened. `_ANSWER` keeps its shape and the glob guard only adds a failure mode; a malformed answer still does not count as an answer.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned, since `scripts/gate_models.py` changes.
- P15 applies — the subject of both fixes: `test_every_ls_files_glob_in_a_test_matches_something` turns a glob that matches nothing into a failure instead of an aggregate that passes, and `_MEANT_AS_ANSWER` in `scripts/gate_models.py` stops a line that did not parse from being reported as a pillar that is missing.
- P16 n/a — no fallback path added.

## Deviations

none

## Dependencies

None added.

## Levers

- `grep-for-siblings` — the whole pass: three classes, swept rather than waited for.
- `check-that-fires-on-everything` — a glob matching nothing is a broken query, and an aggregate floor hides it.
- `ambiguous-signals` — a line that did not parse must not be reported as a line that is absent.
- `test-that-cannot-fail` — the guard exists because the existing `>= 40` assertion could not see a zero-contribution member.
