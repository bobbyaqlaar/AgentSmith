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

## Pass 4 — findings: 1

CI run 35962361559 refused the change, and it was right to. `mutation_check.py` reported
`tenant_adopt: STALE TARGET (2 matches, expected 1)` for "the gate's note stops naming the command
that wrote the files": this slice added the `framework sync` escape by **copying** the scaffold
escape's note, so the mutation had two places to land and could no longer prove anything.

- `one-catalog` — **finding:** the two escapes shared a hash check (`manifest_problems`) but each
  carried its own copy of the sentence that reports it, which is how Pass 3 could sign Group 1 as
  "one hash check behind both escapes" while the words a tenant reads were duplicated. Fixed:
  `vouched_note(label, gated, read)` in `scripts/process_gate.py` is the one place that sentence is
  written, and both escapes call it. The mutation target resolves to one line again, so the
  property is defended rather than merely declared.

Worth recording about *how* this was caught: the suite watches `runtime/adopt.py` and
`scripts/process_gate.py`, so it was skipped on the intervening docs-only push (run 35923740233,
named out loud, 79 mutations) and ran on the push that touched them. The narrowing deferred the
signal by one push; it did not lose it.

## Pass 5 — findings: 0

The extracted helper and its two call sites. Considered and declined:

- Re-pointing the mutation at one of the two copies, which is what the tool's message offers. It
  would make the run green and leave a second copy of the message no mutation touches.
- Giving the two escapes different wording so each target is unique. They report the same fact —
  every gated file matches the manifest — and saying it two ways would be a signal-integrity bug
  dressed up as a fix.

**Stated limits:** unchanged from Pass 3; this pass changed the gate's wording path only, and
`scripts/test/test_scaffold_review.py` still pins the message both escapes now share.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one hash check AND one sentence behind both
                                          escapes (`vouched_note`, Pass 4); hooks from
                                          install_gate_hooks; vendoring from upgrade
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — command-line output, read on a real tenant
Group 6 · Signal integrity            [x] checked — "nothing to do" and "refused" stay different
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_framework_sync.py (9), scripts/test/test_scaffold_review.py
                          (2 re-pinned to the shared message)
Mutation-checked:          yes — framework_sync (10) and tenant_adopt (20), all caught; the
                          tenant_adopt target is unique again
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:3e2fc8d5056a
Gates run locally:         ruff, mypy in a clean environment, the repo-tree check, the sync, scaffold,
                          adopt and gate suites, and the full pytest run
Declared gaps:             (1) IDE configs, rule blocks and the gates workflow are not refreshed yet;
                              (2) the manifest is not signed; (3) a tenant runs sync itself
```
