---
status: active
scope:
  - scripts/map_codebase.py
  - scripts/mutation_check.py
  - scripts/test/test_knowledge_graph.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# The graph's ignore list applies inside the repository, not to the path leading to it

## Problem

`scripts/map_codebase.py` skips a file when any part of its **absolute** path is in `IGNORED_DIRS`. A repository anywhere under
a directory called `coverage`, `build`, `dist`, `out`, `venv` or the like therefore maps no source file at all. The run reports
nothing wrong, and it writes a graph holding only guardrails, with no edges.

Found by accident on 2026-11-05: a worktree named `coverage` regenerated the graph from 629 nodes and 215 edges to 210 and 0, and
the commit went through. A user with `~/build/my-app` gets that graph from `tenant init` onward, and every impact query answers
from it. Nothing would tell them.

## Approach

Test the path relative to the repository root. Directories inside the repository are ignored exactly as before.

`scripts/map_codebase.py` is the only code outside tests that matches an ignore list against `.parts`; a search of `scripts/`,
`agentsmith/` and the hooks found no other.

## Pillars

- P1 applies — `.agent-rfc/designs/kg-ignores-only-inside-the-repo.md` records the reproduction before the fix.
- P2 n/a — no dependency or structural change.
- P3 n/a — no traced code path changes.
- P4 applies — `scripts/test/test_knowledge_graph.py` maps a repository under an ignored name, and still refuses the same name inside it.
- P7 n/a — no stack-specific rule changes.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — no untrusted content is read differently; only the prefix of the path stops being compared.
- P12 n/a — no secret is read or written.
- P13 applies — `scripts/mutation_check.py` gains a mutation restoring the absolute path, in `knowledge_graph`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `scripts/map_codebase.py` no longer turns a directory name into a silent empty answer to an impact query.
- P16 applies — `scripts/map_codebase.py` repairs an emptied graph on the next regeneration, as the walk finds the files again.

## Deviations

none

## Dependencies

none

## Levers

- `environment-parity` — the result depended on where the checkout sits, which CI and local development never varied.
- `when-the-fallback-fails` — an empty walk wrote an empty graph and reported success.
- `test-the-contract` — the tests mapped checkouts whose temporary paths never held an ignored name.
