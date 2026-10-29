# Review — the local gate's base is the base branch

Design: `.agent-rfc/designs/gate-base-is-the-base-branch.md`. Raised by the
owner: *"fix the gate's per-commit changelog rule"*, after a local refusal that
CI did not reproduce.

**The rule was not the bug.** `scripts/process_gate.py:1498` evaluates the
CHANGELOG requirement over `range_files` — the union of files across the range —
which is correct: release notes are a property of a change, not of each commit
in it. The defect was the **range**, in `scripts/gate_steps.py::_merge_base`.

**Built evidence (2026-10-30):**

- **Measured, on the branch this shipped from:**

  | | base resolved | commits in range |
  |---|---|---|
  | `_merge_base` before | `merge-base(origin/test/ts-sweep-runs-once, HEAD)` — the branch's own pushed tip | **0** |
  | `_merge_base` after | `merge-base(origin/main, HEAD)` = `8ec5b19b75` | **5** |
  | CI (`pull_request.base.sha`) | `8ec5b19b75` | 5 |

  After the fix the local base is byte-identical to CI's: `agree: True`.
- **Both failures reproduced, then fixed.** The gate runner that printed
  `Checked 0 commit(s)` + `gates: 1 passed` now prints
  `Checked 5 commit(s), 4 touching gated paths` + `✅`. The CHANGELOG refusal
  that CI did not share is gone, because the range now contains the commit
  carrying the entry.
- **Four mutants, each caught by the right test:**

  | mutant | tests that failed |
  |---|---|
  | reverted to `@{upstream}` — the defect itself | base-is-the-base-branch, range-is-not-empty, origin-main-fallback |
  | `origin/main` fallback removed | origin-main-fallback |
  | `HEAD~1` fallback removed | falls-back-when-no-base-branch |
  | base collapses to `HEAD` (empty range) | all four |

- `ruff` clean, `mypy==1.14.1` clean (`Success: no issues found in 48 source
  files`), 30 tests in `scripts/test/test_gate_steps.py` (26 before).

## Pass 1 — findings: 2

- `test-that-cannot-fail` — **my first three tests passed against the unfixed
  code.** The `branch_repo` fixture set `branch.feature.remote` and
  `branch.feature.merge` but no `remote.origin.url` or fetch refspec, so
  `@{upstream}` failed with *"not stored as a remote-tracking branch"*, the
  helper fell through to `origin/main`, and the tests were green without
  reproducing anything. The fixture now configures the remote **and asserts**
  `@{upstream} == "origin/feature"` before yielding, so a fixture that stops
  reproducing a pushed branch fails instead of passing quietly. Caught by
  checking why three new tests passed before the fix, not by the suite.
- `test-that-cannot-fail` — the middle link of the fallback chain
  (`origin/main` when `origin/HEAD` is unset) was reached by no test: replacing
  `or "origin/main"` with `or ""` changed no result, because the other cases
  resolve `origin/HEAD` or fall through to `HEAD~1` either way. Added
  `test_the_base_uses_origin_main_when_origin_head_is_unset`, and the mutant
  now fails.

## Pass 2 — findings: 2

- `no-copy-paste` — `subprocess.run(["git", "rev-parse", …])` written out three
  times across the fixture and a test. One `_sha(root, ref="HEAD")` helper
  beside the `_run` the file already had; one occurrence left, inside `_sha`.
- `guards-must-be-able-to-fail` — `Path` was used in two annotations and **never
  imported**. The tests passed anyway, because `from __future__ import
  annotations` makes annotations strings, so only `ruff` saw it (`F821
  Undefined name Path`). Imported. Worth recording that the suite could not
  catch this class at all.

## Pass 3 — findings: 0

- `environment-parity` — the point of the slice: same gate, same tree, one
  verdict, whether or not the branch has been pushed. Verified by the base
  equality above rather than by reasoning.
- `ambiguous-signals` — `Checked N commit(s)` and the pass/fail line now agree,
  because N is the number CI would check. The report already printed N; what
  changed is that N means something.
- `when-the-fallback-fails` — each of the three links has a test, and each fails
  when its link is removed. `_git` returns `""` on a failed git call rather than
  raising, which is what makes the chain work, and `-q` on `symbolic-ref` keeps
  an unset ref off stderr.
- `declared-vs-enforced` — the stacked-PR limit is real and is written in the
  docstring and the CHANGELOG rather than left for someone to discover: a local
  range is wider than CI's when a PR targets a non-default branch. Wider checks
  more commits, not fewer.
- Considered and declined: reading `.github/workflows/*.yml` to discover the
  base a PR would declare. The workflow does not know it either — GitHub
  supplies it per event — so this would add a parser for an answer that is not
  in the file.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — Pass 2 removed a thrice-written git call
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked — CHANGELOG entry under [Unreleased];
                                          scripts/gate_steps.py requires one
Group 5 · Intuitive UI                [x] n/a — no screen or control; the gate's stdout is
                                          the surface, and `Checked N commit(s)` now means it
Group 6 · Signal integrity            [x] checked — this slice IS Group 6: a gate reporting a
                                          pass over an empty range
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; reads git refs
                                          from the checkout and passes them to git merge-base

Tests added/updated:      scripts/test/test_gate_steps.py — 26 tests to 30: the base is the
                          base branch, the range is not empty once pushed, origin/main when
                          origin/HEAD is unset, HEAD~1 when neither is known. The fixture
                          asserts it reproduces a pushed branch, because without that the
                          first three passed against the unfixed code.
Mutation-checked:         by hand, 4 mutants on the resolution and each link of the fallback
                          chain, all caught. mutation_check.py has no curated entry for
                          gate_steps._merge_base — the same gap already recorded for
                          _kg_shape and runtime/cli.py's scaffold path.
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:c2018b7baa18
Gates run locally:        pytest (scripts/test/, and the full suite before pushing), ruff,
                          py_compile, mypy==1.14.1 from requirements-lint.txt, agentsmith
                          gate kg check, process gate (design + review) — which for the
                          first time in this session checked a non-empty range — artifacts
Declared gaps:            one, in the docstring and the CHANGELOG: for a pull request opened
                          against a non-default branch, the local range is wider than CI's.
                          A local run cannot know the base a PR will declare.
```
