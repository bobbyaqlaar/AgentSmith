# Review — a pillar answer is the whole answer, not its first line

Design: `.agent-rfc/designs/answer-is-the-whole-answer.md`. Raised by the owner:
*"fix the gate's first-line-only evidence check"*, after it refused five answers
of mine that named tracked paths one line down.

**Built evidence (2026-11-01):**

- **The defect, measured.** On
  `.agent-rfc/designs/curated-mutations-for-todays-gates.md`, five of fourteen
  answers (P1, P4, P11, P13, P15) were refused with *"the answer names nothing
  that can be looked up"* while each named a real, tracked path on its second
  line. Two commits were blocked, and the fix the gate forced was to move the
  backticks up a line.
- **Two more rules with the same defect**, found by grepping `_ANSWER` and
  neither reported by anyone: `gap` read its backlog id from `detail`, and
  `applies`/`n/a` read their reason from `detail`, where `detail` was the first
  line. A third, `parse_deviations`, came out of Pass 2 below.
- **14 tests; 5 fail against the old code.** Confirmed by reverting
  `scripts/gate_models.py` and re-running: `test_a_token_on_a_continuation_line_is_found`,
  `test_a_nested_sub_bullet_counts_for_the_answer_above_it`,
  `test_a_gap_whose_backlog_id_is_on_a_continuation_line_passes`,
  `test_a_reason_on_a_continuation_line_is_a_reason` and
  `test_a_deviations_approval_id_on_a_continuation_line_is_found`. The other
  nine are controls, including the three that must pass either way.
  `scripts/test/test_gate_pillars.py::test_an_answer_whose_token_is_on_a_continuation_line_passes_the_gate`
  reproduces it through a real commit and also fails against the old code.
- **8 curated mutations in the new `record_blocks` suite, all caught — and each
  caught by the test that asserts its own property**, with the rest of the file
  passing:

  | mutant | tests that failed | rest of file |
  |---|---|---|
  | block collapses to its opening line | the 5 continuation tests | 46 pass |
  | block runs past the next entry | not-credited-with-next (answers), does-not-borrow (deviations), withdrawn-still-ends | 48 pass |
  | heading no longer ends a block | heading-ends-a-block | 50 pass |
  | any bullet ends a block | nested-sub-bullet | 50 pass |
  | answer drops its continuation | the 4 answer continuation tests | 47 pass |
  | deviation drops its continuation | approval-id-on-a-continuation-line | 50 pass |
  | withdrawn entry stops opening a block | withdrawn-still-ends-the-entry-before-it | 50 pass |
  | token dedupe removed | repeated-token-quoted-once | 50 pass |

- `ruff` clean; `scripts/test/test_gate_models.py` 38 collected cases to 52.

## Pass 1 — findings: 3

- `test-that-cannot-fail` — **my first continuation test passed against the
  unfixed code.** `test_a_token_on_a_continuation_line_is_found` put
  `` `scripts/mutation_check.py` `` on the answer's **first** line, so it proved
  nothing about blocks. Found by reverting `scripts/gate_models.py` and re-running
  the new tests: 3 of 9 failed where 4 should have. Rewritten so the first line
  names nothing, with the assertion message saying that is the point, plus a
  control asserting the same answer *without* its second line is still refused —
  so the test passes because the block was read, not because the rule stopped
  firing.
- `fixture-truth` — the `record_blocks` entry for the block-collapse mutation was
  written by a generator that put any string containing `\n` into a triple-quoted
  literal. The target line contains the *escape* `"\n"`, so the generator expanded
  it into a real newline and the entry read `STALE TARGET (0 matches, expected 1)`
  — a catalogue entry that caught nothing while sitting in the suite. Found by
  running the suite, not by reading the diff. Repaired to a single-quoted literal
  with the escape intact, and every one of the eight targets re-counted against
  the source afterwards.
- `expect-re-review` — the stop gate refused with *"`.agent-rfc/reviews/curated-mutations-for-todays-gates.md`:
  last updated before the newest change it covers"*, because this slice changes
  `scripts/mutation_check.py` again and that record covers it. Resolved by flipping
  both shipped designs to `status: done` —
  `curated-mutations-for-todays-gates` (merged as `3f9756d`, PR #71) and
  `gate-base-is-the-base-branch` (`c4ed3a5`) — which is the trailing-flip debt this
  session had been carrying since the first of them landed. Not by touching a
  record whose pass I had not run.

## Pass 2 — findings: 1

- `grep-for-siblings` — swept `splitlines()` across `scripts/gate_models.py` and
  `scripts/process_gate.py` rather than stopping at `_ANSWER`. Found a **third**
  instance of the same defect: `parse_deviations` reads a deviation entry a line
  at a time, so an `approval:` id that wrapped was invisible and the entry was
  refused for having no owner approval **when the owner had approved it** — the
  worst-consequence version of this bug, since the remedy a reader would reach for
  is to ask the owner to approve again. Fixed in the same slice: the helper became
  `_blocks(section, opens)`, parameterised by what opens an entry, and
  `parse_deviations` sits on it beside `_answers`. `_OPENS_DEVIATION` matches a
  withdrawn entry too, so `- ~~D2 …~~` still ends the live entry above it instead
  of being swallowed into it along with its approval id — four tests, one of which
  fails against the old code and three of which are controls.
  `parse_approvals` was checked and left alone: it reads JSONL, one record per
  line by format, so per-line is correct there.

## Pass 3 — findings: 0

- `check-that-fires-on-everything` — the defect, closed on all three rules. The
  control no longer fires on records that satisfy it.
- `gate-integrity` — the check gets **more permissive**, which is the case to
  justify rather than slip through, and P13 of the design says exactly what moves:
  more text counts as "the entry", while each token must still resolve against
  what the commit tracks. The bar per token is unchanged. Nothing else weakened —
  no threshold, exemption or allowlist is touched.
- `guards-must-be-able-to-fail` — the risk a looser check creates is
  cross-crediting, and it has a test on both paths (`…not_credited_with_the_next_answers_token`,
  `…does_not_borrow_the_next_entrys_approval`) plus a mutation that makes both
  fail.
- `no-copy-paste` — one `_blocks`, two callers. The alternative was a second
  block reader for deviations, which is how two parsers stop agreeing.
- `parameterize-dont-clone` — `opens` is the parameter; the only thing that
  differs between an answer and a deviation entry is what starts one.
- `ambiguous-signals` — both refusal messages are kept verbatim and are now true:
  "names nothing that can be looked up" means the whole entry names nothing, and
  the tokens it rejected are still quoted. Deduplicated so a token repeated across
  an entry's lines is quoted once, which has its own test and mutation.
- `every-line-earns-its-place` — `_answers` lost its own line walk and is now five
  lines over `_blocks`.
- `docs-match-behaviour` — `pillar_kinds` keeps reading line by line, and the
  docstring says why: it reads only `verdict`, which `_ANSWER` can match only on
  the line that opens an entry. Stated so the asymmetry reads as a decision.
- Considered and declined: ending a block on any bullet (`- `). Simpler to
  explain, and wrong — a nested sub-bullet is part of the entry above it, so it
  would reintroduce this very defect one level down. `test_a_nested_sub_bullet_counts_for_the_answer_above_it`
  and its mutation pin the choice.

## Pass 4 — findings: 8

Asked for by the owner: *"do the full review passes based on all the review
levers and ensure that the lines of code are as optimised as possible."* Every
finding is in code this slice added.

**Pass 3 reported 0 and was wrong.** It worked the levers it expected to matter —
the ones about whether the fix was correct — and never read the diff as a diff.
Eight of these were visible on the page the whole time. Worth recording, because
a 0 that ends a review is only worth what the pass behind it looked at.

- `every-line-earns-its-place` + `no-copy-paste` — **`_answers`' docstring was 17
  lines over 5 lines of code, and its middle paragraph restated `_blocks`'
  docstring almost verbatim.** The lever names "a docstring longer than the code"
  explicitly, and duplicated prose drifts exactly like duplicated code. `_answers`
  now points at `_blocks` for block semantics and keeps only what is its own: the
  measured defect, and the did-not-parse note.
- `no-copy-paste` — `match.group("verdict").strip("* ").rstrip(" —")` was written
  out **three times** (`pillar_kinds`, `check_pillars`, `check_evidence`); two of
  those lines are in this diff. Extracted `_verdict(match)`, one line, three
  callers. Pre-existing triplication, but this diff touched two of the three, so
  leaving it would have been choosing not to look.
- `every-line-earns-its-place` — `_blocks`' heading scan was a four-line inner
  loop that **reassigned the loop's own bound** (`end = offset; break`). Correct,
  because `range` was already materialised, but it reads as a bug. One
  `next((i for i in … ), end)` instead: four lines to one, and nothing mutated
  mid-iteration.
- `guards-must-be-able-to-fail` — `_blocks` and `_answers` had **no return
  annotation**, in a file whose other helpers annotate. `scripts/**` is outside
  mypy's scope, so nothing would ever have said so. Both annotated
  (`Iterator[tuple[str, str]]`, `Iterator[tuple[re.Match[str], str]]`).
- `docs-match-behaviour` + `test-that-cannot-fail` — `_answers`' docstring claimed
  a line meant as an answer that does not parse **still ends the block before
  it**, and nothing pinned it. Without that, P1 would swallow the malformed line
  and be credited with the token on it.
  `test_an_unparseable_answer_line_still_ends_the_block_above_it` now pins it, and
  a curated entry mutates `_blocks(section, _MEANT_AS_ANSWER)` to `_ANSWER`.
- `every-line-earns-its-place` — the `parse_deviations` comment was four lines
  repeating what the design and the CHANGELOG already say. Two lines, carrying the
  one fact that is not in the code: a wrapped `approval:` id read as no approval.
- `search-before-writing` — **`_registry()` has been in
  `scripts/test/test_gate_models.py` the whole time and I wrote its body out by
  hand three times.** Replaced in all five places, including the two that predate
  this slice.
- `parameterize-dont-clone` — two of the new pillar tests differed only in the
  answer text, testing one rule (whichever rule reads `detail` reads the
  continuation lines). One parameterised test with two cases; the refusal control
  stays its own test, because it asserts the opposite.

Also found and re-pointed, not a lever finding but worth the record: two curated
entries in `record_blocks` went **stale** against the refactor above — the
block-collapse entry (the yield line changed) and the heading entry (the inner
loop became one expression). Caught by re-counting every target against the
source, which is the module's documented remedy rather than deleting them.

One entry had to be narrowed. `an unparseable answer line stops ending the block
above it` first mutated `opens.match` inside `_blocks`, which broke the helper for
**both** callers and failed nine tests — "caught", but proving only that the
parameter is used. Re-pointed at `_answers`' own call site, where it now fails one
test: the one that asserts the property.

## Pass 5 — findings: 0

- Re-ran the specificity check over all nine `record_blocks` entries: each fails
  the test that asserts its own property, with the rest of the file passing.
- Re-confirmed against the unfixed `scripts/gate_models.py` after the refactor:
  **6 of the 15 collected new cases fail**, the same set as before Pass 4, so the
  optimisation did not weaken what the tests prove.
- `no-redundant-artifacts` — checked for a dead `import json` after replacing the
  five inline registry reads; it is still used twice, so it stays.
- `one-verdict` — `_verdict` returns the verdict, not the pieces to re-derive it;
  `pillar_kinds` lowercases the result rather than re-stripping the match.
- `use-existing-apis` — `_blocks`, `_answers`, `_verdict` and `_detail` are all
  private helpers in the module that owns the records; no parallel parser.
- `minimal-host-dependency` — `collections.abc.Iterator` is stdlib; nothing new is
  required of the machine.
- `provenance-and-precedence` — a token's only source is the entry's own block, and
  a block cannot overlap its neighbour, so there is no two-source precedence to
  resolve.
- Groups 5 and 7 re-checked and still n/a: no screen, no control, no session.
  Group 7 touches the owner-approval path only in that a wrapped `approval:` id is
  now found and a withdrawn entry cannot lend its id upward — both tested.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one `_blocks`, two callers; Pass 2 chose a
                                          parameter over a second parser; Pass 4 removed a
                                          triplicated verdict read, a docstring that restated
                                          another, and three hand-written copies of `_registry()`
Group 2 · Quality / safety            [x] checked — Pass 1 fixed a test that could not fail and
                                          a catalogue entry that caught nothing
Group 3 · Architecture / hygiene      [x] checked — one helper in an existing module; no new
                                          file, no new dependency
Group 4 · Process                     [x] checked — CHANGELOG entry under [Unreleased]
                                          (scripts/** requires one); two shipped designs flipped
                                          to done, clearing the trailing-flip debt
Group 5 · Intuitive UI                [x] n/a — no screen or control; the surface is the gate's
                                          refusal text, kept verbatim and now true
Group 6 · Signal integrity            [x] checked — a false refusal reads exactly like a true
                                          one, which is why this cost two blocked commits
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session. It does touch the
                                          owner-approval path: a wrapped `approval:` id is now
                                          found, and a withdrawn entry cannot lend its id to the
                                          entry above it

Tests added/updated:      scripts/test/test_gate_models.py 38 → 52 collected (13 new functions,
                          one of them parameterised into two cases) plus one end-to-end commit in
                          scripts/test/test_gate_pillars.py. 6 of the 15 new cases fail against
                          the old code, re-confirmed after the Pass 4 refactor; the rest are
                          controls, 3 of which must pass either way.
Mutation-checked:         new suite `record_blocks`, 9 mutations, all caught, and each verified
                          to fail the test asserting its own property with the rest of the file
                          passing — re-verified after Pass 4 re-pointed two stale targets and
                          narrowed one that was too broad. The FULL catalogue was NOT completed
                          locally: the harness edits gated files in place, so every turn boundary
                          during a ~30-minute run was refused by the stop gate as unreviewed work
                          (now a backlog item). CI runs it across four required shards, and
                          scripts/mutation_check.py is in SHARED_TRIGGERS, so every suite runs
                          there on this branch.
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:4b1fab2a0d76
Gates run locally:        pytest — the full suite on the final tree, 2463 passed / 10 skipped
                          (2448 before this slice, + 15 new cases); ruff; mypy==1.14.1 from
                          requirements-lint.txt (48 files); py_compile sweep; mutation_check.py
                          record_blocks; design-tree drift; agentsmith gate kg check;
                          --check-hooks; --check-redaction on both profiles; process gate
                          (design + review). Not run here: the full curated catalogue (above),
                          and the Postgres-backed and portal jobs, which need services.
Declared gaps:            one, and it is the change itself: the checks are deliberately more
                          permissive. More text counts as "the entry", so unrelated prose under
                          an entry that happens to carry a resolving backtick now satisfies it.
                          Each token still resolves against what the commit tracks, so the bar
                          per token is unchanged; only the span searched moves. Declared in the
                          CHANGELOG and in P13.
```
