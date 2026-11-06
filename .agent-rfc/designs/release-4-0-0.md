---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - contract/intake/v1/record.schema.json
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 4.0.0

## Problem

The package rename (`package-agentsmith`, #80) is merged and reaches nobody until it is released, and the public launch
fixes the name. The owner asked for the rename and the two-stage launch on 2026-11-03.

## Approach

- **4.0.0, a MAJOR.** `from runtime.X` stops working, with no shim. No wire value changes: the OpenTelemetry scope
  `agentsmith.runtime` stays, and the hooks differ only in a comment. One `contract/` edit, in a description: the path the
  rename missed in `contract/intake/v1/record.schema.json`; nothing a tenant validates against changes.
- **The one break that is not an import, and the row says it.** `agentsmith-sync.yml` follows the latest release, not the
  pin. A 3.x copy runs `python3 -P -m runtime.cli`, so from 4.0.0 on it fails and cannot repair itself. Run by hand,
  `agentsmith sync` rewrites it and moves the pin, tried on a repository adopted with the v3.0.1 tree.
- **Nobody known is exposed:** KYC Sentinel and Tenant B do not carry that workflow, the scratch tenants are on the new line, and
  the repository has no forks. So no shim for it: the row tells an unknown adopter what to run.
- **The gap this exposed goes on the backlog:** the scratch tenants are rebuilt from HEAD, so nothing moves a tenant from an
  earlier release forward.
- `pyproject.toml` and `install-ai-stack.sh` declare `4.0.0`; `docs/DESIGN.md`'s header and mirror row and the README's
  pinned setup step follow. `CHANGELOG.md`: Unreleased becomes `[4.0.0] — 2026-11-05`, with the false "keeps working until
  it moves" sentence corrected.
- **Records:** `docs/PRODUCT_BACKLOG.md` and `docs/PRODUCT_ARCHIVE.md`; the designs this ships are marked done.
- **Merged by rebase.** Then an annotated tag `v4.0.0` on the merged commit, pushed; `release.yml` publishes and runs the
  Quick Start on the real URL.

## Pillars

- P1 applies — `.agent-rfc/designs/release-4-0-0.md` records the version and why it is a major before any file changes.
- P2 n/a — no dependency changes; only version strings and records.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes; the Wire Contract table gains no row.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-4-0-0.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md`'s 4.0.x row names the sync workflow's failure and the command that repairs it.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag, and its verify job shows a broken release at once; a tenant that has not moved stays on its pinned 3.x release.

## Deviations

none

## Dependencies

none

## Levers

- `two-owners-two-cadences` — what a tenant already holds meets the new release; the sync workflow is where it broke.
- `docs-match-behaviour` — the row's claims were run against a repository adopted at v3.0.1.
- `when-the-fallback-fails` — the sync workflow cannot repair itself, so the row names the manual path, which was run.
