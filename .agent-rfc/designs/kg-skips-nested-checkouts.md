---
status: done
scope:
  - scripts/map_codebase.py
  - scripts/test/test_knowledge_graph.py
---
# The knowledge graph maps this repository, not a checkout living inside it

## Problem

`scripts/map_codebase.py` walks the filesystem and skips directories by **name** (`IGNORED_DIRS`).
Nothing skips a nested git checkout, and this IDE puts one inside the repository: a Claude Code
worktree at `.claude/worktrees/<name>/`, which is a full checkout of another branch.

Measured on this machine, 2026-10-16: the regenerated graph held **790 nodes, 196 of them** from
`.claude/worktrees/magical-babbage-99cac4/…` — another branch's copy of the portal. It surfaced as a
**test failure in the full suite**, `test_documented_env_vars_exist.py::test_allowlist_entries_are_still_orphans`:
`ROLE_HEADER` and `TENANT_SCOPE_HEADER` are retired portal header names, allowlisted as history, and
the stale worktree still contains them — so the graph "referenced them in code" and the allowlist
check fired. The names are in no tracked file of this branch; `git grep` finds them only in
`docs/PRODUCT_ARCHIVE.md`, a review record, and the graph I had just rebuilt.

Three things follow, and the third is the reason this is worth a slice:

1. **The committed fixture depends on local dirt.** Whoever regenerates the graph with a worktree
   open commits a different file from whoever does not.
2. **`verify_system --check-kg` means different things in the two places.** It passed locally
   *because* it rebuilt the polluted graph and compared it with itself; in CI, where no worktree
   exists, the same committed file is stale. Green here, red there — the parity defect
   `.agent-rfc/designs/version-marker-test.md` was written about, in the other direction.
3. **A review's scope is derived from this graph.** `agentsmith gate kg impact` turns a change into
   the files a review must read, and its hash goes in the sign-off. Nodes from another branch's
   checkout are not files any review of this branch should read.

This is the same defect the file already carries a comment about: `dist` and `build` were ignored
but not `.next`, so the portal's Next.js output put 297 generated files into the graph — "two thirds
of every node in it". That was fixed by adding names. A nested checkout is not a name problem.

## Approach

Two rules, because they answer different questions:

- **A directory that is its own git checkout is not this repository.** `_iter_source_files` skips
  any path under a directory below the root that contains a `.git` entry — a worktree's `.git` is a
  file, a clone's is a directory, and `Path.exists()` covers both. That catches the worktrees this
  IDE makes, a vendored clone, or anything else someone checks out inside the tree, wherever it
  sits. The roots are collected once per walk.
- **`.claude` is tool state, not product code**, so it joins `IGNORED_DIRS` beside `.agents` and
  `.github`, which are already there. On its own this would fix today's case; it would not fix the
  next nested checkout somewhere else, which is why the first rule exists and is the one the test
  pins.

**And the purge has to answer one question, not two.** Adding the rules above was not enough: the
graph is incremental, and a `CodebaseFile` node was purged only when it was both unseen by the walk
**and** gone from disk. The 196 worktree files were still on disk, so they were never stale and the
rebuilt graph kept every one of them — adding an ignore rule could not clean a graph that already
held them. "This walk did not claim it" is the whole question, and `seen_files` holds every file the
walk included, skipped-as-unchanged ones too, so no file of ours can be caught by it. Measured
after the change: **595 nodes, 215 edges**, down from 791 and 291, with no `.claude` node left.

**Kept deliberately minimal: the walk stays `rglob` + filter.** Rewriting it as `os.walk` with
directory pruning would be faster and is tempting, but it would risk changing the order in which
files enter the graph — and the committed fixture is a byte comparison in CI. A performance change
to the walker is its own slice, with the fixture diff read on its own.

**What this does not do:** it does not make the graph independent of the filesystem — an untracked
file in the repository is still mapped, which is deliberate (an agent reasons about the tree it is
in, not the index). "Only tracked files" would be a different product decision, and the backlog is
where it belongs if it is ever wanted.

## Pillars

- P1 applies — this note (`.agent-rfc/designs/kg-skips-nested-checkouts.md`) precedes the change; the defect was found by `scripts/test/test_documented_env_vars_exist.py::test_allowlist_entries_are_still_orphans` failing over `.agent-rfc/fixtures/knowledge_graph.json`, not by reading code, and the measurement is in `.agent-rfc/reviews/kg-skips-nested-checkouts.md`.
- P2 n/a — no dependency added; `pathlib` is already imported.
- P3 n/a — the mapper emits no spans; it is a build step.
- P4 applies — two failing tests first in `scripts/test/test_knowledge_graph.py`: a nested checkout (a directory holding a `.git` file, as a worktree does, and one holding a `.git` directory, as a clone does) contributes no node while a sibling source file in the repository still does; and a node the walk stops claiming is purged **though its file is still on disk**, which is the half the ignore rule alone could not fix.
- P7 applies — the new helper is typed and returns a `set[Path]`, matching the module's existing annotations.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 applies — the walker reads files it did not write; it already parses them as data with `errors="replace"` and this slice only *removes* files from that set.
- P12 n/a — no credentials. Worth noting the opposite risk is also reduced: a nested checkout can hold another branch's files, and they no longer enter a graph that is committed.
- P13 applies — `agentsmith gate kg impact` derives a review's scope from this graph, so a narrower graph could narrow a review. What is removed is only what the walker does not claim: `scripts/test/test_knowledge_graph.py::test_walker_ignores_a_checkout_living_inside_the_repo` asserts the repository's own `app.py` is still mapped while the nested checkout's file is not, `test_a_file_the_walker_no_longer_claims_is_purged` pins the purge, and `.agent-rfc/fixtures/knowledge_graph.json` is read node by node in the review before it is committed.
- P14 applies — this *is* a fixture-drift slice: `.agent-rfc/fixtures/knowledge_graph.json` is regenerated, the 196 foreign nodes are gone (791 → 595 nodes, 291 → 215 edges), the file is searched for `.claude` and worktree paths by content, and both counts are in the review so the next drift is visible.
- P15 applies — "a file in this repository" and "a file in a checkout that happens to live inside it" were one signal to the walker; the `.git` marker separates them.
- P16 applies — if the `.git` probe raises (a permission error on a directory), the walk must not die: the probe is guarded and an unreadable directory is treated as part of the repository, which is the status quo rather than a silent exclusion.

## Deviations

none

## Dependencies

None added.

## Levers

- `environment-parity` — the committed graph stops depending on whether an IDE worktree happens to exist on the machine that built it.
- `grep-for-siblings` — the fix is the *kind* of directory (a checkout), not another name in a list, because the name list is what let this through after `.next`.
- `fixture-truth` — the regenerated fixture is checked for foreign nodes by content, not assumed clean because a test passed.
- `check-that-fires-on-everything` — 791 nodes where 595 belong is the "result too large to match the code" signal; it read as a discovery, not a bug, until the suite failed.
- `guards-must-be-able-to-fail` — the purge could not remove a node while its file existed, so the one cleanup path the graph has could not fire on the case that needed it.
- `ambiguous-signals` — `--check-kg` passing locally and failing in CI was the symptom; the cause was that each was comparing a different thing.
