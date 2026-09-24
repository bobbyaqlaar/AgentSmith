# Review — a tenant is told when it is behind, as a pull request

Design: `.agent-rfc/designs/sync-pull-request.md`, fifth slice of
`.agent-rfc/designs/governance-providers.md`. Owner, 2026-09-24: "next slice".

**Built evidence (2026-09-24):**

- **Failing tests first.** `scripts/test/test_sync_workflow.py` (8) reads the workflow as data —
  CI cannot be run from here — and failed on the missing template; the adopt and sync suites gained
  a case each and failed before the constant existed.
- **It proposes, never pushes:** the tests assert `gh pr create`/`gh pr edit`, one fixed branch, and
  that nothing pushes to the default branch.
- **The commit it writes is the one the gate accepts** — `Review: n/a: framework sync <tag>` with
  the design trailer — so the proposal is judged by hash in the tenant's own CI, like any other
  sync commit.
- **It is framework-owned**: `tenant adopt` writes it and `agentsmith sync` refreshes it, proven by
  `test_adopt_writes_the_sync_workflow_so_a_tenant_hears_about_upgrades` and
  `test_the_sync_workflow_is_refreshed_like_everything_else_the_framework_owns`.

## Pass 1 — findings: 1

- `test-the-contract` — **finding:** my first version of the workflow test imported `_shared_files`
  and asserted a constant, which proves nothing about what the workflow does. The coverage moved
  to where the fixtures are — adopt writes it, sync refreshes it — and this file now reads the
  workflow as data and asserts its behaviour: the schedule, the proposal, the trailers, the single
  branch, and that "nothing to sync" ends the run.

## Pass 2 — findings: 0

The workflow, the two wiring changes and the docs. Considered and declined:

- Pushing straight to the default branch when the tenant is behind. The framework would be writing
  to a repository nobody asked it to write to; a pull request is the same information and leaves
  the decision where it belongs.
- Pinning the sync workflow to the adopted release, as the gates workflow is pinned. It exists to
  notice a *new* release, so it follows the latest one; the gates workflow stays pinned, and the
  sync proposal is what moves it.
- Failing the run when Actions may not open pull requests. It says which setting to change and
  leaves the run green: a scheduled job that goes red for a permission a person must grant teaches
  people to ignore it.

**Stated limits:**

- **it has never run on GitHub** — no tenant of ours has the workflow yet, so the evidence here is
  the workflow read as data, not a green run. The first adopted repository will prove it;
- the release lookup and the PR need `AGENTSMITH_READ_TOKEN` and the repository setting that lets
  Actions open pull requests, both the owner's to set;
- it proposes what `sync` writes, so its blind spots are `sync`'s: `.cursor/hooks.json` is
  all-or-nothing, and the manifest is unsigned.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the workflow runs `agentsmith sync`, not a
                                          second implementation of it
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] checked — the pull request body says what moved, why it is
                                          safe to read quickly, and that closing it is an answer
Group 6 · Signal integrity            [x] checked — "nothing to sync" ends the run and says so
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_sync_workflow.py (8), scripts/test/test_framework_sync.py (+1),
                          scripts/test/test_tenant_adopt.py (+1)
Mutation-checked:          yes — framework_sync, 10 mutations, all caught
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:fae49d90bc8e
Gates run locally:         ruff, mypy in a clean environment, the sync, adopt and workflow suites,
                          and the full pytest run
Declared gaps:             (1) the workflow has never run on GitHub; (2) it needs a secret and a
                              repository setting the owner controls; (3) sync's own limits apply
```
