---
status: active
scope:
  - pyproject.toml
  - install-ai-stack.sh
---
# Release 2.0.0

## Problem

`main` carries everything since v1.3.0 (2026-08-27) under `CHANGELOG.md` › Unreleased, and
nothing that needs a release can use it: `tenant adopt`'s gates workflow checks out AgentSmith at
`v<installed version>`, and v1.3.0 predates the rule that accepts the adoption commit, so an
adopted repository's first CI run fails.

Owner decision, 2026-09-19: the release is **2.0.0**, not 1.4.0. The 18 `ai-*` shell functions
1.3.0 installed into `~/.zshrc` are no longer installed; replacing an interface people typed is
treated as breaking, even with the `ai-compat.sh` shim, and the startup version check warns
across a MAJOR boundary.

## Approach

- `pyproject.toml` and `install-ai-stack.sh` declare `2.0.0`; `docs/DESIGN.md`'s header follows,
  as `scripts/test/test_version_consistency.py` requires.
- `CHANGELOG.md`: Unreleased becomes `[2.0.0] — 2026-09-19` with a new empty Unreleased above it;
  a `2.0.x` row in the compatibility matrix naming what breaks and what does not; one Wire
  Contract row for the Dev record the portal now ingests. `docs/DESIGN.md` mirrors the current row.
- `docs/PRODUCT_BACKLOG.md`: the release is the latest; the "cut a release" row closes.
- An annotated tag `v2.0.0` on the release commit, pushed with `main`; `release.yml` builds the
  artifacts from it.

## Pillars

- P1 applies — this design records the owner's version decision before the files change, in `.agent-rfc/designs/release-2-0-0.md`.
- P2 n/a — no dependency changes; only the version strings.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together, and requires a CHANGELOG section for the version.
- P7 n/a — no code changes.
- P8 n/a — no telemetry wiring changes; the Wire Contract row documents one that already shipped.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — the release workflow signs with secrets it reads by name, unchanged, in `.github/workflows/release.yml`.
- P13 applies — the release commit goes through the same commit gate, with this design and `.agent-rfc/reviews/release-2-0-0.md`.
- P14 n/a — no fixture or baseline changes.
- P15 applies — the compatibility row says plainly what breaks and what does not, in `CHANGELOG.md`.
- P16 applies — a bad tag is deleted and re-cut before anyone pins it; `release.yml` publishes nothing a tenant installs without the tag.

## Deviations

none

## Dependencies

None added.

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the compatibility row describes the upgrade a 1.3.0 user actually faces.
