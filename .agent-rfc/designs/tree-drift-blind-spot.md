---
status: done
scope:
  - docs/DESIGN.md
  - .github/workflows/self-test.yml
  - CHANGELOG.md
---
# The tree said `workflow-templates/` held three families; it holds five

Owner, 2026-09-27: "Documents and knowledge graph updated?" — checked rather than asserted, and the
check found one thing, which then found a second.

## Problem

The knowledge graph is current: a forced rebuild produces no diff, and
`verify_system.py --check-kg` passes (467 nodes, 177 edges). The `CHANGELOG.md` covers all twenty of
this session's slices, `artifacts` passes, and `docs/validation-checklist.md`'s gates table was
regenerated from the tags.

`docs/DESIGN.md` was not current, in a place its own drift check cannot see:

1. The tree described `workflow-templates/` as *"Tenant CI/CD templates (ci-\* / cd-\* / eval-\*
   reusable workflows)"*. That omits `agentsmith-gates.yml` and `agentsmith-sync.yml` — **the two
   workflows that carry the governance**, and the subject of most of this session. A reader of the
   canonical tree would not know a tenant receives them.
2. The drift check in `.github/workflows/self-test.yml` diffs second-level entries for four
   directories — `scripts`, `runtime`, `docs`, `fixtures` — chosen in 2026-07 because the P12
   additions drifted at that depth. `workflow-templates` was never added, so nothing could have caught
   (1). The check is the reason the P12 class stopped recurring; it just never covered this directory.

## Approach

- **The tree lists the families**, not a sentence naming three of five: `agentsmith-gates.yml` and
  `agentsmith-sync.yml` by name, because a tenant's governance depends on those two specifically, and
  `ci-*`, `cd-*`, `eval-*` and `shadow-eval.yml` as the families they are.
- **`workflow-templates` joins `DEEP_DIRS`**, so the next template added to a family nobody documented
  fails CI instead of accumulating. Running the widened check immediately found a **second** gap —
  `shadow-eval.yml`, a fifth family the four globs did not cover — which is the argument for widening
  rather than for fixing (1) alone.

## Pillars

- P1 applies — this design precedes the edit; the verification is recorded in `.agent-rfc/reviews/tree-drift-blind-spot.md`.
- P2 applies — no dependency and no new file; one list in `.github/workflows/self-test.yml` gains an entry and `docs/DESIGN.md`'s tree gains six lines.
- P3 n/a — documentation and a CI check; no traced path.
- P4 applies — the check itself is the test: run before the fix it reported `workflow-templates/shadow-eval.yml` missing, and after it passes. It runs in CI as a tagged gate (`# agentsmith:gate`).
- P7 n/a — no code beyond a list literal.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the check reads `docs/DESIGN.md` and `git ls-files` as data, in `.github/workflows/self-test.yml`.
- P12 applies — no credential is read or named; the two newly documented workflows name secrets only, which `workflow-templates/agentsmith-gates.yml` already did.
- P13 applies — a check gets **wider**, never weaker: `DEEP_DIRS` gains a directory, and the globs added to the tree are families that exist rather than a wildcard that would excuse anything. `ci-*.yml` is as loose as it gets, and a file outside all five families still fails.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` was verified current by a forced `scripts/map_codebase.py` rebuild and by `scripts/verify_system.py --check-kg`, and needs no re-pin: only `docs/DESIGN.md` and a list literal in `.github/workflows/self-test.yml` change.
- P15 applies — the `DEEP_DIRS` list in `.github/workflows/self-test.yml` makes "this directory is documented" and "this directory's contents are documented" different answers; with `workflow-templates` absent from it, a sentence naming three families passed for five.
- P16 n/a — no fallback path.

## Deviations

none

## Dependencies

None added.

## Levers

- `docs-match-behaviour` — the canonical tree named three of five families in the directory it describes.
- `check-that-fires-on-everything` — a second-level check covering four directories of eleven cannot see the seventh.
- `grep-for-siblings` — widening it found `shadow-eval.yml` on the first run.
- `single-source-of-truth` — `docs/DESIGN.md` holds the only copy of the tree, which is why it has to be right.
