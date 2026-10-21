---
status: done
scope:
  - scripts/map_codebase.py
  - scripts/verify_system.py
  - scripts/test/test_knowledge_graph.py
  - scripts/mutation_check.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# The knowledge graph maps what git tracks, by repository-relative path

## Problem

`scripts/map_codebase.py` builds the graph from the filesystem and never asks git what belongs to the
repository:
- the source walk skips a fixed list of directory names (`IGNORED_DIRS`) and nested checkouts;
- the three document extractors glob `.agent-rfc/**/*.md`, `docs/superpowers/{specs,plans}/` and
  `.cursorrules` directly.

A file git ignores therefore becomes a node. Reproduced 2026-10-20 in a fresh worktree of `main`
(`b237499`): `agentsmith gates run` ran `scripts/delivery_evidence.py`, which writes
`.agent-rfc/fixtures/delivery_evidence.md` (gitignored, `.gitignore:49`). The next
`verify_system.py --check-kg` regenerated the graph with a Guardrail node for it, "Delivery Model —
promote evidence pack". The agent context built from the graph (`fetch_subgraph_context_window`)
then reads a generated, ignored file as a rule in force.

And every Guardrail node stores `source_file` as an **absolute** path:
- the committed graph's 187 Guardrail nodes all begin `/Users/mac/Documents/…`, the owner's machine,
  in a committed file;
- a graph built anywhere else differs on every one;
- CodebaseFile ids are already repository-relative.

`verify_system._kg_shape`, the comparison behind `--check-kg` and `kg check`, documents both defects
and works around them: it leaves Guardrail nodes and untracked files out. So the gate holds, but the
committed graph is still wrong, and it changes with whoever built it last.

## Approach

- **One list of what the repository holds.** `_mapped(root)` asks
  `git ls-files --cached --others --exclude-standard`: tracked files, plus untracked files no ignore
  rule covers, so a new design not yet added still maps. The source walk and the three extractors
  map only paths in it. The nested-checkout and `IGNORED_DIRS` skips stay.
- **When git cannot answer, everything maps, as before.** Outside a checkout, with no `git` on PATH,
  or when `ls-files` fails, `_mapped` returns None. Unknown is not "nothing is tracked", and a graph of
  nothing would purge every node.
- **`source_file` is repository-relative**, as CodebaseFile ids are. Nothing reads it as a path: its
  only reader is the graph file itself.
- **The existing purges clean up.** A regeneration purges the ignored document's Guardrail node
  (`kg-purges-guardrails`) and an ignored source file's node (the walk's own purge), and rewrites
  every `source_file`. The committed graph is regenerated with this change.
- **In AgentSmith itself, `.cursorrules` is generated and gitignored**, so its pillar nodes (18 in the
  committed graph, from the owner's local copy) leave this repository's graph. CI's graph never had
  them. The pillars live in `templates/agent-rules.yaml`, and agents read them through the rule files.
  A tenant that commits its `.cursorrules` keeps them.
- **`_kg_shape` keeps its exclusions.** Untracked-but-unignored files still differ between a working
  tree and CI. Its comment drops the two defects this fixes.
- **Tests** in `scripts/test/test_knowledge_graph.py`, in a real git repository:
  - an ignored `.agent-rfc` document and an ignored source file produce no node, and an existing node
    for either is purged;
  - an untracked, unignored design still maps;
  - `source_file` is repository-relative;
  - outside a git checkout, everything maps.

## Pillars

- P1 applies — `.agent-rfc/designs/kg-maps-what-git-tracks.md` records the reproduction and the committed graph's absolute paths before the change.
- P2 applies — one helper, `_mapped`, decides membership for the source walk and all three extractors in `scripts/map_codebase.py`; no dependency added (`subprocess` is the standard library).
- P3 n/a — a developer tool with no service path.
- P4 applies — `scripts/test/test_knowledge_graph.py` holds the ignored, untracked and no-git cases against a real repository.
- P7 n/a — no model built from external data.
- P8 n/a — no telemetry.
- P9 n/a — no agent code; the agent context built from the graph only loses nodes it should not have had.
- P10 n/a — no model call.
- P11 n/a — the inputs are git's own file list and this repository's files.
- P12 applies — `.agent-rfc/fixtures/knowledge_graph.json` stops carrying a machine's home-directory path in a committed file.
- P13 applies — `scripts/verify_system.py`'s `_kg_shape` comparison is unchanged in what it compares; only its comment changes, so `kg check` keeps its verdicts.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated: relative `source_file` throughout, and no node for an ignored file.
- P15 applies — `scripts/map_codebase.py` treats "git cannot say" as unknown and maps everything, never as an empty repository.
- P16 n/a — a reverted commit restores the old walk; the next regeneration rewrites the graph either way.

## Deviations

none

## Dependencies

none

## Levers

- `single-source-of-truth` — git's own list decides what the repository holds, once, for every walk.
- `ambiguous-signals` — "git cannot answer" and "git lists nothing" are different answers.
- `environment-parity` — a graph built on any machine, or in CI, holds the same nodes and paths.
- `test-the-contract` — tested against a real git repository, not a stubbed file list.
