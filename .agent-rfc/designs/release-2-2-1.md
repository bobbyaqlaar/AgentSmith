---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 2.2.1

## Problem

v2.2.0 (2026-10-07) published `contract/evals/v1` with dataset schemas narrower than their scorers:
KYC Sentinel's hallucination dataset — `retrieved_context` as `{id, text}` documents — is
`not_gradable` whole under it, so KYC cannot move its evals onto the contract at that release. The
fix (`evals-dataset-shapes`) is on `main`'s next commit; a tenant pins a release, not a commit.

The owner asked for KYC's evals on the contract on 2026-10-07; this release is what unblocks it.

## Approach

- **2.2.1, a PATCH.** Unreleased holds one Fixed heading. The contract accepts more of what its
  scorers already read; the one refusal it adds is a `rag_poison` `expect` other than `quarantine` or
  `safe`, which the scorer misread as `safe` — no tenant has adopted v1 yet (it is a day old).
- `pyproject.toml` and `install-ai-stack.sh` declare `2.2.1`; `docs/DESIGN.md`'s header follows
  (`scripts/test/test_version_consistency.py`).
- `CHANGELOG.md`: Unreleased becomes `[2.2.1] — 2026-10-07`; the 2.2.x compatibility row stands — a
  patch adds no row — with a sentence that 2.2.1 is the release to adopt the evals contract at.
- `docs/PRODUCT_BACKLOG.md`: v2.2.1 is the latest release. `docs/PRODUCT_ARCHIVE.md`: the release.
- **The same pull request as the fix**, a second commit; then an annotated tag `v2.2.1` on the
  merged commit, pushed; `release.yml` publishes it.

## Pillars

- P1 applies — `.agent-rfc/designs/release-2-2-1.md` records the version and why it is a patch before any file changes.
- P2 n/a — no dependency changes; only the version strings.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section for the version.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-2-2-1.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md` names 2.2.1 as the release to adopt the evals contract at, and why.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag; a bad tag is deleted and re-cut before anyone pins it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the 2.2.x row says which patch a tenant adopting the evals contract needs.
