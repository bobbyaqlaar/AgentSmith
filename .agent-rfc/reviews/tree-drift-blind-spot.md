# Review — the tree said `workflow-templates/` held three families; it holds five

Design: `.agent-rfc/designs/tree-drift-blind-spot.md`. Owner, 2026-09-27: "Documents and knowledge
graph updated?"

## Pass 1 — findings: 2

The question was answered by running the checks, not by reading. Current and needing nothing:

- **the knowledge graph** — a forced `map_codebase.run_map(force=True)` produces no diff, and
  `verify_system.py --check-kg` passes with 467 nodes and 177 edges. That is the check that failed CI
  on `96b1bbd` earlier in this session, so it is the one worth running;
- **`CHANGELOG.md`** — twenty `###` entries under Unreleased, one per slice shipped today;
- **the artifacts registry** — `one file per type, no strays (enforce)`;
- **`docs/validation-checklist.md`** — its gates table was regenerated from the workflow tags in the
  previous slice, and `test_the_checklist_holds_the_generated_table` guards it;
- **the working tree** — clean, nothing uncommitted.

Two things were not:

1. `docs-match-behaviour` — **`docs/DESIGN.md`'s tree described `workflow-templates/` as "(ci-\* /
   cd-\* / eval-\* reusable workflows)"**, omitting `agentsmith-gates.yml` and `agentsmith-sync.yml`.
   Those are the two workflows that carry the governance and the subject of most of this session: a
   reader of the canonical tree would not learn a tenant receives them. Replaced with the families,
   naming those two individually because a tenant's governance depends on them specifically.
2. `check-that-fires-on-everything` — **the drift check could not have caught it.** It diffs
   second-level entries for `scripts`, `runtime`, `docs` and `fixtures`, chosen in 2026-07 after the
   P12 additions drifted at exactly that depth; `workflow-templates` was never added, so its contents
   were governed only by the top-level entry existing. Added to `DEEP_DIRS`.

## Pass 2 — findings: 1

1. `grep-for-siblings` — **the widened check found a second gap on its first run.**
   `workflow-templates/shadow-eval.yml` matched none of the four families I had just written, because
   it is a fifth — an opt-in scheduled sampler. Listed. This is the argument for widening the check
   rather than only fixing the sentence: the fix I had reasoned my way to was itself incomplete, and
   the check said so immediately.

## Pass 3 — findings: 0

- The drift check, run exactly as `self-test.yml` runs it, with `workflow-templates` in `DEEP_DIRS`:
  no top-level entry missing, no second-level entry missing, no ghost. It reported
  `workflow-templates/shadow-eval.yml` before the Pass 2 fix and passes after, so it is verified
  against a real miss rather than only against a green tree.
- Re-checked the other four deep directories after the change: unchanged and still passing.
- The knowledge graph needs no re-pin — no source file changed, only `docs/DESIGN.md`, a workflow
  comment and a list literal.

## Stated limits

- **`ci-*.yml` is a glob**, so a template named `ci-anything.yml` satisfies the tree without being
  described. That is the trade for not listing thirteen files; a file outside all five families still
  fails.
- **Six of eleven top-level directories still have no second-level check** — `templates`, `portal`,
  `contract`, `examples`, `enterprise`, `hooks`. Each could drift the way `workflow-templates` did.
  Widening them all would require listing or globbing their contents in the tree, which is a larger
  change than this answer warranted; recorded rather than done.
- **The tree is prose**, so a correct name with a wrong description passes.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — docs/DESIGN.md holds the only copy of the tree;
                                          nothing was duplicated to fix it
Group 2 · Quality / safety            [x] checked — no behaviour changed
Group 3 · Architecture / hygiene      [x] checked — the directory holding the governance workflows
                                          now describes them
Group 4 · Process                     [x] checked — three passes; Pass 2's finding came from the
                                          check widened in Pass 1
Group 5 · Intuitive UI                [x] n/a — no screen
Group 6 · Signal integrity            [x] checked — "documented at top level" and "contents
                                          documented" stopped being the same answer
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      none — the widened CI check IS the test, tagged `# agentsmith:gate`, and it
                          was run against a real miss (shadow-eval.yml) before the fix
Mutation-checked:          not applicable — no production code changed
Fixtures re-pinned:        none required; the knowledge graph was verified current and unchanged
KG query:                 kg:5ef82bf85b00
Gates run locally:         the repo-tree drift check as the workflow runs it, verify_system --check-kg,
                          the artifacts check
Declared gaps:             (1) `ci-*.yml` is a glob; (2) six top-level directories still have no
                              second-level check; (3) the tree is prose, so a right name with a wrong
                              description passes
```
