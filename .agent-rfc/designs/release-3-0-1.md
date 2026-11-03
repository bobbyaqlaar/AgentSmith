---
status: active
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 3.0.1

## Problem

v3.0.0 fails a stranger: installed as the README says, the first commit is refused. The fix is merged
(`release-install-path`, #74), and a user only gets it from a release. The launch needs it first, with the
AGPL notices (#76). The owner asked for this release on 2026-11-03.

## Approach

- **3.0.1, a PATCH.** No contract, wire or `contract/*` surface changes. The Unreleased section is the install
  fix, gate fixes, notices and test machinery. `AgentKnowledgeGraph.remove_file` becoming `remove_node` is a
  rename inside the graph script, which no port exposes and neither tenant imports.
- **One thing a reader can notice, and the 3.0.x row says it:** the release no longer carries the `scripts`,
  `githooks`, `workflow-templates`, `templates` or `requirements.lock` assets. Only a saved 3.0.0 installer
  script looks for them, because it downloads from `latest`. The documented one-liner fetches the current installer.
- `pyproject.toml` and `install-ai-stack.sh` declare `3.0.1`. `docs/DESIGN.md`'s header and mirror row follow
  (`scripts/test/test_version_consistency.py`), and so does the README's pinned setup step.
- `CHANGELOG.md`: Unreleased becomes `[3.0.1] — 2026-11-04`. No wire change.
- **Records:** `docs/PRODUCT_BACKLOG.md` and `docs/PRODUCT_ARCHIVE.md`; the two designs this ships are marked done.
- **Merged by rebase.** Then an annotated tag `v3.0.1` on the merged commit, pushed. `release.yml` publishes it, and
  its new `verify-published-release` job runs the Quick Start on the real URL, which is the check the 3.0.0 release lacked.

## Pillars

- P1 applies — `.agent-rfc/designs/release-3-0-1.md` records the version and why it is a patch before any file changes.
- P2 n/a — no dependency changes; only version strings and records.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes; the Wire Contract table gains no row.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-3-0-1.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md`'s 3.0.x row names the removed assets and who can notice them.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag, and its verify job shows a broken release at once; a bad release is followed by a corrected tag.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the row's claim about removed assets was checked against the release workflow.
- `when-the-fallback-fails` — the release is verified from the URL a stranger uses, after publishing.
