# Review — the slow mutation suite runs when what it protects changes

Design: `.agent-rfc/designs/mutation-ci-scope.md`. Owner decision, 2026-09-19: option 1 — run
the `tenant_adopt` mutations only when their files change.

**Built evidence (2026-09-19):**

- **Failing tests first.** `scripts/test/test_mutation_check_scope.py` (12, then 13) failed on the
  missing `watch`, `select_suites` and `changed_files` before any of them existed.
- **Two defects found while building:**
  - with every suite skipped, `_dirty_catalogue_files` ran `git status --porcelain --` with no
    paths, which reports the whole repository, and refused to run — present before this change,
    unreachable until a run could select no suite;
  - `git diff REF HEAD` sees commits only, so a local run (`agentsmith gates run` resolves `$BASE`
    to the merge base) would skip `tenant_adopt` while its files were being edited — exactly when
    it matters. Uncommitted and untracked files now count;
    `test_uncommitted_and_new_files_count_as_changed`. The CLI test then ran the whole suite here,
    correctly, because the harness itself was uncommitted; it now runs from its own committed copy.
- **Mutation checks, by hand, each restored from a copy:** a watched suite never skipped; unknown
  changes read as "nothing changed"; new files not counted; a run with skipped suites claiming
  "all caught". All four caught.
- `agentsmith gates run` still runs the step locally: `gate_steps.runnable` answers yes, and the
  `$BASE` expression resolves to the merge base.

## Pass 1 — findings: 0

Every lever over the diff, the workflow step and the CHANGELOG. Considered and declined:

- Watching every file the four tests import, transitively. The tests themselves still run on
  every push in the pytest job; what a skip gives up is only the proof that each guard's test can
  fail, and only for a change outside `watch`. `watch` names the files the guards live in and the
  code the tests drive directly; `test_the_tenant_adopt_suite_watches_everything_it_mutates_and_tests`
  keeps it from falling behind the suite's own mutations and tests.
- Adding the four selection mutations to the catalogue. The harness would be rewriting the file it
  is running from; the hand run above is the evidence, recorded here.
- Narrowing any other suite. None is slow enough to be worth a skip.

**Stated limit:** a change that breaks a `tenant_adopt` guard from a file outside `watch` is
caught by the ordinary tests on that push, and by the mutation suite on the next push that touches
a watched file — not on the push itself.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — a CLI flag; its output was read in each case
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_mutation_check_scope.py (13)
Mutation-checked:          yes — four, by hand, each restored; all caught
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:0374295032fb
Gates run locally:         ruff, the new tests, the gates-table drift check, gate_steps.runnable on the step
Declared gaps:             a guard broken from outside `watch` is proven on the next watched push, not this one
```
