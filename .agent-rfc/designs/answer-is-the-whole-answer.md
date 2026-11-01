---
status: done
scope:
  - scripts/gate_models.py
  - scripts/test/test_gate_models.py
  - scripts/test/test_gate_pillars.py
  - scripts/mutation_check.py
---
# A pillar answer is the whole answer, not its first line

## Problem

`scripts/gate_models.py::check_evidence` and `check_pillars` both iterate
`section.splitlines()` and judge each pillar answer from the **first line alone**.
Every answer long enough to wrap is judged on a fragment of itself.

Measured today, on `.agent-rfc/designs/curated-mutations-for-todays-gates.md`:
**five of fourteen answers were refused while naming real, tracked paths one line
down.** P1, P4, P11, P13 and P15 each got

> `P4 applies — the answer names nothing that can be looked up`

against an answer whose second line read ``the 11 new entries in
`scripts/mutation_check.py` must fail at least one named test``. The fix the gate
forced was to move the backticks up a line — which taught nothing, changed no
evidence, and cost two blocked commits.

The same defect sits in `check_pillars`, in two more places:

- **`gap`** requires a backlog id matching `\b[A-Z][A-Z0-9]*-\d+\b` in `detail`,
  and `detail` is first-line-only. `- P15 gap —` with `PB-402 covers it` on the
  next line is refused for naming no id.
- **`applies` / `n/a`** require a non-empty `detail`. A bullet carrying its
  verdict on line 1 and its reason on line 2 reads as *"the answer says why"*
  unanswered.

Nobody hit those two yet because the convention has been to put the id and the
reason on the first line. That is a convention holding a check up, not a check.

This is a `check-that-fires-on-everything` inversion: the control fires on
answers that satisfy it. A gate that refuses correct work teaches people to
reshape prose until it passes, which is exactly the "sixteen lines of it applies"
form the evidence rule exists to prevent.

## Approach

One helper, `_answers(section)`, yielding `(match, block)` for each parsed
answer, where `block` is the answer's own line plus every following line up to —
not including — the next line that is **meant as an answer** (`_MEANT_AS_ANSWER`),
the next markdown heading, or the end of the section.

`check_pillars` then takes `detail` from the block, and `check_evidence` takes its
backtick tokens from the block.

**Why answers delimit answers, not bullets.** A nested sub-bullet under an answer
is part of that answer — refusing it would reintroduce the same bug one level
down — so a bare `- ` cannot end a block. Delimiting on `_MEANT_AS_ANSWER`
instead means no answer can ever be credited with the token of a *neighbouring*
answer, which is the one way this change could make the check weaker. There is a
test for exactly that.

**`pillar_kinds` stays per-line, deliberately.** It reads only `verdict`, which
`_ANSWER` can only match on the line that opens the answer, so routing it through
blocks would add a traversal and change no result. Stated here so the asymmetry
reads as a decision rather than a missed call site.

**A third sibling, found in Pass 2 and fixed here.** Sweeping `splitlines()` across
`scripts/gate_models.py` turned up `parse_deviations`, which reads a deviation
entry a line at a time: an `approval:` id that wrapped was invisible, and the
entry was refused for having no owner approval when it had one. Same defect, same
file, same severity — a false refusal on a record the owner had approved. So the
block reader is `_blocks(section, opens)`, parameterised by what opens an entry,
and `_answers` and `parse_deviations` both sit on it. `_OPENS_DEVIATION` matches a
withdrawn entry too (`- ~~D2 …~~`), so a struck-through entry still ends the live
one above it instead of being swallowed into it with its approval id.

Curated mutations go in a new suite `record_blocks`, because no suite owns
`scripts/test/test_gate_models.py` or `scripts/test/test_gate_pillars.py` today
(`rules_contract` and `evals_contract` mutate `scripts/gate_models.py` for
unrelated properties and keep theirs).

## Pillars

- P1 applies — this design; `scripts/gate_models.py` is the one non-test file it
  changes, and the scope names the three test files and the catalogue.
- P2 applies — searched first: `grep -n _ANSWER scripts/gate_models.py` found
  three per-line loops (`pillar_kinds`, `check_pillars`, `check_evidence`), which
  is how the two unreported siblings in `check_pillars` turned up. Minimal change
  is one helper and two call sites, not a parser. No dependency added; no new
  module, so no knowledge-graph node.
- P3 n/a — adds no command, route, job, hook or model call. The gate's existing
  spans are unchanged.
- P4 applies — `scripts/test/test_gate_models.py` gains 13 unit cases and
  `scripts/test/test_gate_pillars.py` one end-to-end commit; 5 of the 14 fail
  against the old code. The new `record_blocks` suite in
  `scripts/mutation_check.py` mutates the block helper so a later edit cannot
  collapse it back to one line unnoticed.
- P7 applies — Python, `from __future__ import annotations` already at the top of
  `scripts/gate_models.py`; a generator returning tuples, no new class, no `Any`.
- P8 n/a — emits no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — calls no LLM.
- P11 applies — `scripts/gate_models.py` reads `.agent-rfc` records, which are
  author-written, not untrusted input, and this change widens how much of one is
  read. It stays data: tokens are matched against what the commit tracks and a
  record cannot resolve its own token, which
  `test_a_token_the_record_itself_invents_does_not_vouch_for_it` already pins.
- P12 n/a — touches no credential.
- P13 applies — `scripts/gate_models.py` holds a check that gets **more
  permissive**, and that is the fix: it refused answers that satisfied it. What is
  genuinely new is that more text counts as "the answer", so unrelated prose under
  an answer carrying a resolving backtick would now satisfy it. The token must
  still resolve against the commit's tracked files, so the bar per token is
  unchanged; only the span of text searched moves. Declared in the CHANGELOG, and
  the cross-crediting case is a test rather than a claim.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned for the
  two new rfc documents. No golden or baseline changes; every record already in
  the repository still parses the same way, because a first line that satisfied
  the old check still satisfies the new one.
- P15 applies — `scripts/gate_models.py` keeps both messages it already had, and
  they get truer: "names nothing that can be looked up" now means the whole
  answer names nothing. The refusal still quotes the tokens it rejected.
- P16 applies — `scripts/gate_models.py` has no fallback to add: `_answers` is a
  pure read over text already in memory, and a section with no parseable answer
  yields nothing, which `check_pillars` already reports as an unanswered pillar.

## Deviations

none

## Dependencies

none

## Levers

- `check-that-fires-on-everything` — the defect: the control fired on answers
  that satisfied it, five times in one record.
- `grep-for-siblings` — twice. Grepping `_ANSWER` found the same per-line read in
  `check_pillars`, in two more rules; sweeping `splitlines()` in Pass 2 found a
  third in `parse_deviations`. Neither was reported by anyone.
- `ambiguous-signals` — "names nothing that can be looked up" was false, and a
  false refusal reads exactly like a true one.
- `guards-must-be-able-to-fail` — the point of the slice is a looser check, so
  the cross-crediting case gets a test that must be able to fail.
- `gate-integrity` — a check getting more permissive is the case to justify, not
  to slip through. P13 says what moves and what does not.
- `test-that-pins-a-defect` — one test per refusal observed today, plus one for
  each sibling that nobody has hit.
