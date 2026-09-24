---
status: active
scope:
  - workflow-templates/agentsmith-sync.yml
  - runtime/adopt.py
  - runtime/sync.py
  - scripts/test/test_sync_workflow.py
  - scripts/test/test_framework_sync.py
  - scripts/test/test_tenant_adopt.py
  - scripts/mutation_check.py
  - docs/process-gates.md
  - docs/UserManual.md
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# A tenant is told when it is behind, as a pull request

Fifth slice of `.agent-rfc/designs/governance-providers.md`. `agentsmith sync` exists and its
commit passes a tenant's gates; somebody still has to remember to run it.

## Problem

A tenant only learns it is behind when a person thinks to check. That is the same failure the gates
exist to remove — a rule nobody is reminded of is a rule most repositories do not follow — and it
is worse here, because what goes stale is the gate wiring itself. The tenants that most need the
refresh are the ones nobody is watching.

## Approach

### A scheduled workflow that proposes, never pushes

`workflow-templates/agentsmith-sync.yml`, written into a tenant beside the gates workflow:

- **weekly, and on demand** (`workflow_dispatch`);
- checks out the tenant, then AgentSmith **at its latest release** — resolved from the API rather
  than pinned, because the point is to notice a new one;
- runs `agentsmith sync --yes` from that checkout;
- if nothing changed, says so and stops;
- otherwise commits with the trailers the gate accepts — `Review: n/a: framework sync <version>` —
  on a branch, and opens a **pull request**. It never pushes to the default branch: a person
  merges, and the tenant's own gates run over the PR like any other change.

The PR body says what moved and what a reviewer should look at: the version, the files, and the
note that the commit is accepted by hash rather than by review.

### One open proposal at a time

The branch name is fixed (`agentsmith/sync`), so a second run updates the existing pull request
instead of opening another. A tenant that ignores it for a month has one PR, not four.

### What it needs from the repository

`AGENTSMITH_READ_TOKEN` — already required by the gates workflow — and permission for Actions to
open a pull request (`contents: write`, `pull-requests: write`, plus the repository setting that
allows it). Both are named in the manual, and the workflow fails with those words rather than a
permissions traceback.

### It is framework-owned

`tenant adopt` writes it, `sync` refreshes it, and the manifest vouches for it — so this workflow
keeps itself current by the same rule as everything else the framework owns.

## Pillars

- P1 applies — this design precedes the code and completes the arc in `.agent-rfc/designs/governance-providers.md`.
- P2 applies — no dependency added; the workflow uses `actions/checkout`, `gh` and `git`, which the gates workflow already uses.
- P3 n/a — no traced service path.
- P4 applies — tests first in `scripts/test/test_sync_workflow.py`: the workflow parses, proposes rather than pushes, carries the trailers the gate accepts, and stops when nothing changed.
- P7 n/a — no new typed boundary; the workflow is data the tests parse.
- P8 n/a — no telemetry.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 applies — the workflow runs the framework's own CLI over the tenant's files and opens a PR; it never executes anything the tenant repository supplies, stated in `workflow-templates/agentsmith-sync.yml`.
- P12 applies — it names `AGENTSMITH_READ_TOKEN` and `GITHUB_TOKEN` by name and writes neither into the repository, in `workflow-templates/agentsmith-sync.yml`.
- P13 applies — it proposes; the tenant's gates still judge the result, and the commit it writes is the hash-verified one (`manifest_problems` in `scripts/process_gate.py`).
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — "nothing to sync" is said out loud and ends the run; it is not the same as a run that failed (`workflow-templates/agentsmith-sync.yml`).
- P16 applies — one branch, so a repeated run updates the open proposal rather than adding another (`test_one_branch_so_a_second_run_updates_the_open_proposal`); a tenant that never merges has one PR to decide about.

## Deviations

none

## Dependencies

None added.

## Levers

- `implemented-not-invoked` — a command nobody remembers to run is a command most tenants do not run.
- `irreversible-needs-confirmation` — it proposes a pull request; merging stays a person's decision.
- `denied-vs-missing` — "nothing to sync" and "the sync failed" are different endings.
- `one-catalog` — the workflow runs `agentsmith sync`, not a second implementation of it.
- `test-the-contract` — the tests read the workflow as data and assert what it does, since CI cannot run here.
