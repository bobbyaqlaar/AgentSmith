# Review — vacuous-sweep-guards

Design: `.agent-rfc/designs/vacuous-sweep-guards.md`
Levers: `docs/review-levers.md` (all 55, with `every-line-earns-its-place` asked for by name)

## Pass 1 — findings: 3

All three are the same defect, found by an AST sweep for tests whose only
assertions sit inside a loop over a filesystem-derived list.

1. **`runtime/test/test_provider_dispatch_cloud.py` — the adapter sweep.** Visits
   four adapters today and asserts each delegates to a shared parser; nothing
   asserts it visited any. Proven: renaming `parse_response` in
   `runtime/provider_dispatch.py` made it pass before the guard and fail after.
2. **`scripts/test/test_no_hardcoded_model_ids.py` — the template glob.** Rename
   `workflow-templates/` and it certifies nothing. Its neighbour proves the
   detector works on a synthetic probe, which is a different guarantee.
3. **`scripts/test/test_scratch_tenants.py` — the apps walk.** Guarded only by a
   sibling test in the same file that happens to compare against a non-empty
   registry.

Each now asserts the size of what it swept, against something meaningful rather
than a magic number.

### Swept and clean — recorded because the answer is the useful part

- **Dead code: none.** Every function in `runtime/` and `scripts/` matched against
  every mention anywhere in the repository — zero never-referenced.
- **Wrappers: none to remove.** 17 pure pass-throughs, all load-bearing —
  `delegating.py` is the SEC-control dispatch table and `run(control, ctx)` is a
  called-by-name interface. The 85 "single-caller trivial body" candidates are
  mostly `_cmd_*`, which is argparse's dispatch table.
- **Comment bloat: none.** The seven files added in the last four slices measure
  0.47 comment-to-code against a repository norm of 0.44.
- **Duplicated test helpers: 5, none worth merging.** `_git` and
  `_run_post_checkout` are three-line builders in three modules each; the two
  modules sharing `_clean`/`_declare` test different halves of one feature and
  say so in their docstrings.
- **Declared-but-unread config: one, see Pass 2.**

## Pass 2 — findings: 1

Recorded, not fixed.

1. **`declared-vs-enforced` — `Adapter.fail_closed` has no reader and no stated
   meaning.** It appears exactly twice in the repository, both times as a field
   declaration (`scripts/gate_ides.py:194`, `scripts/gate_models.py:137`), is set
   for all seven adapters and mirrored into `templates/governance.json`'s `ides`
   list, and **nothing reads the value**. Its sibling `note` is unread too.

   I am not fixing it, because fixing it means deciding what it should mean, and I
   could not establish that from the code. The values are not what an outside
   reader would guess: `cursor` and the neutral profile are `True`; `claude` is
   `False` — while Claude's own note says "the shell fallback prints a deny", and
   `.githooks/process-gate`'s fallback emits Claude-dialect deny JSON. Meanwhile
   `docs/process-gates.md:792` states one blanket rule, "Only the edit gate fails
   closed", with no per-IDE qualifier.

   So there are three descriptions of one property — a per-adapter boolean, a
   per-adapter prose note, and a repo-wide sentence — and no code that reconciles
   them. Inventing a consumer would risk encoding a meaning the owner did not
   choose. Recorded for the owner with the evidence above.

## Pass 3 — findings: 0

Fresh sweep, nothing new.

- The detector was re-run after the fixes: of 12 tests that sweep a filesystem
  list, the three with no effective outer assertion are the three fixed here.
- `ruff check` clean on all three files.
- The three suites pass together: 44 tests.
- No production code changed, so no behaviour moved — only what the tests refuse
  to let past.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — swept for dead code, wrappers and duplicated
                                          helpers; all three came back clean and the results are
                                          recorded above rather than left as "looked at it"
Group 2 · Quality / safety            [x] checked — three checks that could pass without looking
                                          now cannot; no production code touched
Group 3 · Architecture / hygiene      [x] checked — one assertion per test, no helper introduced
                                          for three call sites in three modules
Group 4 · Process                     [x] checked — three passes; Pass 2's finding is recorded
                                          rather than guessed at, which is the honest outcome when
                                          the fix needs a decision I cannot source
Group 5 · Intuitive UI                [x] n/a — no screen
Group 6 · Signal integrity            [x] checked — "found no offenders" and "looked at nothing"
                                          were the same green tick; each now says which it is
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      3 assertions in 3 existing tests. No new test file: the defect is that
                          existing tests did not assert enough, and a fourth test asserting that
                          they do would be further from the code than the line itself.
Mutation-checked:          not applicable — no production code changed. The equivalent proof is the
                          rename of `parse_response`, which passed before the guard and failed after.
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json via map_codebase.run_map(force=True);
                          test_kg_drift_gate.py passes
KG query:                 kg:dc51f54591eb
Gates run locally:         the three affected suites (44 passed), ruff check, artifacts, pillars,
                          KG drift
Declared gaps:             (1) Adapter.fail_closed and Adapter.note are read by nothing and their
                              meaning is unsettled — Pass 2, owner's call; (2) the detector is a
                              sweep run in this review, not a test, so a NEW vacuous sweep added
                              tomorrow is not caught by anything — making it a test would need a
                              way to tell a guarded sweep from an unguarded one that does not
                              produce false positives on the 9 it currently flags wrongly.
```
