---
status: done
scope:
  - .github/scratch-tenants/**
  - .github/workflows/scratch-tenants.yml
  - scripts/test/**
  - .agenticframework/process-gates.json
---
# An adopted scratch tenant: the governance contracts proved in CI, at every commit

Closes the backlog item "CI does not prove the contract on any change" (found 2026-10-02, after
C1 merged).

## Problem

The five scratch tenants are built with `tenant init` and the machine's post-checkout hook — the
vendored path. None has a gates workflow, so the scratch-tenants run has never exercised the gate
contract's `ci` event, the provider setup action, the rules check or a commit through a contract-3
commit gate. Those paths were proved on real tenants by hand: KYC Sentinel on 2026-10-06, against
a released tag. A change to `.github/actions/setup-agentsmith`, the launcher or the providers lands
on `main` with nothing in CI that runs them as a tenant does.

## Approach

- **A sixth scratch repository, `bobbyaqlaar/agentsmith-scratch-adopted`** (public, created
  2026-10-06 at the owner's direction), built by **`tenant adopt`**, not by the hook.
- **Its source**, `.github/scratch-tenants/adopted/`, is a small existing Python project: a library
  module, its test, `requirements.txt` and **its own CI** (`ci.yml`) — the shape adopt is for, and a
  workflow adopt must leave alone. A plain library rather than a web app: a new request handler
  would need an entry on this repository's pillar allowlist, which only the owner can add to.
- **`.github/scratch-tenants/adopt.sh <target> <framework-ref>`** empties the target (keeping
  `.git`), starts an orphan `main`, copies the source in, commits it as the tenant's own code, then
  runs `agentsmith tenant adopt scratch-adopted --framework-ref <ref> --yes` and makes the adoption
  commit **exactly as adopt prints it — through the tenant's own contract-3 commit gate**, answered
  by the provider installed from this commit. Nothing bypasses a hook.
- **`--framework-ref` is this commit's SHA**, so the tenant's gates workflow and `providers.json`
  name `setup-agentsmith@<sha>`: CI installs the provider from the commit under test, not from a
  release.
- **A new job, "Scratch tenant — adopted"**, in `scratch-tenants.yml`: installs AgentSmith from this
  commit, runs `adopt.sh`, **force-pushes** `main` (owner-approved: each run re-adopts from a clean
  history, because adopt refuses a repository already under the gates), and waits for **both** the
  tenant's own CI and its "AgentSmith gates" run to succeed.
- **The workflow also rebuilds on `.githooks/**`**: an adopted tenant receives the launcher and the
  gate hooks from there, and a change to them must re-prove the tenant. `process-gates.json`'s
  CHANGELOG paths are kept equal to the paths that rebuild tenants (a test pins the two), so a change
  to the gate hooks now needs a CHANGELOG entry — right, since every tenant receives it.
- Tests: `adopt.sh` run locally into a temporary repository — the adoption commit passes the
  tenant's gate, the gates workflow and `providers.json` name the given ref, the tenant's own CI is
  untouched — and the workflow job waits on both workflow names.

**Deliberately not done:** telemetry conformance in the adopted tenant — it emits nothing, and the
runtime library is scored in this repository's own tests; adopting the existing five (they prove the
vendored path, which stays until C9).

## Pillars

- P1 applies — `.agent-rfc/designs/scratch-adopted.md` closes a recorded backlog item; the owner approved the repository and the force-push on 2026-10-06.
- P2 applies — `.github/scratch-tenants/adopt.sh` drives the real `agentsmith tenant adopt`; the job reuses the existing workflow's install and wait steps.
- P3 n/a — no traced code changes; the scratch source is a plain library.
- P4 applies — `scripts/test/test_scratch_tenants.py` builds the adopted tenant with `adopt.sh` and checks the commit went through the gate and the refs are pinned.
- P7 n/a — no framework code changes.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 n/a — no untrusted input.
- P12 applies — `.github/workflows/scratch-tenants.yml` uses `SCRATCH_TENANTS_TOKEN` by name, as the other jobs do; the owner adds the new repository to its selection.
- P13 applies — `.github/scratch-tenants/adopt.sh` makes the adoption commit through the tenant's gate rather than around it; nothing is weakened.
- P14 n/a — no fixtures or baselines.
- P15 applies — `.github/workflows/scratch-tenants.yml` fails unless both of the tenant's workflows succeed, and names which did not.
- P16 applies — `.github/scratch-tenants/adopt.sh` rebuilds from an orphan commit each run, so a broken earlier build never blocks the next.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the contracts' tenant paths run in CI at every commit, not only by hand on a released tag.
- `test-the-contract` — the gate's `ci` event, the setup action and the rules check run as a tenant runs them.
- `run-the-gates-ci-lists` — the adoption commit passes the same commit gate a developer's would.
