# Review — the drift gate compares tracked Guardrail nodes

Design: `.agent-rfc/designs/kg-check-sees-tracked-guardrails.md`. Raised by the
owner: *"correct the errors and fill the gaps found"*. The errors and gaps are
the ones this session reported and did not close — the gate that reported green
over a stale fixture, and the list-valued fixtures recorded as out of scope in
`.agent-rfc/reviews/ts-sweep-runs-once.md` Pass 1.

**Built evidence (2026-10-28):**

- **The defect, reproduced end to end on the real graph rather than argued.**
  `rfc:reviews/design-tree-drift-is-a-pytest-test.md` deleted from
  `.agent-rfc/fixtures/knowledge_graph.json` (598 → 597 nodes):

  | gate | verdict on the stale graph |
  |---|---|
  | this change | `❌ knowledge_graph.json was stale` |
  | `HEAD`'s `_kg_shape`, loaded from git | stale and pristine graphs **compare equal** |

  The second row is the bug, measured directly, not inferred from the symptom.
- **Failing test first, and again after restructuring.**
  `test_shape_catches_a_removed_guardrail`,
  `test_shape_catches_a_retitled_guardrail` and
  `test_guardrails_are_actually_in_the_shape` were written before the fix and
  ran `3 failed, 11 passed`. Re-proved after Pass 1 reworked the fixtures: the
  same three fail when the filter is replaced with `if False`.
- **Seven mutants on the new comparison, each caught by the right tests:**

  | mutant | tests that failed |
  |---|---|
  | guardrails excluded entirely (the original bug) | removed, retitled, pillar, in-the-shape |
  | trackedness filter dropped | untracked nodes, untracked guardrails, absolute paths |
  | `pillar` dropped from the tuple | pillar |
  | `id` dropped | in-the-shape |
  | `title` dropped | retitled, in-the-shape |
  | `guardrails` key left out of the shape | removed, retitled, pillar, in-the-shape |

- **The gate still passes on a current graph** —
  `✅ … compared 413 tracked file(s), 185 guardrail(s) and 215 edge(s)` — which
  is the P13 worry: the exclusion existed because comparing these nodes used to
  fail every CI run, and a false-positive gate gets deleted. 185 compared where
  0 were.
- **mypy scope checked, not assumed:** `pyproject.toml [tool.mypy] files =
  ["runtime"]`, so nothing changed here is in its scope. `ruff` clean,
  15 tests pass in `test_kg_drift_gate.py` (9 before), 11 in
  `test_design_tree_drift.py`.
- **Line counts:** `test_kg_drift_gate.py` 90 → 138 code lines for 6 new tests,
  one helper and one fixture — 8 per test.

## Pass 1 — findings: 2

- `parameterize-dont-clone` — I had added a `write_rails` fixture and a
  `_graph_with_rails` helper that duplicated the existing `write_graph`
  fixture's counter-and-tmp_path pattern with a different node list.
  `write_graph` gained a `rails` parameter instead and both went away: one
  place writes a graph.
- `no-copy-paste` — all six new tests opened with the same two lines stubbing
  `_git_tracked_files` wider. A `vs_rfc` fixture states it once, and states it
  where the `vs` docstring's warning about examining nothing already lives.
  Unlike the previous two slices, this dedupe genuinely removed lines.

## Pass 2 — findings: 2

- `test-that-cannot-fail` — `pillar` was one of the three compared fields and
  **no test varied it**, so dropping it from the tuple changed no result: a
  branch no input reaches rather than a guard. Added
  `test_shape_catches_a_changed_pillar`, and verified the mutant it exists for
  now fails.
- house style — `_rail`'s `pillar=None` was the one unannotated parameter in a
  file that annotates everything. `pillar: str | None = None`.

## Pass 3 — findings: 3

All three in text I had added **for the sake of accuracy**, which is where an
inaccuracy costs most:

- `docs-match-behaviour` — the code comment said "11 CI checks passed" and the
  CHANGELOG entry said "seven required CI checks", about the same event. Both
  true; stating two numbers in two places is how a reader learns to trust
  neither. Both now say "all 11 checks … 7 of them required".
- `aggregates-name-their-scope` — the new verdict message exists to name what
  was compared, and it named "name, language, symbols and title" while the
  comparison also included `pillar`. A scope line that is itself incomplete is
  worse than none. Now "…, title and pillar".
- `every-line-earns-its-place` — `counted = json.loads(before)` parses this
  function's own output, which a reader will stop on. One comment saying why:
  the shape **is** what was compared, so counting the graph instead would
  report a scope the verdict does not rest on.

## Pass 4 — findings: 0

- `gate-integrity` — the check can now fail for the staleness that occurred,
  shown by the end-to-end reproduction, and still cannot fail for the reason the
  exclusion was added, shown by `test_untracked_guardrails_are_excluded` and
  `test_absolute_source_paths_are_excluded` plus a passing run on the real
  graph.
- `declared-vs-enforced` — 184 declared Guardrails, 0 enforced, became 185
  declared and 185 enforced. The number is in the gate's own output, so the next
  reader does not have to take this record's word for it.
- `provenance-and-precedence` — `source_file` is the only field used to decide
  trackedness, and `scripts/map_codebase.py` writes it repository-relative since
  `kg-maps-what-git-tracks`; the absolute-path case from before that fix is
  excluded by the same comparison rather than by a branch for it.
- `when-the-fallback-fails` — `_kg_shape` still returns `None` when git cannot
  answer or the graph is unreadable, and `check_kg_fresh` still skips rather
  than guessing; the new block is inside those early returns and
  `test_shape_is_none_when_git_cannot_answer` and
  `test_missing_or_unreadable_graph_is_none` still pass.
- Considered and **declined**: comparing a digest of each rfc document's body,
  which would catch an edited design whose title is unchanged. The mapper stores
  no such digest, adding one changes the graph's schema and every tenant's
  committed fixture, and it is a different question from this gate. Recorded as
  a declared gap below rather than left implied by the word "matches".
- Considered and **declined**: splitting the sibling file's one-word fixture fix
  into its own design and review. Roughly 150 lines of process for `tuple(...)`
  twice, on a gap this slice exists to close; folded in, with the scope widened
  in the design and the reason stated there.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — Pass 1 removed a cloned fixture and a
                                          six-times-repeated stub
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked — CHANGELOG entry added under
                                          [Unreleased]; scripts/verify_system.py requires one
Group 5 · Intuitive UI                [x] n/a — no screen or control; the gate's stdout is
                                          the only surface and it now names its own scope
Group 6 · Signal integrity            [x] checked — this slice IS Group 6: a gate that could
                                          not fail for the case it exists for
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; reads the
                                          committed graph and `git ls-files`, executes nothing

Tests added/updated:      scripts/test/test_kg_drift_gate.py — 9 tests to 15: removed,
                          retitled, changed pillar, untracked excluded, absolute paths
                          excluded, created_at ignored, and guardrails-are-in-the-shape as
                          the guard on the other six. scripts/test/test_design_tree_drift.py
                          unchanged in count; its two fixtures return tuples.
Mutation-checked:         by hand, 7 mutants on the new comparison, all caught, each by the
                          tests named in the table above; plus the end-to-end reproduction
                          against HEAD's _kg_shape. mutation_check.py's curated suite does
                          not cover verify_system._kg_shape — recorded as a gap below.
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json — and for the last time
                          verified by diffing node ids by hand; from here the gate is the
                          control, which is what this slice changes
KG query:                 kg:085a69e73a23
Gates run locally:        pytest (full suite), ruff, py_compile, agentsmith gate kg check,
                          process gate (design + review), artifacts; mypy skipped — not
                          installed here, and [tool.mypy] files = ["runtime"] excludes these
                          paths either way
Declared gaps:            two, both stated in the design and in the gate's own output rather
                          than implied away:
                          (1) an rfc document whose BODY changes without its title still
                              reads as current — the mapper stores no content digest;
                          (2) scripts/mutation_check.py's curated suite has no entry for
                              _kg_shape, so these seven mutants were run by hand and will
                              not be re-run by CI.
```
