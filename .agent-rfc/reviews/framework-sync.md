# Review — one command keeps a tenant current, and its own gates accept it

Design: `.agent-rfc/designs/framework-sync.md`, third slice of
`.agent-rfc/designs/governance-providers.md`. Owner, 2026-09-24: "next slice".

**Built evidence (2026-09-24):**

- **Failing tests first.** `scripts/test/test_framework_sync.py` (9) drives a real adopted tenant
  through a real sync and commits through its real hooks; seven of seven failed before
  `runtime/sync.py` existed.
- **The escape is verified, not declared:** `Review: n/a: framework sync <version>` passes only
  while every gated file in the commit matches the manifest, and the hash check is now one
  function (`manifest_problems`) shared with the generated-scaffold rule rather than a second copy.
- **`agentsmith upgrade` no longer vendors into an adopted repository** — it read a package pin but
  not the adoption manifest, so it would have undone what adoption promised. Both commands read it
  now.
- **Mutation checks:** a new `framework_sync` suite, 5 mutations, all caught.
- **Tried on the real adopted TypeScript tenant** from the earlier slice: it reports nothing stale,
  because that tenant was adopted from the current framework — the honest answer, and the one the
  "second run writes nothing" test pins.

## Pass 1 — findings: 3

Each found by a mutation surviving, which is the check working.

- `test-that-cannot-fail` — **finding:** the "sync commit passes its own gates" test passed before
  the gate rule existed, because the commit was small enough for the 20-line `n/a` escape. The
  fixture's drift is now larger than that, so only the hash rule can explain the pass.
- `test-that-cannot-fail` — **finding:** "any commit may claim to be a framework sync" survived:
  the test asserted the commit was refused, and it was — by the design's scope, not by the sync
  rule. It now asserts the rule's own words, naming the file.
- `test-that-pins-a-defect` — **finding:** "a sync lists files it did not touch" survived, because
  the case the filter protects had no test: a hook edited by hand in the working tree, which sync
  restores to what the repository already committed, leaving nothing to commit and nothing to list.

## Pass 2 — findings: 1

- `denied-vs-missing` — **finding:** my first notion of "stale" was an uncommitted edit in the
  tenant, which git already shows and which sync would "fix" by reverting. Drift is the *framework*
  having moved on since the tenant took its copy, so `plan_sync` takes the framework to sync from
  and the fixture builds one that moved. Without this the command would have looked right and
  measured the wrong thing.

## Pass 3 — findings: 0

The stale set, the filter, the gate rule, the CLI and the docs.

Considered and declined:

- Refreshing the IDE hook configs and rule-file blocks in this slice. They are merged into files a
  tenant also edits, and a wrong merge there is worse than a stale block; the hooks and the
  declaration are what the gates depend on. Recorded as the next step rather than half-done.
- Rewriting the adoption design on each sync. A sync changes no scope, and a design rewritten every
  upgrade would read as a new decision each time.

**Stated limits:**

- `sync` refreshes the gate hooks, the provider declaration and (vendored tenants) the vendored
  trees; the IDE configs, the rule-file blocks and the gates workflow are not refreshed yet;
- the manifest is not signed — rewriting a file *and* its hash defeats the escape, deliberately and
  visibly, exactly as for the generated scaffold;
- a tenant still runs `sync` itself: nothing opens a pull request for it.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one hash check behind both escapes; hooks from
                                          install_gate_hooks; vendoring from upgrade
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — command-line output, read on a real tenant
Group 6 · Signal integrity            [x] checked — "nothing to do" and "refused" stay different
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_framework_sync.py (9), scripts/test/test_scaffold_review.py
                          (2 re-pinned to the shared message)
Mutation-checked:          yes — framework_sync, 5 mutations, all caught after three test fixes
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:15989e6292fb
Gates run locally:         ruff, mypy in a clean environment, the repo-tree check, the sync, scaffold,
                          adopt and gate suites, and the full pytest run
Declared gaps:             (1) IDE configs, rule blocks and the gates workflow are not refreshed yet;
                              (2) the manifest is not signed; (3) a tenant runs sync itself
```
