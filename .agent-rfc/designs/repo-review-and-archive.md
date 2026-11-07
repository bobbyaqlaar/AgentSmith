---
status: active
scope:
  - docker-compose.yml
  - portal/.env.example
  - portal/app/api/sync/history/route.ts
  - templates/in-app-widget/README.md
  - examples/oil-price-agent/check_model_ids.py
  - archive/**
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Review the repository, and archive what nothing uses

## Problem

The owner asked, on 7 Nov before the launch announcement, for up to four review passes over the repository against
`docs/design-review-checklist.md` and `docs/validation-checklist.md`, including whether the documents still match the
code, and then for every file no phase or function needs to move to an archive that can be deleted once the system
is shown to work without it. An earlier deletion (`judge.py`) removed a file something still used, so "looks unused"
is not evidence.

## Approach

- **Review passes, mechanical first.** Every backticked path and relative link in the live documents against the tree;
  every documented `agentsmith` command against the CLI; every file deleted in history against live mentions; every
  file against what refers to it. Records (`CHANGELOG.md`, `docs/PRODUCT_ARCHIVE.md`, `docs/REVIEW_LOG.md`,
  `.agent-rfc/`) say what was true then and are not edited.
- **A file is archived only if nothing reaches it:** no import, no workflow, installer, template, config, test or
  CLI reference, no directory a tool reads whole (the Helm chart, the scratch-tenant apps, the IDE payload fixtures),
  and no live document telling a reader to use it. Two files meet that: `examples/oil-price-agent/check_model_ids.py`
  (a one-off model-ID probe for the archived demo repository, named by nothing) and `assets/LogoAqlaar-Transparent.png`
  (the source the portal's `portal/assets/brand/aqlaar.png` was cut from; nothing reads it).
- **`archive/` at the root, by `git mv`,** so history follows the file and restoring it is one move. It is outside the
  gated paths and holds no Markdown, so the artifacts gate has no stray to report. `docs/DESIGN.md`'s tree names it.
  Deleting it is the owner's call after the end-to-end check passes without it.
- Findings are fixed in the documents they are in; the portal route's change is its header comment only.

## Pillars

- P1 applies — `.agent-rfc/designs/repo-review-and-archive.md` states what qualifies a file for the archive before any moves.
- P2 n/a — no dependency or code path changes.
- P3 n/a — no traced code changes; `portal/app/api/sync/history/route.ts` changes in a comment.
- P4 applies — `scripts/test/test_design_tree_drift.py` holds the tree with `archive/` in it; the archived files had no test.
- P7 n/a — no stack rule changes.
- P8 n/a — no telemetry changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — no untrusted content.
- P12 n/a — no secrets.
- P13 n/a — no gate changes.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` follows the moved file.
- P15 n/a — no signal is read.
- P16 applies — `archive/` keeps each file with its history, so restoring it is a `git mv` back.

## Deviations

none

## Dependencies

none

## Levers

- `docs-match-behaviour` — the documents are read against the code they describe.
- `no-redundant-artifacts` — a file nothing reaches is archived, not kept.
- `grep-for-siblings` — each document finding is searched for in the other live documents.
- `implemented-not-invoked` — a file counts as used only with a real caller.
