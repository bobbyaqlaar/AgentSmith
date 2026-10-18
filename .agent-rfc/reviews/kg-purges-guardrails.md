# Review — a guardrail node goes when the document behind it goes

Design: `.agent-rfc/designs/kg-purges-guardrails.md`. Owner's instruction, 2026-10-18: "purge the
stale rfc nodes too" — the gap this slice's predecessor (`a34c79d`) declared rather than fixed.

**Built evidence (2026-10-18):**

- **Cause reproduced before any code**, on this checkout: a throwaway `.agent-rfc/_probe-stale-node.md`
  appeared in the graph as `rfc:_probe-stale-node.md`; the file was deleted; the next walk still had
  the node. First seen the day before, in `.agent-rfc/reviews/kg-skips-nested-checkouts.md` pass 7,
  where `rfc:designs/shell-gate-one-walk.md` survived a file held aside for a commit.
- **Tests first**: `test_a_guardrail_whose_document_is_gone_is_purged` and
  `test_a_pillar_removed_from_cursorrules_is_purged` both failed; 13 passed. After the change, 15 of
  15 in that file. `test_a_production_incident_survives_the_walk` was written as the control and
  passed before **and** after — the point of it is that it must never start failing.
- **The probe cleaned itself up.** The regenerated fixture no longer carries
  `rfc:_probe-stale-node.md`, and a content check over every `rfc:` node finds **none whose document
  is missing** (166 of them). `ProductionIncident` nodes: none in this repository today, and the
  control test is what keeps the filter honest.
- **Hand mutants: 5 of 5 caught**, each reverted — no purge at all, a purge ignoring the node type
  (the control test fails), nothing recorded as seen (every guardrail deleted, so the
  "still there" assertions fail), `purged` not counted, and a purge narrowed to `rfc:` only (the
  `.cursorrules` pillar case fails).

## Pass 1 — findings: 1

- `design-before-code` — **finding, caught by the edit gate rather than by me:** the first version of
  the design answered eleven pillars; P8, P9 and P10 were missing, and the gate refused the edit to
  `scripts/test/test_knowledge_graph.py` naming all three. They are n/a here (a build step with no
  telemetry, no orchestration, no model call) and now say so. Worth recording rather than quietly
  fixing: the gate caught an incomplete design at the moment it mattered, which is the behaviour the
  programme exists for.

## Pass 2 — findings: 0

- `grep-for-siblings` — the node types a walk can produce are `CodebaseFile` (purged one slice ago)
  and `Guardrail` (this slice). `ProductionIncident` is the only other type in
  `scripts/local_knowledge_graph.py`, it is not walk-produced, and it is excluded by type with a test
  to prove it. No fourth type exists — checked by reading `node_type=` in that file, four hits, three
  distinct types plus the counter.
- `guards-must-be-able-to-fail` — the graph's cleanup path now fires for both produced types; each
  has a mutant that fails a test.
- `declared-vs-enforced` — a guardrail node is presented to an agent as a rule in force, so a
  document that no longer exists must stop being one; that is the sentence in the CHANGELOG entry and
  the reason the slice is not cosmetic.
- `early-exit-keeps-the-record` — placement matters: beside the file purge (before the three
  extractions) this code would delete every guardrail the same run then re-adds, leaving a correct
  graph by accident and a wrong `purged` count. It sits after extraction, and the comment says why.
- **A nit I am not fixing here, with the reason:** `kg.remove_file(node_id)` removes any node by id,
  so it is what this purge calls, but its name and docstring say `CodebaseFile`. Renaming it touches
  `scripts/local_knowledge_graph.py`, which this design's scope does not cover and which has other
  callers; the call carries an inline comment instead. Offered to the owner as a rename slice.
- Re-read the whole diff: `seen_guardrails`, three `.add` calls, the purge block, three tests.
  Nothing else.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the purge mirrors the file purge deliberately
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — a stale rule reading as live is the defect
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_knowledge_graph.py — 3 added (12 → 15), two failing first and
                          one written as a control that must never start failing
Mutation-checked:          5 by hand, 5 caught, each reverted
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json — the probe node from the
                          reproduction is gone, 166 `rfc:` guardrails all backed by a document
                          that exists, checked by content
KG query:                 kg:aed66d8a7dd8
Gates run locally:         six by name, all passing — the process gate itself, commit
                          guardrails, ruff, py_compile, --check-kg, bash -n/zsh -n — plus the
                          suites this change can reach: the graph's own tests, the KG drift
                          gate, the gate's kg verbs, the bare-except and env-var sweeps, and
                          the mutation journal. NOT run: the full `gates run`, whose curated
                          mutation step is unsharded locally (four hours yesterday); CI shards
                          it four ways
Declared gaps:             a renamed document is a delete plus an add, as it is in git — no
                          attempt to follow a rename. `remove_file` keeps its file-shaped name
                          (pass 2). The deferred two-agent lock is untouched
```
