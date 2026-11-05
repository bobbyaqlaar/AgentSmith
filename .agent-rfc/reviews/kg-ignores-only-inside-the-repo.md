# Review: kg-ignores-only-inside-the-repo

## Pass 1 — findings: 0

- **Inside the repository nothing changes:** a tracked `build/made.py` stays out of the graph, in the same test.
- **`path` is always under `root`:** it comes from `root.rglob`, so `relative_to` cannot raise.
- **No other site has this:** a search of `scripts/`, `agentsmith/` and the hooks for an ignore list matched against `.parts` found only this one, and `test_hitl_gate.py`'s sweep already uses the relative path.
- **The test fails without the fix:** run with the old line restored, and held by a mutation.
- **The committed graph is sound:** this tree regenerates it with its files and edges in place, and `--check-kg` passes.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — one expression in one walk.
Group 2 · Quality / safety — [x] checked — the walk's answer no longer depends on where the checkout sits.
Group 3 · Architecture / hygiene — [x] n/a — no dependency or structural change.
Group 4 · Process — [x] checked — design before the fix; CHANGELOG entry; one mutation.
Group 5 · Intuitive UI — [x] n/a — no interface.
Group 6 · Signal integrity — [x] checked — an impact query no longer answers from an emptied graph because of a directory name.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: `scripts/test/test_knowledge_graph.py`.
Mutation-checked: `scripts/mutation_check.py knowledge_graph`, 4 of 4 caught, including the new one.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `test_knowledge_graph.py` and `test_kg_drift_gate.py` (37 passed); ruff; py_compile; repo-tree; Commit guardrails; check-kg; artifacts; process gate. Self-Test runs the full suite, the other mutation suites, and the portal and widget gates.

Levers reviewed: `environment-parity`, `when-the-fallback-fails`, `test-the-contract`.

KG query: kg:15e697cc65e2
