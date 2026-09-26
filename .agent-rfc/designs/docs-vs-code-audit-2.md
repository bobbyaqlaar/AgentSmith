---
status: done
scope:
  - README.md
  - docs/DESIGN.md
  - docs/PRODUCT_BACKLOG.md
  - scripts/test/**
  - CHANGELOG.md
---
# Two more rounds of the documentation against the code

Owner, 2026-09-26: "Since each pass found something, let's repeat the three pass exercise twice."

## Problem

Repeating the three classes from `.agent-rfc/designs/docs-vs-code-audit.md` would find nothing —
they were fixed. So each round takes classes not yet tried, or the exercise is theatre. Five new
classes were prepared; the owner's stopping rule (a pass finding nothing before the third ends the
round) fired in both rounds, so four ran.

**Round 2 — environment variables.** Clean. Both directions are already tested, deliberately loosely
("any tracked .md counts"), and neither canonical table claims to be exhaustive, so "absent from the
table" is not falsifiable. Three documented effects were checked against the code and hold.

**Round 3 — parseable examples, then cross-document consistency.** Examples are clean: 13 JSON, 16
YAML and 147 bash blocks parse; the six Python failures are `await`/`return` fragments shown outside
their function, which is the normal idiom.

Cross-document consistency was not clean, and it is the finding worth the exercise:

1. **`docs/DESIGN.md`'s pillar section was titled "Ten Operational Pillars" and documented
   fourteen**, with prose in two more places calling them "the Ten Pillars", and `README.md` pointing
   at the section by that stale title while calling them "The Fourteen Pillars".
2. **P15 (Ambiguous Signals) and P16 (Recovery Paths) are answered in every design and were
   specified in neither canonical document.** They existed only in `templates/agent-rules.yaml` and
   `templates/governance.json` — the machine-readable registry. A contributor reads `README.md` and
   `docs/DESIGN.md`, writes a design, and the gate rejects it for two pillars they have never seen.
   Going public makes that a stranger's first experience of the framework.

The counts were all wrong in a way worth naming: the registry defines **16** pillars; **14** are
design questions (`check` contains `design`); P5 and P6 are `check: [review]`. README listed fourteen
— but a *different* fourteen, including P5 and P6 and omitting P15 and P16.

## Approach

- **`docs/DESIGN.md`**: the heading loses its count (it was "Ten" for four pillars longer than it was
  true), states the 16/14 split and where the authority is, and gains `### Pillar 15` and
  `### Pillar 16` sections written to the same shape as the other fourteen.
- **`README.md`**: "The Sixteen Pillars", both missing entries added, and the pointer repaired.
- **`docs/PRODUCT_BACKLOG.md`**: the article plan said "Ten Pillars" — it is a plan for a public
  article, so it is corrected rather than left.
- **Pinned, not just fixed.** The pillar list is a second copy of the registry across a boundary
  that cannot be merged, so three tests in `scripts/test/test_design_and_validation_docs.py` parse
  both sides: every registry pillar has a `docs/DESIGN.md` section, every design-question pillar is
  in README's list, and no document states a count the registry contradicts.

## Pillars

- P1 applies — this design precedes the edits; the passes are recorded in `.agent-rfc/reviews/docs-vs-code-audit-2.md`.
- P2 applies — no dependency; the new tests read `templates/governance.json`, the registry the gate already reads.
- P3 n/a — documentation and tests; no execution path.
- P4 applies — three tests in `scripts/test/test_design_and_validation_docs.py`, each confirmed failing against a reverted fix.
- P7 n/a — no typed boundary; the tests follow the file's existing shape.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the tests read this repository's own `README.md`, `docs/DESIGN.md` and `templates/governance.json` as data, never as instructions.
- P12 applies — no credential is read or written. `docs/DESIGN.md`'s new `### Pillar 12 — Secrets and Credentials` neighbour sections name no value, and the tests in `scripts/test/test_design_and_validation_docs.py` read only `templates/governance.json` and two markdown files.
- P13 applies — no check is weakened and three are added. `test_no_document_states_a_stale_pillar_count` asserts against the wrong spellings rather than for the right one, so a count cannot go stale silently again.
- P14 n/a — no fixture or baseline; no code the knowledge graph indexes changed.
- P15 applies — its own subject: a pass that finds nothing is recorded as a zero with what it covered, never as silence, in `.agent-rfc/reviews/docs-vs-code-audit-2.md`.
- P16 n/a — no fallback path added.

## Deviations

none

## Dependencies

None added.

## Levers

- `docs-match-behaviour` — two canonical documents disagreed with the registry the gate reads.
- `pin-unremovable-duplicates` — the pillar list is prose restating JSON; pinned by parsing both.
- `declared-vs-enforced` — two pillars enforced on every design with no specification to read.
- `check-that-fires-on-everything` — each pass prints what it parsed, because a detector returning nothing is a broken query until proven otherwise.
- `ambiguous-signals` — a count in a heading is a second copy of `len(pillars)` and goes stale silently.
