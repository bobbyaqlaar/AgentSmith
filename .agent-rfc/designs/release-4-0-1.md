---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 4.0.1

## Problem

The launch fixes are merged and reach nobody until they are released. The one that matters most is the installer:
v4.0.0's published `install-ai-stack.sh`, piped inside a checkout of AgentSmith, installs that checkout under a v4.0.0
banner. The owner moved the launch to Saturday 7 November, end of day, and the launch installs the latest release.

## Approach

- **4.0.1, a PATCH.** No import, wire value, hook interface or contract changes. One template interface tightens:
  `AgentStatus` requires `widgetScriptUrl`. A copy already in an app is unaffected, and a caller that omitted the prop was
  loading no widget, so the 4.0.x row says so rather than calling it a minor.
- **What ships:** `piped-install-source`, `kg-ignores-only-inside-the-repo`, `first-run-security-message`,
  `launch-small-fixes`, `name-no-private-tenant`, the coverage map and the README. Their designs are marked done, with
  `hook-answers-without-its-payload`, which shipped in 4.0.0 and was left active.
- `pyproject.toml` and `install-ai-stack.sh` declare `4.0.1`; `docs/DESIGN.md`'s header and the README's pinned setup step
  follow. `CHANGELOG.md`: Unreleased becomes `[4.0.1] — 2026-11-07`.
- **Records:** `docs/PRODUCT_BACKLOG.md` (current state, the new target date, step 5 ticked now KYC is on 4.0.0) and
  `docs/PRODUCT_ARCHIVE.md`.
- **Merged by rebase.** Then an annotated tag `v4.0.1` on the merged commit, pushed; `release.yml` publishes and runs the
  Quick Start on the real URL; `scripts/check_release_install.sh` is run against it.

## Pillars

- P1 applies — `.agent-rfc/designs/release-4-0-1.md` records the version and why it is a patch before any file changes.
- P2 n/a — no dependency changes; only version strings and records.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-4-0-1.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md`'s 4.0.x row names the one tightened template interface and who it can affect.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag, and its verify job shows a broken release at once; a tenant pinned to 4.0.0 stays there until it moves.

## Deviations

none

## Dependencies

none

## Levers

- `docs-match-behaviour` — the row and the records say what this release changes, and no more.
- `two-owners-two-cadences` — a tenant pinned to 4.0.0 meets this release only when it moves.
