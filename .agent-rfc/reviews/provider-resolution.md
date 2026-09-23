# Review — a tenant names its provider

Design: `.agent-rfc/designs/provider-resolution.md`, second slice of
`.agent-rfc/designs/governance-providers.md`. Owner, 2026-09-23: "next slice".

**Built evidence (2026-09-23):**

- **Failing tests first.** `scripts/test/test_provider_resolution.py` (11) drives the real
  `.githooks/process-gate` with stub providers; seven of ten failed before the launcher changed.
- **The seam is real:** a repository declaring a provider gets its decision, and the framework's
  own paths are never consulted — `test_the_declared_provider_answers`, and the mutation "the
  declaration is ignored" is caught.
- **Naming a provider is additive, not a migration:** three kinds of provider that do not answer —
  exit 3, a command that is not there, and one installed but too old to know the event — each fall
  through to the framework's gate, which still refuses the edit.
- **Mutation checks:** the `gate_contract` suite now carries 8, all caught, including the three
  resolution rules and adopt's declaration.

## Pass 1 — findings: 3

All three came from running it rather than reading it.

- `guards-must-be-able-to-fail` — **finding:** the launcher first fell through only on exit 3, 126
  and 127. The installed `agentsmith` on this machine predates the `gate` command and exits 2 with
  a usage error, which would have left that repository **ungated** — the failure mode this slice
  exists to avoid, and one every tenant would hit the day its provider lagged the contract. The
  rule is now "an answer is a decision on stdout": a provider that prints none has not answered,
  whatever its exit code. The contract and the design say so, and `TOO_OLD` pins it.
- `failure-is-not-a-result` — **finding:** the neutral profile crashed on a payload in another
  dialect (a Claude event), because `GateEvent` forbids extra fields and nothing caught the
  validation error. A provider handed something it cannot read must refuse, not crash: the parse
  raises `Unreadable`, which the gate already answers with a deny.
- `test-that-cannot-fail` — **finding:** the `"gate": "none"` test asserted silence in a repository
  that had no gate configuration, so falling back would have been silent too — the mutation
  survived. The repository is now configured so the framework *would* refuse, and silence means
  `none` was honoured.

## Pass 2 — findings: 0

Every lever over the launcher, the declaration, the schema, the adapter and the docs. Considered
and declined:

- Enumerating more exit codes rather than reading stdout. The list would never be complete — this
  slice found the third kind by accident — and a provider that prints a decision is unambiguous.
- Routing `commit-msg`, `sweep` and `ci` through a provider. Contract v1 does not define them;
  doing it here would pin AgentSmith's own CLI as the protocol.
- Declaring a provider in AgentSmith's own repository. It is the framework: its hooks should find
  its own script, and pointing them at an installed copy would test the wrong thing.

**Stated limits:**

- the declaration covers the `gate` port; telemetry, records and security are ignored for now and
  can be declared early without effect;
- a provider that serves IDE hooks must accept `--ide`; a neutral-only provider is valid, but a
  repository whose IDE configs pass a dialect needs one that translates;
- the fall-back to this framework's paths stays, deliberately: without it every existing tenant
  would break the day it adopted a declaration.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — hook output; each path was read end to end
Group 6 · Signal integrity            [x] checked — "declared ungoverned" and "no provider answered"
                                          stay different answers
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_provider_resolution.py (11),
                          scripts/test/test_tenant_adopt.py (+1)
Mutation-checked:          yes — gate_contract, 8 mutations; one survivor (the `none` test could not
                          fail) fixed and re-checked by hand
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:4fac20eb7034
Gates run locally:         ruff, mypy in a clean environment, the launcher's bash syntax, the gate,
                          adopt, IDE and CLI suites, and the full pytest run
Declared gaps:             (1) the `gate` port only; (2) an IDE-serving provider must accept --ide;
                              (3) the framework fall-back stays by design
```
