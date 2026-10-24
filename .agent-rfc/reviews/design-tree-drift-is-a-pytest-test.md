# Review — the repo-tree drift check belongs in pytest, not in a workflow step

Design: `.agent-rfc/designs/design-tree-drift-is-a-pytest-test.md`. Raised by
`PR #66`, which passed 2423 local tests and still failed CI on
`missing from docs/DESIGN.md tree (second level): ['docs/agentic-42001-coverage.md']`.

**Built evidence (2026-10-24):**

- **Parity with the step it replaces, measured rather than asserted.** The old
  inline script was extracted out of the YAML into a scratch file and run beside
  the new test on five trees — the repository as it stands, and four mutated
  `docs/DESIGN.md`s. They agree on every one: `old:PASS / new:9 passed`,
  then `old:FAIL / new:1 failed` four times.
- **Each direction fires exactly one named test**, which the single exit code
  could not do:

  | mutation to `docs/DESIGN.md` | test that failed |
  |---|---|
  | second-level entry deleted (`docs/review-levers.md`) | `test_every_tracked_second_level_entry_is_in_the_tree` |
  | top-level entry deleted (`portal`) | `test_every_tracked_top_level_entry_is_in_the_tree` |
  | top-level entry for a path that does not exist | `test_no_top_level_tree_entry_is_absent_on_disk` |
  | second-level entry for a file that does not exist | `test_no_second_level_tree_entry_is_absent_on_disk` |
  | wildcard entry matching nothing | `test_every_wildcard_tree_entry_still_matches_something` |

- **Four more mutants, all caught:** the heading renamed so the parse returns
  nothing (6 tests fail, `test_the_tree_parse_found_the_repository` first —
  without it the sweeps would compare the repository against empty sets and
  report nothing); `DEEP_DIRS` losing `docs`
  (`test_second_level_is_collected_per_directory`, so the allowlist cannot
  silently shrink — the P13 concern); the depth calculation flattened to `0`
  (4 tests).
- **The gate still exists and now runs here.** `agentsmith gates list` reports
  the step with its command where it used to read `(script)`, and
  `agentsmith gates run --only "docs/DESIGN.md repo-tree drift check"` →
  `gates: 1 passed, 0 failed, 0 skipped`. The regenerated table is committed and
  `scripts/test/test_gate_steps.py` (26 tests) passes against it.
- **Cwd-independence**, which the original did not have: run from `docs/`, the
  new test passes and the old script raises
  `FileNotFoundError: 'docs/DESIGN.md'`.
- `ruff check` clean, `py_compile` clean, the workflow still parses
  (`yaml.safe_load`, 8 jobs), 87 lines out of `self-test.yml`.

## Pass 1 — findings: 2

- `no-copy-paste` / house style — the port arrived with
  `from typing import Dict, List, Set, Tuple`, where 40 of the 96 files in
  `scripts/test/` use builtin generics and only one other uses typing aliases.
  Rewritten as `list[str]`, `dict[str, set[str]]`, `list[tuple[int, str]]`.
- `use-existing-apis` — the missing-tree-block case was a hand-rolled
  `try/except AssertionError/else: raise`, which accepts **any** AssertionError
  and so would have passed if `_tree_of` failed for an unrelated reason.
  `pytest.raises(AssertionError, match="Repository Structure")` instead; 64 of
  96 files in this directory already import pytest.

## Pass 2 — findings: 2

- `test-that-cannot-fail` — the ghost direction skips every entry containing
  `*`, because a pattern has no single path to check. That leaves the one kind
  of tree line that can describe nothing and never be reported. Added
  `test_every_wildcard_tree_entry_still_matches_something`, matching forward.
  Checked before adding it that all four wildcards in the tree match today
  (`fixtures/*_judge_criteria_base.json` 3, `workflow-templates/cd-*.yml` 2,
  `ci-*.yml` 3, `eval-*.yml` 4), so it closes a hole rather than reporting one.
- `every-line-earns-its-place` — `IGNORE_SECOND` and `IGNORE_TOP` were the only
  constants in the file with no reason attached. One comment, saying what those
  entries have in common.

## Pass 3 — findings: 1

- `docs-match-behaviour` — the workflow comment I wrote said `pytest` is
  "installed two steps above". It is four steps above, in this job's
  `pip install --require-hashes -r requirements.lock`, which runs before `ruff`.
  Corrected to name the step rather than count steps, which is what would rot
  next time a step is inserted.

## Pass 4 — findings: 1

- `docs-match-behaviour` — the module docstring still said "the four drift
  directions" and "same wildcard handling" after pass 2 added a fifth direction
  and changed wildcard handling. Rewritten to state what actually carried over
  unchanged (regex, ` / ` splitting, first-component rule, `DEEP_DIRS`) and what
  did not (per-direction tests, fixture-pinned parser, ROOT-relative paths, the
  wildcard check). The design's Approach and P15 answer updated the same way.

## Pass 5 — findings: 0

- `implemented-not-invoked` — the step's `run:` names the file, and
  `pytest scripts/test/` in the `Python runtime behaviour tests
  (Postgres-backed)` job collects it too, so it gates merges from two required
  checks rather than one.
- `single-source-of-truth` — `DEEP_DIRS`, `IGNORE_SECOND`, `IGNORE_TOP`, the
  tree regex and the parse now exist once, in the test. Nothing was left behind
  in the YAML to drift from them.
- `environment-parity` — same code locally and in CI; no environment variable,
  clock or network. `git ls-files` is the index on both, and
  `_tracked_paths(cwd=ROOT)` makes the answer independent of where pytest ran.
- `aggregates-name-their-scope` — each failure message lists the offending
  paths, and the second-level ones name the five directories the check covers,
  so "nothing missing" cannot be read as "everything checked".
- `ambiguous-signals` — "missing from the tree" and "absent on disk" are
  separate tests with separate fixes; so is a wildcard that matches nothing.
- Considered and declined: `git ls-files --others --exclude-standard`, as
  `test_ts_runner_invocations.py::_candidate_files` uses. It answers a different
  question — that sweep must see a call site before it is committed, while this
  one must return the verdict CI returns — and it would fail the suite on any
  untracked file in the working tree, the PDF in `assets/` included.
- Considered and declined: deleting the workflow step and relying on
  `pytest scripts/test/`. The step's name is a declared gate in
  `docs/validation-checklist.md` and is counted by
  `test_the_frameworks_own_workflow_tags_its_gates`; keeping it named means the
  check is still something `agentsmith gates list` can tell you about.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the logic exists once, in the test
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked — gate kept its name, table regenerated
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — 9 mutants, 8 tree/parse + 1 allowlist
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; reads
                                          docs/DESIGN.md and `git ls-files`, executes nothing

Tests added/updated:      scripts/test/test_design_tree_drift.py — new, 10 tests (4 parser
                          and fixture, 6 against the repository). The check it carries had
                          no test of its own while it lived in YAML.
Mutation-checked:         by hand, 9 mutants, all caught — 5 to docs/DESIGN.md, 2 to the
                          test's own constants and parse, plus the heading rename and the
                          flattened depth. mutation_check.py mutates shipped code, and
                          this slice adds a test and deletes YAML.
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:3749f9809179
Gates run locally:        agentsmith gates run --only "docs/DESIGN.md repo-tree drift check",
                          pytest scripts/test/ (full), ruff, py_compile, process gate
                          (design + review), artifacts, gate kg check
Declared gaps:            none
```
