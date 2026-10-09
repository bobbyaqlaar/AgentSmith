---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 2.2.3

## Problem

`setup-evals-provider` (the previous commit) makes the provider's CI setup step able to call a
judge. A tenant's eval job pins the setup step to a release, so the fix reaches none until one is
cut — and AqlaarTeleologyStudio's move onto the evals contract, the owner's request of 2026-10-09,
pins its eval jobs to it.

## Approach

- **2.2.3, a PATCH.** Unreleased holds one Fixed heading: the setup step installs one more package,
  already a framework dependency; nothing a 2.2.2 tenant runs changes.
- `pyproject.toml` and `install-ai-stack.sh` declare `2.2.3`; `docs/DESIGN.md`'s header follows
  (`scripts/test/test_version_consistency.py`).
- `CHANGELOG.md`: Unreleased becomes `[2.2.3] — 2026-10-09`; the 2.2.x row says an eval job that
  installs the provider through the setup step needs `@v2.2.3` or later to reach its judge.
  `docs/DESIGN.md`'s mirror says the same.
- `docs/PRODUCT_BACKLOG.md`: v2.2.3 is the latest release. `docs/PRODUCT_ARCHIVE.md`: the release.
- **The same pull request as the fix**, a second commit; then an annotated tag `v2.2.3` on the
  merged commit, pushed; `release.yml` publishes it.

## Pillars

- P1 applies — `.agent-rfc/designs/release-2-2-3.md` records the version and why it is a patch before any file changes.
- P2 n/a — no dependency changes in this commit; only the version strings.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section for the version.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-2-2-3.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md`'s 2.2.x row names the release an eval job's setup step must pin to grade.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag; a bad tag is deleted and re-cut before anyone pins it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the 2.2.x row says which setup-step pin can grade an eval.
