---
status: done
scope:
  - scripts/process_gate.py
  - scripts/gate_models.py
  - templates/governance.json
  - templates/agent-rules.yaml
  - scripts/test/test_gate_artifacts.py
  - scripts/test/test_gate_models.py
  - install-ai-stack.sh
  - .github/workflows/release.yml
  - scripts/cost_router.py
---
# A pointer into another document names something that document defines

## Problem

The cross-reference rule refuses a new line carrying `SPECS.md §23` or `DESIGN.md#L120`. It does <!-- xref: example -->
not see the same pointer without the `§` — `docs/PRODUCT_ARCHIVE.md 5.10` — or with a backtick <!-- xref: example -->
between the file and the number, as in `` `docs/UserManual.md` §2.3b ``. G5b found 68 of the first <!-- xref: example -->
kind by hand; five were dead. The second kind is still in the tree: `portal/README.md` sends
readers to `docs/UserManual.md` §2.3b and "Part E", and neither has existed since G5b took the <!-- xref: example -->
numbers out of the manual.

What cannot be done is refuse every number after a file name. `CHANGELOG.md` 1.1.0 names a <!-- xref: example -->
release, and `docs/PRODUCT_ARCHIVE.md 4.14` names an archive entry that will never be renumbered: <!-- xref: example -->
the archive is append-only. Those are names. The rule exists to refuse positions — numbers that
move on the next edit of the document they point into.

The owner chose, on 2026-09-18, to tell the two apart by **looking in the target** (option (a))
rather than by the shape of the number (option (b)).

## Approach

**A pointer** is a Markdown file name followed by a token with a digit in it: with `§` or `#L`
between them, or whitespace, and optionally a closing backtick, quote, `*`, `)` or `]` after the
file name. A token followed at once by `-<digit>` is a date or a range, not a pointer
(`DEVLOG.md` 2026-09-12). <!-- xref: example -->

**The verdict, for each pointer on a line a change adds:**

1. `#L…` — refused, as today. A line number is never a name.
2. **The target document is found** relative to the file the line is in, then from the repo root,
   read at the state being committed. A target this repo does not have is refused: a number into a
   document nobody can open is the least resolvable pointer there is.
3. **The target defines the token as a name**, or the pointer is refused. A name is defined by:
   - a heading containing the token as a whole word;
   - the first word of a table row's first cell;
   - the first word of a list item's bold lead (`- **2.3 HITL blob…**`).

   Fenced code blocks are skipped: a `# comment` inside one is not a heading.
4. **A bare number that opens a heading, row or list item is a name only in an append-only
   document.** Digits and dots, with an optional letter suffix or a part's letter (`5.10`, `2.3b`, `E.1`), in that first
   place label a numbered heading or row — in a living document, a position, which is what the
   rule exists to refuse. In an append-only record, the same number never moves. A number inside
   a heading's words (`## Python 3.11 support`) is part of its name either way. The registry says which types are append-only: `append_only: true` on `archive`,
   `review_log` and `changelog` in `templates/agent-rules.yaml`, compiled into `templates/governance.json`. The gate does not guess.

   Without this, pure option (a) passes `docs/uae-regulatory.md` §2: that document numbers its <!-- xref: example -->
   headings (`## 2. Strict Bias and Fairness Enforcement`), and a status table repeats `2` in a first
   cell. That document is living; the number is a position.

`<!-- xref: example -->` still exempts a line that must show a bad pointer.

**Where it runs:** the lines a change adds, under `artifacts: report|enforce` — at commit, and
in CI and the pre-push sweep. Those two skipped any commit that touched no gated path, and most
documents are ungated, so a pointer in a docs-only commit that bypassed the commit gate reached
`main` unread. `check_commits` now reads the pointers of such a commit too. Both tenants that carry the gate have `artifacts: off`, so this
changes nothing for them until they migrate — and a repo still numbering its headings cannot pass
a positional pointer under rule 4.

**The one-off sweep.** The rule sees added lines only, so the existing pointers are swept once,
with the new function over every tracked file, in this change. Dead ones found by the prototype:

- `portal/README.md` — `docs/UserManual.md` §2.3b and Part E; <!-- xref: example -->
- `install-ai-stack.sh` — `docs/PRODUCT_ARCHIVE.md P0.5`, `.github/workflows/release.yml` — <!-- xref: example -->
  `4.13`, `scripts/cost_router.py` — `4.4`: entries that exist nowhere in the archive; <!-- xref: example -->
- `templates/uae-sovereign/README.md` — `docs/uae-regulatory.md` §2, a position; <!-- xref: example -->
- `docs/PRODUCT_BACKLOG.md` — a review record's `§ G3`, a section that record does not have.

Each becomes the heading it meant, or goes, keeping the explanation around it. Left as they are,
and recorded in the review: records under `.agent-rfc/` (history, true when written), test
fixtures that hold legacy text byte for byte, and test strings that are deliberate examples.

**Not done here:** a pointer by heading name (`docs/DESIGN.md › Section`) that dies when the
heading is renamed. It carries no digit, so this rule does not read it; catching it needs a
whole-tree check on the target side, which is its own change — a backlog item.

## Pillars

- P1 applies — this note precedes the code; the option the owner chose is recorded in `.agent-rfc/designs/xref-names.md`.
- P2 n/a — no dependency added: the change is regular expressions and the existing Pydantic registry model.
- P3 n/a — the gate emits no spans of its own for a single rule; the commit and CI gates already report through their existing paths.
- P4 applies — failing tests first in `scripts/test/test_gate_artifacts.py`, one per verdict rule, plus the registry field in `scripts/test/test_gate_models.py`.
- P7 applies — the registry field is declared on the Pydantic `Artifact` model in `scripts/gate_models.py`, not read as a loose dict key.
- P8 n/a — no telemetry wiring.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 applies — the target document is text this code did not write; it is read as data and only searched, by `cross_reference_problems`.
- P12 n/a — no credentials.
- P13 applies — the rule is widened, not loosened: every pointer refused today is still refused unless its target defines the token, and a bare number counts only where `append_only` in `templates/governance.json` says it cannot move.
- P14 applies — the fixture documents in `scripts/test/test_gate_artifacts.py` are written by each test, so the verdict is pinned against known targets.
- P15 applies — "not in this repo", "a line number" and "not a name that document defines" are three different messages from `cross_reference_problems`.
- P16 applies — an unreadable registry makes every document living, which is the stricter reading; `cross_reference_problems` never passes a pointer because something failed to load.

## Deviations

none

## Dependencies

None added.

## Levers

- `guards-must-be-able-to-fail` — each verdict rule has a test that fails the commit.
- `test-that-cannot-fail` — the positive controls: a version, an archive ID and a list-item ID pass, so a rule that refused everything would fail tests too.
- `ambiguous-signals` — a number is a name or a position depending on the document it names; the registry says which, instead of the number's shape.
- `single-source-of-truth` — which document types are append-only lives in the registry, beside the note that already said so in prose.
- `grep-for-siblings` — the sweep runs the new function over every tracked file, not only the Markdown the old rule was written for.
- `docs-match-behaviour` — `docs/process-gates.md` describes the rule as it now runs.
- `declared-vs-enforced` — the heading-name pointer the rule does not read is written down as a gap, not implied covered.
