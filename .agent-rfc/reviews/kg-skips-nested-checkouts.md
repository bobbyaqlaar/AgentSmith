# Review — the knowledge graph maps this repository, not a checkout living inside it

Design: `.agent-rfc/designs/kg-skips-nested-checkouts.md`. Not asked for: found on 2026-10-16 by the
full suite, while verifying `.agent-rfc/designs/shell-gate-one-walk.md`.

**Built evidence (2026-10-16):**

- **How it surfaced.** `pytest` over the whole repo: 1 failed, 2394 passed —
  `test_documented_env_vars_exist.py::test_allowlist_entries_are_still_orphans` reporting
  `['TENANT_SCOPE_HEADER', 'ROLE_HEADER'] are now referenced in code`. Those are retired portal
  header names, allowlisted as history. `git grep` found them in no tracked source file of this
  branch — only in the archive, an old review record, and `.agent-rfc/fixtures/knowledge_graph.json`,
  which I had regenerated an hour earlier. The graph held **791 nodes, 196 of them** under
  `.claude/worktrees/magical-babbage-99cac4/…`: a Claude Code worktree of another branch, with the
  old portal still in it.
- **Both halves confirmed before fixing.** `_iter_source_files` skips directories by name, and
  `.claude` is not a name in that list; the purge required a node to be unseen **and** its file to be
  gone, so the foreign nodes could never be removed while the worktree existed. The second half was
  found by the fix not working: the ignore rule landed, the graph rebuilt, and all 196 were still
  there.
- **Tests first, both failing.** `test_walker_ignores_a_checkout_living_inside_the_repo` (4 files
  mapped where 2 belong) and `test_a_file_the_walker_no_longer_claims_is_purged` (`purged == 0`,
  expected 1). Both pass after the change; 12 of 12 in that file.
- **Measured after:** **596 nodes, 215 edges**, from 791 and 291. The fixture is searched by content
  for `worktree` and `.claude` — zero of each — and for the symbols this slice added to
  `gate_shell.py`, which are present, so the narrower walk did not drop the repository's own code.

## Pass 1 — findings: 1

- `test-the-contract` / `fixture-truth` — **finding:** the first version of
  `test_walker_ignores_a_checkout_living_inside_the_repo` wrote `ROLE_HEADER = 'x-role'` into its
  fake worktree file, to make the fixture look like the real thing. That **re-broke the check that
  found the defect**: `test_documented_env_vars_exist.py` reads every tracked source file, so a
  retired name in my test's string reads as "referenced in code again" — the test went on failing
  after the graph was clean, for a new reason. The literal is now a neutral `OLD_SETTING`, with a
  comment saying why no real retired name may appear there, and both files pass.

## Pass 2 — findings: 1

- `no-redundant-artifacts` / `test-that-cannot-fail` — **finding:** `.claude` had also been added to
  `IGNORED_DIRS`, and a hand mutant deleting it **survived**: the `.git` rule already catches every
  worktree this IDE makes, so the name asserted nothing. Worse than redundant — it would silently
  exclude a tracked hook script someone later adds under `.claude/`, where the rest of the walker
  maps untracked files on purpose. Checked what is actually tracked there: `.claude/settings.json`
  alone, which carries no source suffix and was never mapped. The name is **removed**; the general
  rule stands and is the one the tests pin. Mutants after that: **2 of 2 caught** (drop the `.git`
  probe → foreign nodes return; restore `and not (root / node_id).exists()` → the stale node
  survives).

## Pass 3 — findings: 0

- **Fixture read node by node, not trusted.** Against the committed fixture, the regenerated one
  **adds exactly four nodes** — `rfc:` entries for this slice's and the shell-gate slice's design and
  review records — and **removes none**. So the repository's own 592 nodes are untouched, and the
  pollution was never in `main`: it existed only in my working copy, and this commit is what would
  have carried it in.
- `environment-parity` — the point of the slice: `verify_system --check-kg` no longer answers
  differently depending on whether an IDE worktree happens to be open. Before: locally it rebuilt
  the polluted graph and compared it with itself (pass), while CI, which has no worktree, would see
  the committed file as stale.
- `guards-must-be-able-to-fail` — the purge now fires on the only case that needed it, pinned by a
  test that deletes nothing from disk.
- `declared-vs-enforced` — what the walker still maps on purpose (untracked files in the tree) is
  written down in the design as a product decision, not left implied.
- `grep-for-siblings` — the fix keys on the *kind* of directory, a checkout, rather than adding
  `.claude` to a list of names; the name is added too, as a cheap short-circuit, and the test pins
  the general rule. Checked the other walkers for the same assumption:
  `scripts/test/test_documented_env_vars_exist.py` and the process gate use `git ls-files`, which
  never saw the worktree — the mapper was the only filesystem walk with this exposure.
- `minimal-host-dependency` — the `.git` probe is wrapped, and an unreadable directory is treated as
  part of the repository: the status quo, never a silent exclusion.
- Performance read: the extra `rglob(".git")` costs one pass; the whole `--check-kg` run measured
  **10.6 s** wall on this machine, against a job that already parses every source file. The faster
  `os.walk` rewrite is declined here on purpose — it would reorder the fixture, and a fixture diff
  belongs to the slice that intends it.

## Pass 4 — findings: 0

Re-verified after pass 2 deleted the redundant `.claude` entry, because that edit changed the
walker's inputs and every number above was measured before it:

- `scripts/test/test_knowledge_graph.py` — 12 pass; `test_documented_env_vars_exist.py` — 4 pass,
  the failure that started this slice gone.
- Hand mutants re-run on the final walker: **2 of 2 caught**, each reverted.
- Fixture regenerated and read: **596 nodes, 215 edges**, no `worktree` or `.claude` node, and
  against the committed fixture exactly four added `rfc:` record nodes with nothing removed.
- `ruff check scripts/map_codebase.py` clean.

One note on reading mtimes in this repo, learned here rather than from the docs: `gates run`
executes `mutation_check.py`, which **edits working-tree files in place** and restores them, so a
gates run bumps the mtime of every file it mutates — including the two this record covers. That is
what the stop gate was reporting when it refused this turn, not an unreviewed edit. It also means an
**interrupted** gates run can leave a live mutation in the tree: `scripts/rules_port.py` was found
this afternoon with `_ours(...)` silently dropped from its placement check, left behind by a run
cancelled earlier, and reverted by hand. Offered to the owner as its own slice — restore on
`SIGTERM`/`SIGINT`, and refuse to start when a previous run left a file mutated.

## Pass 5 — findings: 1

The full suite on the final tree: **2396 passed, 1 failed** — and the failure was mine.

- `use-existing-apis` / `grep-for-siblings` — **finding:**
  `test_bare_except_tree.py::test_every_tracked_python_file_passes_the_bare_except_check` named
  `scripts/map_codebase.py:90`. My `except OSError:` carried a reason as ordinary prose
  ("unreadable: treat it as ours") where this repo requires the marker the checker reads,
  `# fail-open: <reason>` — an idiom the same file already uses four times, the nearest ten lines
  above the function I added. A comment a human can read is not the same as the one the gate reads.
  Now `# fail-open: an unreadable directory stays part of the repo`; the sweep and the 12 graph
  tests pass, `ruff` clean.

This is the pass the slice needed: three earlier ones measured the walker's behaviour, and the
defect left was in how the code was written, caught by a sweep over every tracked file rather than
by any test of this change.

## Pass 6 — findings: 0

Pass 5's finding fixed and re-verified. The change is one comment on the `except` line, so what is
re-run is what could see it:

- `test_bare_except_tree.py` — 2 pass, the sweep over every tracked Python file included;
  `test_knowledge_graph.py` — 12 pass; `ruff check scripts/map_codebase.py` clean.
- Nothing about the walker's behaviour moved: the edit is inside a comment, and the two hand mutants
  key on the `.git` probe and the purge condition, neither of which the line touches. They are
  re-run in the closing pass below rather than now, because a `gates run` is in flight and
  `mutation_check.py` edits the same file in place — two mutation runs over one file would corrupt
  each other's restore.

## Pass 7 — findings: 1

Producing this commit's fixture found one more, in the same place and of the same kind:

- `ambiguous-signals` / `no-redundant-artifacts` — **finding, declared as a gap rather than fixed
  here:** the purge this slice corrected covers **`CodebaseFile` nodes only**. An `rfc:` guardrail
  node is never purged at all, so a deleted design or RFC stays in the graph forever. Seen
  directly: with this slice's sibling records held aside, the rebuilt graph still carried
  `rfc:designs/shell-gate-one-walk.md` for a file that was not on disk. The fixture in this commit
  is correct because it was rebuilt from empty (`rm` the json, then `--check-kg`), which is also
  the workaround for anyone who hits it.
  **Not fixed in this slice:** the design's scope and its P13 argument are about files the walker
  claims; extending the purge to guardrail nodes changes what happens to every tenant's RFC nodes
  and deserves its own design, failing test and CHANGELOG entry. Offered to the owner as the next
  slice, and recorded in the sign-off's declared gaps.

## Pass 8 — findings: 0

The committed state read once more, after the rebuild and with the sibling slice held aside:
**590 nodes, 215 edges**, no `worktree` path, no `.claude` path, no record node for a file that is
not there, and `scripts/gate_shell.py` still mapped. `test_knowledge_graph.py` 12, plus
`test_bare_except_tree.py` 2 and `test_gate_shell.py` 120 in the same run — 134 pass; `ruff` clean.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — the slice is a signal-integrity defect
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_knowledge_graph.py — 2 added (10 → 12 in the file), both
                          failing before the change
Mutation-checked:          3 by hand, each reverted — 2 of 2 caught after pass 2 removed the
                          third's redundant line (neither changed file is a target in any
                          curated suite; `mutation_check.py --list` was checked against
                          both, so the hand mutants are this change's coverage): dropping the `.git` probe (foreign nodes
                          return), restoring `and not (root / node_id).exists()` to the purge
                          (the stale node survives). The survivor was `.claude` in
                          IGNORED_DIRS, which pass 2 deleted rather than pinned
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json — 791 → 596 nodes,
                          291 → 215 edges, no `.claude` or worktree node left; against the
                          committed fixture it adds only four `rfc:` record nodes and removes
                          nothing
KG query:                 kg:062879266e34
Gates run locally:         14 gates run individually by name, all pass: the process gate
                          itself ("Every gated commit has a design and a clean review"),
                          "Commit guardrails / enterprise RFC checks", ruff, py_compile,
                          DESIGN.md tree drift, redaction, --check-kg, on-prem template,
                          delivery evidence, delivery-model unit tests, bash -n/zsh -n, and
                          the two npm suites. mypy SKIPPED (it needs an install step; its
                          scope is `files = ["runtime"]`, so it never covered scripts/).
                          The portal's tsc and build gates were green in the full run earlier
                          and nothing since touches portal/. Full pytest on this tree:
                          2396 passed, 1 failed — that failure was pass 5's finding, fixed,
                          and its sweep passes now
Declared gaps:             (1) an `rfc:` guardrail node is never purged — pass 7, evidence
                          there; workaround is to rebuild the graph from empty, and the fix
                          is offered as its own slice. (2) the walker still maps untracked
                          files inside the tree, by design (an agent reasons about the tree
                          it is in); "tracked files only" would be a product decision and is
                          not taken here. (3) the curated gate-path mutation suites
                          (gate_contract, _v2, _v3, commit_guardrails) were NOT completed
                          locally: 32 mutations each re-running test_tenant_adopt.py and
                          siblings ran four hours without finishing, unsharded. CI shards
                          that step four ways in 10-12 minutes and nothing is pushed yet
```
