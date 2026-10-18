---
status: active
scope:
  - scripts/local_knowledge_graph.py
  - scripts/map_codebase.py
  - scripts/test/test_knowledge_graph.py
---
# The method that removes any node is not called `remove_file`

## Problem

`AgentKnowledgeGraph.remove_file(rel_path)` removes whatever node carries that id. Its name, its
parameter and its docstring all say file:

```python
def remove_file(self, rel_path: str) -> None:
    """Remove a stale CodebaseFile node (e.g. deleted file)."""
```

Yesterday's guardrail purge (`fb61de5`) calls it for `rfc:<path>` and `cursorrules:pillar:<n>`
nodes, which are not files, and had to carry an inline comment saying so —
`kg.remove_file(node_id)          # removes any node by id, despite the name`. That comment is the
defect: a reader has to be told the name is wrong, and the next person purging a third node type
either repeats the comment or believes the docstring and writes a second removal method beside it.

Recorded as a nit in `.agent-rfc/reviews/kg-purges-guardrails.md` pass 2, out of that slice's scope
because the method lives in `scripts/local_knowledge_graph.py`, which that design did not cover.

## Approach

**Rename to `remove_node`,** with the parameter `node_id` and a docstring that says what it does:
removes the node with that id, of any type, and is a no-op when there is none. Update both call
sites in `scripts/map_codebase.py` — the `CodebaseFile` purge and the `Guardrail` purge — and drop
the apologetic comment, which the name now makes unnecessary.

**No deprecation alias.** Nothing outside this repository can call it: `pyproject.toml` distributes
`packages = ["runtime", "runtime.workflows", "runtime.machine"]`, so `scripts/` is not in the
installed package, and `runtime/cli.py` reaches this module as a **subprocess** (`--impact`), not by
import. Every caller is in `scripts/`, named by `grep` in the review. An alias nobody can reach is
dead code (`no-redundant-artifacts`).

**One new assertion, not just a rename.** The old name denied what the method does, so the tests
only ever removed a file node. `test_remove_node_removes_any_node_type` removes a `Guardrail` node
and a `ProductionIncident` node directly, which is the behaviour the guardrail purge depends on and
which nothing asserted before.

**Not in scope:** the rest of this module's file-shaped vocabulary (`find_files_by_symbol`,
`fetch_subgraph_context_window`'s file hints) — those genuinely are about files. The `remove_file`
name in `.agent-rfc/fixtures/knowledge_graph.json` is a symbol the walk records, so it changes when
the graph is regenerated, not by hand.

## Pillars

- P1 applies — this note (`.agent-rfc/designs/kg-remove-node-name.md`) precedes the change, and the nit it fixes is recorded in `.agent-rfc/reviews/kg-purges-guardrails.md` pass 2.
- P2 n/a — no dependency added; a rename inside one module and its two callers.
- P3 n/a — no tracing path; `scripts/local_knowledge_graph.py` is a build-time module.
- P4 applies — `scripts/test/test_knowledge_graph.py`: `test_remove_file` becomes `test_remove_node` against the new name, and `test_remove_node_removes_any_node_type` is added for the behaviour the old name denied. Both fail before the change — the first on `AttributeError`.
- P7 applies — the signature is annotated as before (`def remove_node(self, node_id: str) -> None`), matching the module's style.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 n/a — no new input is read; the node id already came from the graph or the walk.
- P12 n/a — no credentials.
- P13 applies — the graph feeds `agentsmith gate kg impact`, so a removal method that silently did nothing would narrow a review. `test_remove_node` keeps the no-op-on-missing-id behaviour pinned, and `scripts/test/test_knowledge_graph.py`'s two purge tests (`test_a_file_the_walker_no_longer_claims_is_purged`, `test_a_guardrail_whose_document_is_gone_is_purged`) exercise both call sites through `run_map`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated, because the symbol list for `scripts/local_knowledge_graph.py` carries the method's name.
- P15 applies — the name and the docstring said "file" while the behaviour said "any node"; a reader had two answers and the inline comment in `scripts/map_codebase.py` was the tell. One name, one meaning.
- P16 n/a — no failure path added or changed; the no-op on a missing id stays as it is.

## Deviations

none

## Dependencies

None added.

## Levers

- `ambiguous-signals` — the name denied the behaviour, and the fix was a comment telling readers to ignore the name.
- `no-redundant-artifacts` — no alias for callers that cannot exist, and the apologetic comment goes.
- `single-source-of-truth` — the method's name, parameter and docstring now say the same thing.
- `test-the-contract` — the added test asserts what the method actually removes, which the old name had kept out of the tests.
- `grep-for-siblings` — every caller found by `grep` before renaming, and the module's other file-shaped names checked and left alone because they really are about files.
