---
status: active
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
  - .github/actions/install-python-deps/action.yml
---
# Release 3.0.0

## Problem

C9 (`vendoring-retired`) is merged: #54, with two fixes the scratch tenants found, #55 and #56. A
tenant takes the provider from a tag, and the ports C9 added are only in a release:
- `kg check`;
- `evals run --fail-below`;
- composite actions referenced at the provider.

OTS's and KYC Sentinel's moves wait on it. The owner chose a MAJOR on 2026-10-13 and asked for the
release on 2026-10-14.

## Approach

- **3.0.0, a MAJOR.** It removes surfaces a 2.x tenant or machine can reach:
  - the machine-wide git hooks, and the installer arming them;
  - `agentsmith upgrade` and `ai-stack-upgrade`;
  - vendoring into a repository, and `sync` refreshing a copy;
  - the launcher running a tenant's copy of the gate;
  - two workflow templates;
  - two release assets;
  - the Enterprise Pack's hook bundle.

  The 3.0.x row names each, and the order a 2.x tenant moves in.
- **Nothing a 2.x tenant runs stops at once, and the row says so.** A vendored copy keeps
  running by path until the tenant moves. `sync` names it and never deletes or refreshes it. The
  row gives the order, because two replacements exist only from 3.0.0 (checked against OTS's and
  KYC's workflows on 2026-10-14):
  1. re-run the installer on each machine;
  2. pin the setup step and actions `@v3.0.0`, and `agentsmith sync` for the 3.0.0 launcher;
  3. swap each by-path step for its port;
  4. delete what `verify_system --governed` names.
- **What a tenant will notice without moving:**
  - The commit guardrails are on by default in every repository's gate (`commit_guardrails`), not
    only where the machine hooks were armed.
  - A clone made before 3.0.0 keeps the machine hooks git copied into `.git/hooks`.
  - A 2.x installer script run outside a checkout fetches the latest release's assets, which no
    longer include `hooks.tar.gz` or `github-actions.tar.gz`. It reports both, an error and a
    warning, and carries on (its `error` does not exit). The fix is the 3.0.0 installer, which the
    documented one-liner fetches.
- `pyproject.toml` and `install-ai-stack.sh` declare `3.0.0`. `docs/DESIGN.md`'s header and mirror
  row follow (`scripts/test/test_version_consistency.py`).
- `CHANGELOG.md`: Unreleased becomes `[3.0.0] — 2026-10-14`, with a 3.0.x row. No wire change.
- **Records:**
  - `docs/PRODUCT_BACKLOG.md`: v3.0.0 is the latest release, and C9's tenants can move.
  - `docs/PRODUCT_ARCHIVE.md`: the release.
  - The C9 design is marked done.
  - The governance-contracts design stays active until OTS and KYC have moved.
- **Merged by rebase.** Then an annotated tag `v3.0.0` on the merged commit, pushed;
  `release.yml` publishes it.

## Pillars

- P1 applies — `.agent-rfc/designs/release-3-0-0.md` records the version and why it is a major before any file changes.
- P2 n/a — no dependency changes; only the version strings and records.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section for the version.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes; the Wire Contract table gains no row.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-3-0-0.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md`'s 3.0.x row names what a 2.x tenant and machine will notice, and the order to move in.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag; a bad tag is deleted and re-cut before anyone pins it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the 3.0.x row says what stops, what keeps running stale, and the order a tenant moves in, checked against the two real tenants' workflows.
- `two-owners-two-cadences` — tenants pin the release on their own schedule; the row is their migration path.
