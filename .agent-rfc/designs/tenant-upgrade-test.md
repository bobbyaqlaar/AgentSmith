---
status: active
scope:
  - agentsmith/sync.py
  - agentsmith/adopt.py
  - scripts/check_tenant_upgrade.sh
  - scripts/test/test_framework_sync.py
  - .github/workflows/self-test.yml
---
# A tenant on the last release upgrades to this commit

## Problem

Scratch tenants are rebuilt from HEAD, so they pass while what a real tenant already holds breaks. Nothing tests moving forward. A prototype, a tenant made with `v4.0.1` and then synced from this commit, found four defects:

1. **`sync` can lower a tenant's pin.** It writes the running version into `providers.json`, and `framework_version()` trusts an installed package record over the code. A stale record moved a pin from `v4.0.1` to `v3.0.0`, silently.
2. **`sync` drops what `tenant init` declared.** It re-renders `providers.json` without `new_repository`, losing the `not_gradable` and `no_verdict` warnings and the telemetry `emitter`. A healthy new tenant's evals go red on its first sync, and `SEC-PII-002` with them.
3. **`sync` adds records without redrawing the graph.** The design it writes is a graph node, so the tenant's CI `kg check` fails on the sync pull request.
4. **`tenant adopt` draws the graph before writing its records,** so an adopted repository's graph is stale from its first commit.

## Approach

`scripts/check_tenant_upgrade.sh` does what a tenant does: exports the last release and this commit with `git archive`, builds the environment the sync workflow builds from `scripts/requirements-gate.txt`, makes a tenant with the old release both ways (`tenant init`, `tenant adopt`), runs the new `sync`, commits with the workflow's own trailers through the tenant's gates, and checks the ports. It also confirms the profile does not reach a tenant that did not ask for it, and that `compliance enable` works afterwards. Self-Test runs it as a gate.

The four fixes:

- `plan_sync` refuses to move a pin to an older release. It compares only released versions of AgentSmith's own setup action, so a branch ref or another provider is left alone.
- `_shared_files` carries the tenant's `not_gradable`, `no_verdict` and `emitter` into the re-render. `with_profile_ports` still strips the warnings on a profile, because it runs after.
- `sync` redraws the graph when it wrote anything.
- `tenant adopt` draws the graph after its records, then rewrites the manifest so the graph's hash is right.

`framework_version()` is unchanged. Preferring an installed record is how a real install reports itself, and the refusal covers every cause of a lower number.

## Pillars

- P1 applies — `.agent-rfc/designs/tenant-upgrade-test.md` is the plan; `docs/PRODUCT_BACKLOG.md` raised it.
- P2 applies — `scripts/check_release_install.sh` is the shape the new script copies; no new dependency.
- P3 n/a — a CI script and a CLI step; `agentsmith/sync.py` opens no span today and this adds no model or tool call.
- P4 applies — `scripts/test/test_framework_sync.py` pins each fix; each is mutation-checked by hand, and the script is shown to fail with each fix removed.
- P7 applies — `agentsmith/sync.py` reads the declaration with `json` and treats anything malformed as not comparable; `scripts/gate_models.py` is unchanged.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — `agentsmith/sync.py` parses a version from a tenant's file with an anchored pattern, and nothing from it is executed.
- P12 n/a — no secrets; the script runs with an empty `HOME`.
- P13 applies — `.github/workflows/self-test.yml` adds a gate; `agentsmith/sync.py` still leaves a file a tenant edited alone.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated for this change.
- P15 applies — `scripts/check_tenant_upgrade.sh` treats a crash as a failure, and tells an expected red scaffold result from a provider that could not answer.
- P16 applies — `CHANGELOG.md` names the change; `agentsmith sync` writes no schema and a tenant reverts a sync by not merging it.

## Deviations

none

## Dependencies

none

## Levers

- `implemented-not-invoked` — the upgrade path itself is now run.
- `failure-is-not-a-result` — a crash in any port fails the check.
- `grep-for-siblings` — `tenant adopt` and `sync` both draw the graph; both are fixed.
- `test-that-cannot-fail` — each fix is removed by hand to show its test and the script fail.
