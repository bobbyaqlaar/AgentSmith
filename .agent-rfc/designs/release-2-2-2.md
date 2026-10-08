---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 2.2.2

## Problem

`main` carries `env-file-credentials` (merged 2026-10-07) under Unreleased: a credential a
repository's `.env` declares now wins over the same variable exported in the shell, said by name,
and `agentsmith doctor` reports credentials exported in shell profiles. It reaches a developer's
machine and a tenant's scripts only through a release. The owner asked for it on 2026-10-08.

## Approach

- **2.2.2, a PATCH.** Unreleased holds one Changed heading. It makes credentials follow the
  precedence `runtime/config.py` already documents for every other setting (`.env` above the
  ambient shell); nothing changes unless a shell export disagrees with a repository's `.env`, and
  `env_overrides` keeps the deliberate route. CI and deployments have no `.env`.
- `pyproject.toml` and `install-ai-stack.sh` declare `2.2.2`; `docs/DESIGN.md`'s header follows
  (`scripts/test/test_version_consistency.py`).
- `CHANGELOG.md`: Unreleased becomes `[2.2.2] — 2026-10-08`; the 2.2.x row gains what a developer
  will notice from 2.2.2 — a shell-exported key that differs from a repository's `.env` is now
  ignored there, with a warning naming it. `docs/DESIGN.md`'s mirror says the same.
- `docs/PRODUCT_BACKLOG.md`: v2.2.2 is the latest release. `docs/PRODUCT_ARCHIVE.md`: the release.
- **Through a pull request**, then an annotated tag `v2.2.2` on the merged commit, pushed;
  `release.yml` publishes it.

## Pillars

- P1 applies — `.agent-rfc/designs/release-2-2-2.md` records the version and why it is a patch before any file changes.
- P2 n/a — no dependency changes; only the version strings.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section for the version.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged; the release carries the credential-precedence fix.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-2-2-2.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md`'s 2.2.x row says what a developer will notice from 2.2.2, and how to keep the old behaviour for a key.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag; a bad tag is deleted and re-cut before anyone pins it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the 2.2.x row says what changes on a developer's machine and what does not.
