---
status: done
scope:
  - scripts/map_codebase.py
  - scripts/test/test_knowledge_graph.py
---
# A guardrail node goes when the document behind it goes

## Problem

`map_codebase.run_map` purges a `CodebaseFile` node the walk did not claim — that is
`.agent-rfc/designs/kg-skips-nested-checkouts.md`, committed in `a34c79d`. **`Guardrail` nodes are
not purged at all.** Every design, review, RFC and `docs/superpowers/` document becomes
`rfc:<path>` or `superpowers:<path>`, every `.cursorrules` pillar becomes
`cursorrules:pillar:<n>`, and once a node exists nothing ever removes it: delete the document and
the node stays forever.

Reproduced on this checkout, 2026-10-18, before writing any code:

```
$ printf '# A probe…' > .agent-rfc/_probe-stale-node.md ; <walk>
after creating the probe: True
$ rm .agent-rfc/_probe-stale-node.md ; <walk>
probe file deleted; its node still in the graph: True
```

It was first seen the day before, in that same slice's pass 7: with this slice's sibling records
held aside for a commit, the rebuilt graph still carried `rfc:designs/shell-gate-one-walk.md` for a
file that was not on disk. The workaround recorded there — delete the json and rebuild from empty —
is why the committed fixture shows **zero** stale guardrails today, and why this is worth fixing
rather than leaving: the graph is only clean while someone remembers to rebuild it from nothing.

Why it matters beyond tidiness: `fetch_subgraph_context_window` feeds guardrail nodes to an agent as
the rules in force, and `agentsmith gate kg impact` derives a review's scope from this graph. A
design that was deleted, superseded or renamed still reads as a live guardrail — the same
"declared-but-not-real" failure the cross-reference rule exists to stop in prose.

## Approach

**Symmetry with the file purge.** The walk already tracks `seen_files` and removes `CodebaseFile`
nodes it did not claim. Track `seen_guardrails` the same way — every `rule_id` upserted from
`.cursorrules`, `.agent-rfc/` and `docs/superpowers/` — and after the three extraction blocks remove
every `Guardrail` node not in that set, counting it in the existing `purged` stat.

**Only `Guardrail` nodes, and only after extraction.** Two boundaries the code has to respect:

- `ProductionIncident` nodes come from `inject_production_learning`, not from a walk, so a purge that
  went by "not seen" alone would delete another tool's data on the next run. The filter is the node
  type, exactly as the file purge filters `CodebaseFile`.
- The guardrail purge must run **after** the three extraction blocks, not beside the file purge,
  which runs before them. Put it in the wrong place and it deletes everything the same run is about
  to add.

**Why "not seen" is the right test here too.** A guardrail's source may be gone (`rm` of a design),
renamed (the id is the path), or no longer produced (a `.cursorrules` pillar someone deleted, a
`.agent-rfc/` directory a tenant never created). All four are the same fact — this walk does not
claim it — and keying on "the file no longer exists" would miss the pillar and the renamed section,
which is the mistake the file purge made in the other direction.

**Not in scope:** the edges a purged node carried go with it (networkx removes incident edges on
`remove_node`), and no attempt is made to detect a *renamed* document as the same guardrail. A
rename is a delete plus an add, which is what it looks like in git too.

## Pillars

- P1 applies — this note (`.agent-rfc/designs/kg-purges-guardrails.md`) precedes the change, and the defect is reproduced above and in `.agent-rfc/reviews/kg-skips-nested-checkouts.md` pass 7.
- P2 n/a — no dependency added.
- P3 n/a — the mapper is a build step and emits no spans.
- P4 applies — failing tests first in `scripts/test/test_knowledge_graph.py`: a deleted `.agent-rfc` document's node is purged, a `.cursorrules` pillar's node is purged when the file is gone, a `ProductionIncident` node survives the same walk, and the documents still present keep their nodes.
- P7 applies — `seen_guardrails: set[str]` beside `seen_files: set[str]` in `run_map`, annotated as that function already annotates.
- P8 n/a — no telemetry: the mapper is a build step whose only output is the graph file and its stat line.
- P9 n/a — no orchestration added or changed.
- P10 n/a — no LLM call; the walk is `ast` and regular expressions over files on disk.
- P11 applies — the walker reads documents it did not write, and this slice only *removes* nodes: `run_map`'s new purge compares node ids it already holds against `seen_guardrails` and parses nothing, so no new untrusted text reaches `scripts/map_codebase.py`.
- P12 n/a — no credentials.
- P13 applies — a review's scope comes from this graph (`agentsmith gate kg impact`), so removing nodes could narrow a review. What is removed is only a guardrail no document produces any more: `test_a_guardrail_whose_document_is_gone_is_purged` pins the removal and `test_the_guardrails_still_there_are_kept` is the positive control, both in `scripts/test/test_knowledge_graph.py`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated; the probe node this investigation left behind (`rfc:_probe-stale-node.md`) is itself the proof, and the review records the before and after counts.
- P15 applies — "gone", "renamed" and "no longer produced" are one fact for a guardrail, "this walk did not claim it"; `ProductionIncident` is kept separate by node type rather than by hoping a walk sees it, in `run_map`'s purge filter.
- P16 applies — the purge runs after the three extraction blocks in `run_map`, so a failure inside extraction cannot empty the graph's guardrails; `_extract_guardrails_from_cursorrules`, `_extract_guardrails_from_rfc` and `_extract_guardrails_from_superpowers` each already fail open per document, and a walk that extracted nothing because a source file is absent is the case this slice is about.

## Deviations

none

## Dependencies

None added.

## Levers

- `grep-for-siblings` — the file purge was fixed one slice ago; this is the node type that fix did not cover, found by its own review.
- `guards-must-be-able-to-fail` — the graph's only cleanup path now fires for every node type a walk produces, each pinned by a test.
- `declared-vs-enforced` — a guardrail node is a rule presented to an agent as in force; a document that no longer exists must stop being one.
- `single-source-of-truth` — the documents on disk are the source; the graph stops holding a second, older answer.
- `fixture-truth` — the regenerated fixture is checked by content for the probe node, not assumed clean.
