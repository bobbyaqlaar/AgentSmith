# Review — governance enforcement, G4 (reviews that use the graph)

Design: `.agent-rfc/designs/governance-enforcement.md` § G4, with the amendment written before
this code: what the hash covers, and why the gate reads the graph without networkx.

**Built evidence (2026-09-18):**

- **Failing tests first.** `scripts/test/test_gate_kg.py` (16) was written before `impact`; 14
  failed on the first run.
- **The gate's dependency list held the design still.** The first version put `impact` in
  `local_knowledge_graph.py` and imported that from the gate — which failed immediately, because
  that module reaches for `scripts/_shared.py` and networkx, and the gate runs in every tenant's
  git hooks with pydantic and OpenTelemetry and nothing else. `scripts/gate_kg.py` is the pure
  reader over the node-link JSON; the CLI re-exports it, so there is still one definition of "the
  scope of this change".
- **Dogfooded immediately:** AgentSmith runs `enforce`, so this slice's own review record carries
  the `KG query:` line below, and the commit gate recomputed it from this commit's file list.
- **Mutation checks (each reverted):** ten — dependents dropped from the scope, an unknown file
  dropped, the hash ignoring the scope, the sort removed, no lever groups derived, a missing line
  accepted, any hash accepted, a missing graph passing, `report` blocking, and the check never
  running. Nine caught; the tenth is finding 1.

## Pass 1 — findings: 2

- `test-that-cannot-fail`, `environment-parity` — **finding:** removing `sorted()` from the hash
  survived. The scope is built in a set, and set iteration order is stable *within one process* —
  which is exactly what the test measured. Across processes it is not: `PYTHONHASHSEED` differs,
  so a hash written by a developer would stop matching the one a git hook recomputes, at random.
  The test now runs the computation in two subprocesses with different seeds, which is the
  property that matters and kills the mutation.
- `declared-vs-enforced` — **finding, in the tenant CI template:** the step named "Validate
  Knowledge Graph" ran the mapper and then counted nodes **in the committed file** — it never
  compared the two, so a graph stale by months passed every run, and it printed "skipping
  staleness check" when the file was missing. It runs `verify_system.py --check-kg` now, the same
  check the framework runs on itself, which captures the committed shape before regenerating; and
  it blocks, since the missing-graph case is still a warning inside that check.

## Pass 2 — findings: 0

Every lever over the final diff: the impact function and its one-hop rule, the group derivation,
the hash, the three modes, the commit-gate wiring, the session-start line and the template.
Considered and declined: the transitive closure of dependents. Two hops out from a shared helper
is most of this repo, and a scope nobody can read is a scope nobody reads — the one-hop limit is
stated in the function and in the docs rather than left as a silent choice.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_kg.py (16); the fixture repo vendors gate_kg.py,
                          local_knowledge_graph.py and _shared.py
Mutation-checked:          yes — ten, each reverted; the survivor became finding 1
Fixtures re-pinned:        yes — .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:56f9d2e8eed8
Gates run locally:         ruff, the full pytest suite, --check-kg, `process_gate.py pillars`,
                          the hook-config and gates-table drift checks
Declared gaps:             (1) provisioning a graph at onboarding is G7, where it is already
                              listed; a repo with no graph is told so rather than passed;
                          (2) the scope is one hop of dependents, by choice;
                          (3) the commit gate does not rebuild the graph — freshness is CI's
                              job (`--check-kg`), because rebuilding on every commit would
                              cost more than it catches;
                          (4) lever groups are derived from path shape, which is a heuristic:
                              it points a reviewer at likely groups, it does not excuse the
                              others.
```
