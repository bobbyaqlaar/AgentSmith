# Review — the method that removes any node is not called `remove_file`

Design: `.agent-rfc/designs/kg-remove-node-name.md`. Owner's instruction, 2026-10-18: "rename
remove_file too" — the nit recorded in `.agent-rfc/reviews/kg-purges-guardrails.md` pass 2.

**Built evidence (2026-10-18):**

- **Every caller found before renaming**, by `grep` over `*.py`, `*.md`, `*.json`, `*.yml`: two in
  `scripts/map_codebase.py` (the file purge and the guardrail purge), three in
  `scripts/test/test_knowledge_graph.py`, and the symbol's own appearance in
  `.agent-rfc/fixtures/knowledge_graph.json`, which the walk regenerates. No contract, document or
  workflow names it.
- **No alias, and the reason is checked rather than assumed:** `pyproject.toml` distributes
  `packages = ["runtime", "runtime.workflows", "runtime.machine"]`, so `scripts/` is not installed,
  and `runtime/cli.py:1028` runs `local_knowledge_graph.py` as a **subprocess** with `--impact`
  rather than importing it. Nothing outside this repository can hold a reference to the method.
- **Tests first:** `test_remove_node` (the renamed existing test) and
  `test_remove_node_removes_any_node_type` (new) both failed on `AttributeError`; 16 of 16 in the
  file after the rename.
- **Hand mutants: 3 of 3 caught**, each reverted — the method doing nothing, the missing-id guard
  dropped (so a no-op call raises), and the removal not persisted. The third is the one worth
  having: an unsaved removal leaves the node in the graph on disk, which is the stale-node defect
  this week has already fixed twice.

## Pass 1 — findings: 0

- `grep-for-siblings` — the module's other file-shaped names were read and left alone:
  `upsert_file`, `impacted_files`, `find_files_by_symbol` and `fetch_subgraph_context_window`'s file
  hints are all genuinely about files. Only the removal method took an id of any type.
- `test-the-contract` — the new test asserts what the method removes (a `Guardrail`, a
  `ProductionIncident`) and what it leaves (`app.py`), rather than asserting through a purge that
  would pass for other reasons.
- `no-redundant-artifacts` — the apologetic comment in `scripts/map_codebase.py` is gone, which was
  the point; no deprecation shim is left behind for callers that cannot exist.
- `ambiguous-signals` — name, parameter and docstring now say the same thing, and the docstring
  records the old name and the date so a reader of a stale branch can follow it.
- Both call sites are exercised end to end by `test_a_file_the_walker_no_longer_claims_is_purged`
  and `test_a_guardrail_whose_document_is_gone_is_purged` through `run_map`, not only directly.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked — the slice is a naming defect
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_knowledge_graph.py — 1 renamed, 1 added (15 → 16), both
                          failing first on AttributeError
Mutation-checked:          3 by hand, 3 caught, each reverted
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json — the symbol list for
                          scripts/local_knowledge_graph.py carries the new name
KG query:                 kg:b1d239676223
Gates run locally:         six by name, all passing — the process gate itself, commit
                          guardrails, ruff, py_compile, --check-kg, bash -n/zsh -n — plus 175
                          tests over the graph, the KG drift gate, the gate's kg verbs, the
                          mutation journal and the shell gate. The regenerated fixture lists
                          `remove_node` and no longer lists `remove_file`
Declared gaps:             none for this slice
```
