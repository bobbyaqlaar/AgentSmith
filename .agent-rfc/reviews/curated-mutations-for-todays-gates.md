# Review — the three gate fixes of 2026-10-30/31 get curated mutations

Design: `.agent-rfc/designs/curated-mutations-for-todays-gates.md`. Raised by the
owner: *"add the curated mutation entries"*, the item I had put third on my own
next-steps list.

**What was wrong.** `_kg_shape` (`scripts/verify_system.py`), `init_tenant`'s tail
(`runtime/cli.py`) and `_merge_base` (`scripts/gate_steps.py`) each shipped with
mutation evidence that was real — I ran the mutants and they failed tests — and
recorded **in prose, in a review record**. `scripts/mutation_check.py` had no entry
for any of them, so CI re-ran none of them. Two of the three are gates.

**Built evidence (2026-11-01):**

- **11 new curated mutations, 20 in the three suites, all caught.**

  | suite | mutations | status |
  |---|---|---|
  | `kg_drift_gate` (new) | 5 | 5 caught |
  | `gate_steps` (new) | 3 | 3 caught |
  | `vendoring_retired` (9 → 12) | 3 added | 12 caught |

- **Each of the 11 caught by the test named in its own entry, not by collateral
  damage.** Applied one at a time; the file was parsed with `ast.parse` first, then
  the suite run and the failing test names read off:

  | mutant | tests that failed | rest of suite |
  |---|---|---|
  | guardrails leave the shape (the `beeb838` regression) | removed/retitled/changed-pillar + guardrails-are-in-the-shape | 11 pass |
  | title not compared | retitled, guardrails-are-in-the-shape | 13 pass |
  | pillar not compared | changed-pillar | 14 pass |
  | trackedness filter dropped | untracked-nodes, untracked-guardrails, absolute-source-paths | 12 pass |
  | `created_at` in the shape | ignores-guardrail-created-at | 14 pass |
  | base back to `@{upstream}` | base-is-the-base-branch, range-is-not-empty, origin-main-fallback | 27 pass |
  | no `origin/main` fallback | origin-main-fallback | 29 pass |
  | no `HEAD~1` fallback | falls-back-when-no-base-branch | 29 pass |
  | mapper never runs | kg-check-stale-then-regenerated, scaffolded-graph-knows-its-records | 15 pass |
  | mapper runs before the records | kg-check-stale-then-regenerated, scaffolded-graph-knows-its-records | 15 pass |
  | `framework is not None` guard removed | scaffold-without-an-installed-framework (`TypeError` at `runtime/cli.py:443`) | 16 pass |

- `ruff` clean on both changed Python files. 49 tests in
  `test_mutation_check_journal.py` + `test_mutation_check_scope.py` still pass —
  the catalogue's own meta-tests.
- `scripts/test/test_vendoring_retired.py`: 16 tests to 17.

## Pass 1 — findings: 4

- `test-that-cannot-fail` — **my first version of the new test failed for the
  wrong reason.** It asserted `.agent-rfc` exists after a scaffold with no
  installed framework. It does not: `_provision_governance` returns `[]` when
  `framework is None`, so the whole `.agent-rfc` tree is never written. The test
  went red and read as *"the guard is broken"* when the guard was fine and my
  premise was wrong. Rewritten to assert `"README.md" in written` — the step
  immediately before the guard — with a message saying the test proves nothing
  about the guard if that is missing. The docstring now also records *why*
  `_templates_dir` is deliberately left unpatched: it resolves beside the file,
  so the run reaches the guard instead of returning early.
- `every-line-earns-its-place` — four mutation literals were written as
  single-line strings with `\n` escapes, one of them 127 characters (`ruff` E501
  ×3). Unreadable as well as long: the reorder entry's `before` was a 380-character
  one-liner. Rewritten as triple-quoted blocks matching the `map_codebase.py`
  entries' style, with `'''\` continuation so the first content line is not
  indented into the limit.
- `ambiguous-signals` — **`caught` does not mean "caught by the intended test".**
  The runner prints `caught` when *any* test in the suite fails, so a mutation
  that breaks the parse or an import reads exactly like one that trips the
  assertion. It matters most for the reorder entry, the only multi-statement
  mutation added. Closed for these 11 by hand — the table above is that check, and
  every one failed its own named test with the rest of the suite green. The check
  is **not re-runnable**, which is the same shape of gap these 11 entries closed,
  so it went to the backlog with a concrete fix (an optional expected-failing-test
  field and a third verdict).
- `fixture-truth` — `MINUTES` holds CI-measured per-suite durations from one run
  (38470842052, 2026-10-14). `vendoring_retired` is still listed at 0.7 having
  grown 9 → 12 mutations, three of them full tenant scaffolds, and the two new
  suites are absent (weighing the documented 1.0 default). **Not changed:** a
  locally measured number cannot go into a CI-measured table honestly, and the
  module's comment is right that a stale value costs shard balance, never a
  result. Backlogged as "refresh the whole table from one weekly full run".

## Pass 2 — findings: 1

- `grep-for-siblings` — 13 other review records say "by hand" without naming a
  curated entry (`artifact-consolidation`, `code-volume-sweep`, `evals-contract`,
  `gate-tag-coverage`, `kg-purges-guardrails`, `kg-remove-node-name`,
  `installed-architectures`, `portal-brand`, `installer-next-steps`,
  `portal-migrate-runs-in-the-image`, `portal-phase1-s7`, `provider-resolution`,
  `security-contract`). Not all are mutation claims — "by hand" also covers manual
  verification of other kinds — so the number is an upper bound, not a count of
  gaps. **Declared, not fixed:** this slice closes the three the owner named. A
  sweep of the other twelve is its own slice with its own design, and silently
  widening this one would make an unreviewed claim about files I have not opened.

## Pass 3 — findings: 0

- `guards-must-be-able-to-fail` — the whole point, and now verified twice over:
  every mutation caught, and every mutation caught by the right test.
- `implemented-not-invoked` — the entries are invoked. `shard()` deals the
  catalogue dynamically by weight, so the two new suites enter the CI plan with no
  workflow change; checked that nothing in `.github/workflows/self-test.yml` names
  suites statically. Under `--changed-since`, each new suite's triggers include the
  file its mutations edit, so a change to `verify_system.py`, `gate_steps.py` or
  `cli.py` selects it.
- `no-copy-paste` — `vendoring_retired` was extended rather than cloned, because
  it already owns `test_vendoring_retired.py` and already carried one `_kg_shape`
  mutation. The two new suites exist only because their test files had no owner.
  The repeated `before` literals (one string serving three `kg_drift_gate` entries,
  one serving three `runtime/cli.py` entries) are not duplication to remove: each
  `Mutation` is one independent edit with its own `after` and its own property, and
  the runner applies them separately.
- `single-source-of-truth` — the reorder entry's `before` **does** copy five lines
  of comment out of `runtime/cli.py`, because the two statements it reorders are
  separated by that comment and no shorter span can move them. Considered three
  ways round it and declined all three: inserting the mapper earlier leaves the
  real call in place, so the graph ends correct and nothing reproduces; deleting
  the `write_scaffold_records` call is a different mutation (records never
  written); and moving the comment out of the function to shorten the span would
  change production code to suit a test. The copy is declared in the design, and
  its consequence — rewrite the comment and the target goes stale — is the
  `expect-re-review` signal the module documents a remedy for.
- `one-catalog` — one `CATALOGUE`; no second list, no per-file registry.
- `declared-vs-enforced` — this slice moves three controls from declared to
  enforced. What stays declared is stated in the CHANGELOG and the design: the
  catalogue proves a mutation is caught, never that the catalogue is complete.
  mutmut's non-blocking job remains the exhaustive half and gains nothing here.
- `gate-integrity` — nothing got weaker. No threshold, exemption or allowlist
  changed; the diff is additive apart from the test rewrite in Pass 1.
- Considered and declined: a curated entry for `_kg_shape`'s *verdict string*
  (`check_kg_fresh`'s "compared N file(s), M guardrail(s)…"). A mutation on a
  print is caught only if a test asserts the message, and
  `aggregates-name-their-scope` is about the message being *true*, which the five
  shape mutations already pin. An entry there would assert the wording.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — vendoring_retired extended, not cloned;
                                          the repeated `before` literals are independent
                                          edits, not duplicated logic (Pass 3)
Group 2 · Quality / safety            [x] checked — Pass 1 fixed a test that failed for the
                                          wrong reason
Group 3 · Architecture / hygiene      [x] checked — two new suites, one extended; no new
                                          module, no new dependency
Group 4 · Process                     [x] checked — CHANGELOG entry under [Unreleased]
                                          (scripts/** requires one; scripts/test/** does
                                          not); two backlog items added
Group 5 · Intuitive UI                [x] n/a — no screen or control. The surface is
                                          mutation_check.py's stdout, unchanged
Group 6 · Signal integrity            [x] checked — this slice IS Group 6, and Pass 1 turned
                                          it on the runner itself: `caught` does not say
                                          which test caught it
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; the entries are
                                          literal source text matched against tracked files

Tests added/updated:      scripts/test/test_vendoring_retired.py — 16 to 17.
                          test_a_scaffold_without_an_installed_framework_still_completes is
                          the case no test reached: the `framework is not None` guard was put
                          there by mypy, not by a test, so a mutation removing it would have
                          survived and could not honestly be catalogued.
Mutation-checked:         11 new curated entries (5 kg_drift_gate, 3 gate_steps, 3 on
                          vendoring_retired); 20 mutations across the three suites, 20
                          caught, and each of the 11 verified by hand to fail the test named
                          in its own entry with the rest of its suite passing.
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:fb7d70bd25cd
Gates run locally:        pytest (the three suites' test files, the catalogue's 49 meta-tests,
                          and the full suite before pushing), ruff, mypy==1.14.1 from
                          requirements-lint.txt, mutation_check.py on all three suites,
                          agentsmith gate kg check, process gate (design + review)
Declared gaps:            three, all in the backlog or the CHANGELOG. (1) `caught` does not
                          name the catching test — closed by hand here, not re-runnably.
                          (2) MINUTES is stale for vendoring_retired and absent for both new
                          suites; costs shard balance only. (3) 13 other review records say
                          "by hand" without a curated entry — an upper bound on siblings,
                          left to its own slice.
```
