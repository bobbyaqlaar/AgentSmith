# Review — the TypeScript-runner sweep runs once, and states its premise once

Design: `.agent-rfc/designs/ts-sweep-runs-once.md`. Raised by the owner asking
for the redundancy audit that
`.agent-rfc/reviews/tree-drift-test-reads-once.md` applied to the sibling file
to be applied here too — the file I extended by 250 lines in `aa44e03` under the
Group 1 line *"one `where` builder, one predicate per rule"*, which was a claim
about the `where` string phrased as a claim about the file.

**Built evidence (2026-10-28):**

- **What the audit found.** `_invocations()` had 3 call sites,
  `_alias_prefixes()` had 2, and the two-line alias premise
  (`aliases = tuple(_alias_prefixes())` plus its assertion) was duplicated
  character-for-character at lines 289–290 and 339–340. Measured cost of the
  sweep: **910 candidate paths from git, 297 of them read, 53–103 ms warm per
  call** — so two of every three sweeps were repeated work.
- **Call counts, by AST rather than by grep:** `_invocations` 3 → 1,
  `_alias_prefixes` 2 → 1.
- **Wall time, A/B on the same cache state**, the pre-change file copied in
  beside the new one and the two run alternately four times:

  | run | before | after |
  |---|---|---|
  | 1 | 0.31s | 0.14s |
  | 2 | 0.25s | 0.13s |
  | 3 | 0.29s | 0.15s |
  | 4 | 0.25s | 0.14s |

  Roughly 2×. Worth saying why that is measured alternately: a single
  before-and-after pair would have compared a cold run against a warm one — the
  file had already been seen at `0.24s` and `10.91s` in the same session.
- **Lines of code: 213 → 216, +3.** Total 449 → 472, so +15 of the +23 is
  docstring. Smaller growth than the sibling slice because no new test was
  needed: the premise is asserted in the fixture, where the tests that share it
  already go.
- **All eleven mutants from `aa44e03` re-run, each still caught**, and against
  the same tests as before in ten of eleven cases.
- `ruff check` clean, 8 tests pass.

## Pass 1 — findings: 1

- `out-of-order-and-repeated` — the `invocations` fixture is module-scoped, so
  all three tests receive **one object**. `_invocations()` returns a list, and a
  `.sort()` or `.append()` in any one test would silently change what the other
  two examine, with the failure appearing in a test that did nothing wrong.
  Nothing mutates it today. Returns `tuple(...)` now, typed
  `tuple[tuple[str, str], ...]`, so nothing can.
  - Verified the fixture is itself under test: truncating it to
    `tuple(_invocations()[:5])` fails
    `test_the_sweep_finds_the_known_invocations`, so a fixture that hands the
    tests less than the whole sweep does not pass quietly. That was the P13
    worry about this change.
  - **Noted, not fixed here:** `scripts/test/test_design_tree_drift.py`'s
    `tracked` and `entries` fixtures have the same shape and are still lists.
    They are outside this design's scope and shipped in `8ec5b19`; recorded here
    so the two files are not quietly inconsistent for an unstated reason.

## Pass 2 — findings: 0

- `no-copy-paste` — repeated-line scan now returns only the two
  `_sys.path.insert` pairs, declined in the design with the reason, and
  `@pytest.fixture(scope="module")` twice, which is a decorator.
- `test-that-cannot-fail` — considered and **declined**: making
  `test_the_sweep_finds_the_known_invocations:222` read `portal/package.json`
  through the fixture instead of directly. It counts `RUNNER` occurrences in the
  raw script text precisely so the per-link count is derived independently of
  the sweep it is checking. Routing it through the fixture would make the
  control circular — the one duplication in this file that earns its place.
- `ambiguous-signals` — the premise assertion moving into the fixture changes a
  failure's **shape**: a tsconfig with no aliases is now an `ERROR at setup of
  test_what_counts_as_needing_resolution` rather than two separate failures.
  Checked that this is still red — `pytest` exits **1** and prints the same
  message — and it is arguably the better signal, because both dependent tests
  stop with one named cause instead of each failing on its own. Recorded because
  anyone reading CI output will see a different shape than before.
- `one-verdict` — the sweep is computed once and passed; no test re-derives it.
- `every-line-earns-its-place` — considered and declined: splitting
  `test_the_exempt_invocations_import_nothing_needing_resolution` (36 code
  lines, the largest here). It is one premise checked end to end, and four
  smaller tests would each re-resolve the same entry point to assert a quarter
  of one statement.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — this slice IS Group 1: 3 sweeps to 1,
                                          2 premise copies to 1, measured before and after
Group 2 · Quality / safety            [x] checked — shared fixture made immutable
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — 11 mutants re-run plus 1 on the fixture
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; reads
                                          portal/package.json, portal/tsconfig.json and
                                          tracked sources, executes nothing

Tests added/updated:      scripts/test/test_ts_runner_invocations.py — still 8 tests; two
                          module-scoped fixtures replace 3 sweeps and 2 copies of the
                          alias premise. No test added: the premise now lives in the
                          fixture the sharing tests already depend on.
Mutation-checked:         by hand, 12 mutants, all caught — the 11 from aa44e03 re-run to
                          prove no verdict moved, plus the fixture truncated to 5
                          invocations. mutation_check.py mutates shipped code; this slice
                          touches only a test.
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json — node ids diffed, not
                          only `gate kg check`, which reported green over a fixture
                          missing a Guardrail node on 2026-10-26
KG query:                 kg:5285ab4bb58f
Gates run locally:        pytest scripts/test/test_ts_runner_invocations.py, ruff,
                          py_compile, process gate (design + review), artifacts,
                          gate kg check
Declared gaps:            none — the sibling file's list-valued fixtures are recorded in
                          Pass 1 as out of scope, not as a gap in this change
```
