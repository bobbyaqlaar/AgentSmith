---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 2.3.0

## Problem

The security contract (C7, `security-contract`) is merged, and a tenant moves onto it only through a
release: its CI installs the provider through the setup step pinned to a tag, and its launcher comes
from a sync to that tag. KYC Sentinel's and AqlaarTeleologyStudio's moves wait on it. The owner asked
for the release on 2026-10-10.

## Approach

- **2.3.0, a MINOR.** The contract is additive: a new port, a new launcher subcommand, a new CLI
  verb; nothing a 2.2.x tenant runs stops working. Two behaviours of the harness a tenant may still
  run by path change, and the row says so: SEC-GW-001 scans the repository rather than the install it
  runs from, and SEC-TOOL-001 and SEC-AGENCY-001 hold their files to the published schemas.
- `pyproject.toml` and `install-ai-stack.sh` declare `2.3.0`; `docs/DESIGN.md`'s header follows
  (`scripts/test/test_version_consistency.py`).
- `CHANGELOG.md`: Unreleased becomes `[2.3.0] — 2026-10-10`; a 2.3.x compatibility row names what a
  tenant will notice and the pins `process-gate security` needs. `docs/DESIGN.md`'s mirror shows the
  2.3.x row.
- `docs/PRODUCT_BACKLOG.md`: v2.3.0 is the latest release; C7's tenants can move.
  `docs/PRODUCT_ARCHIVE.md`: the release.
- **Merged by rebase**, not squash — a squash folds commits into one whose scope no review names
  (`f83db05`, repaired by #49). Then an annotated tag `v2.3.0` on the merged commit, pushed;
  `release.yml` publishes it.

## Pillars

- P1 applies — `.agent-rfc/designs/release-2-3-0.md` records the version and why it is a minor before any file changes.
- P2 n/a — no dependency changes; only the version strings and records.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section for the version.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-2-3-0.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md`'s 2.3.x row names the launcher and setup-step pins `process-gate security` needs, and the harness behaviours that changed.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag; a bad tag is deleted and re-cut before anyone pins it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the 2.3.x row says what changes for a tenant still running the harness by path.
- `two-owners-two-cadences` — tenants pin the release; the row is their compatibility window.
