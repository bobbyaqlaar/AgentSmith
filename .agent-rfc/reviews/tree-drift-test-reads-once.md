# Review — the drift test reads the repository once, and states its filter once

Design: `.agent-rfc/designs/tree-drift-test-reads-once.md`. Raised by the owner
asking whether the review passes had covered redundancy and minimal lines of
code. They had not — the Group 1 line in
`.agent-rfc/reviews/design-tree-drift-is-a-pytest-test.md` answered whether the
PORTED logic was duplicated against the YAML it came from, not whether the new
file duplicated itself.

**Built evidence (2026-10-26):**

- **The measurement that found it.** Prose-to-code ratio against four siblings
  put the file inside the house range, so commenting was not the problem:

  | file | total | code | docstring | comment | prose/code |
  |---|---|---|---|---|---|
  | `test_design_tree_drift.py` | 286 | 161 | 64 | 13 | 0.48 |
  | `test_ts_runner_invocations.py` | 449 | 213 | 113 | 55 | 0.79 |
  | `test_design_and_validation_docs.py` | 338 | 191 | 72 | 23 | 0.50 |
  | `test_gate_steps.py` | 424 | 266 | 44 | 14 | 0.22 |
  | `test_knowledge_graph.py` | 404 | 237 | 64 | 8 | 0.30 |

  What it did find: `_design_entries()` with 7 call sites, `_tracked_paths()`
  with 4, and the second-level filter written twice in two shapes.
- **Reads and spawns per run: 7 → 1 and 4 → 1.** Two module-scoped fixtures.
  Runtime is unchanged at 0.06s — this is about the call sites, not speed.
- **Verdicts did not move.** All five `docs/DESIGN.md` mutants from the previous
  slice re-run, each still failing exactly one named test: second-level deleted,
  top-level deleted, top-level ghost, second-level ghost, wildcard matching
  nothing. `11 passed` restored after each.
- **Lines of code went UP, by 10** (161 → 171), and the honest breakdown is:

  | added | code lines |
  |---|---|
  | `_tracked_second` (replacing two inline copies) | 6 |
  | `tracked` fixture | 2 |
  | `entries` fixture | 2 |
  | `test_tracked_second_keeps_the_directory_and_drops_the_noise` | 12 |

  So the dedupe itself is roughly line-neutral once the two inline copies and
  eleven call-site expressions come out; the net growth is the 12-line test on
  the extracted helper. That is the trade being made deliberately: the rule the
  two copies disagreed about is now asserted directly instead of inferred from
  whatever the repository happens to contain. Fewer lines was not the goal —
  one statement of each rule was.
- `ruff check` clean, 11 tests pass (10 before).

## Pass 1 — findings: 1

- `aggregates-name-their-scope` — `_tracked_second` is called inside the
  wildcard sweep's `for directory` loop once per directory, which is right, but
  the missing-side sweep calls it inside a comprehension that is re-evaluated
  per `sorted(...)` — read again and confirmed it is evaluated once per
  directory there too, not per name. No change; recorded because the first read
  of it was wrong and the next reader's will be too.

## Pass 2 — findings: 0

- `no-copy-paste` — `git grep 'path.count("/") >= 1'` returns one hit, inside
  `_tracked_second`. The rule is stated once.
- `search-before-writing` — the fixture shape matches
  `scripts/test/test_gate_steps.py`'s `@pytest.fixture()`; nothing new invented.
- `every-line-earns-its-place` — considered and declined: collapsing the three
  `for directory in DEEP_DIRS` loops into one parameterised loop, and the five
  per-direction tests into one. Both are shorter and worse — the per-direction
  split IS the previous slice's deliverable, and a mode flag would move the cost
  into the reader, which the lever names explicitly.
- `test-that-cannot-fail` — the fixtures are module-scoped and read-only, and
  `test_the_tree_parse_found_the_repository` still fails if either returns
  something empty (floor of 20 top-level entries, every `DEEP_DIR` non-empty).
  Verified by the heading-rename mutant in the previous slice's record.
- `one-verdict` — the helper returns the set; neither caller re-derives it.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — this slice IS Group 1; one filter,
                                          one read, one spawn, measured before and after
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — five mutants re-run, verdicts unmoved
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; reads
                                          docs/DESIGN.md and `git ls-files`, executes nothing

Tests added/updated:      scripts/test/test_design_tree_drift.py — 10 tests to 11;
                          test_tracked_second_keeps_the_directory_and_drops_the_noise
                          asserts the IGNORE_SECOND subtraction the second copy dropped
Mutation-checked:         the previous slice's five docs/DESIGN.md mutants re-run, each
                          still failing exactly one named test; mutation_check.py mutates
                          shipped code and this slice touches only a test
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json — node ids diffed, not
                          only `gate kg check`, which reported green over a fixture
                          missing a Guardrail node earlier today
KG query:                 kg:a9a7f80728a1
Gates run locally:        pytest scripts/test/test_design_tree_drift.py, ruff, py_compile,
                          agentsmith gates run --only "docs/DESIGN.md repo-tree drift check",
                          process gate (design + review), artifacts, gate kg check
Declared gaps:            none
```
