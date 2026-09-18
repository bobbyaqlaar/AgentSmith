# Review — a pointer into another document names something that document defines

Design: `.agent-rfc/designs/xref-names.md`. The owner chose option (a) on 2026-09-18: look in the
target, not at the number's shape.

**Built evidence (2026-09-18):**

- **Prototype before design.** A throwaway run of the proposed rule over every tracked file came
  before the design was written, and it changed the design twice:
  - The archive's `| 4.14 |` rows are entry IDs that never move, yet the same shape in
    `docs/uae-regulatory.md` (`| 2 |` under `## 2. Strict Bias…`) is a position. Pure option (a)
    passed both. The difference is the document, so the registry now says which types are
    append-only, and only there does a number that opens a heading or row count as a name.
  - `2.3` in the archive is defined by a bold list item, not a table or heading, so list items
    are a third place a name can be defined.
- **Failing tests first.** The new tests in `scripts/test/test_gate_artifacts.py` were written before
  the code; collection failed on the missing `append_only` field.
- **Mutation checks (each reverted):** fourteen against `process_gate.py` — append-only ignored,
  positions allowed, fenced code counted, the old token pattern, the lettered form not positional,
  the date skip removed, table rows not names, list items not names, no file on added lines, the
  registry not reaching the commit gate, line numbers allowed, a missing target allowed, substring
  instead of whole-word match, a `++` content line read as a header. Thirteen caught on the first
  run; the survivor is finding 3.

## Pass 1 — findings: 5

- `gate-integrity` — **finding:** the widened token pattern could not match `E.1`: the letter
  had to run straight into a digit. The lettered form the design names was invisible to the rule,
  and the unit test for it would have failed. The pattern takes an optional `.` after the letters.
- `grep-for-siblings` — **finding:** the sweep found 14 lettered headings in `docs/UserManual.md`
  (`#### E.1 — Setup`, `### G.3 — MDM deploys…`), left by G5b when their parts were renamed. The
  letters point at parts that no longer exist. Numbers are gone from those headings; the one
  in-text reference (`see E.1 above`) names the heading. "Bare number" now covers the lettered
  form, so a pointer to one is a position.
- `test-that-cannot-fail` — **finding:** mutation "registry not passed" survived. The
  end-to-end test's log entry was `## Pass 4`, a name in any document, so it passed with the
  registry never reaching the commit gate. The entry is now a numbered row, which is a name
  only where `append_only` says so.
- `declared-vs-enforced` — **finding:** the design said the rule runs "at commit and in CI". CI
  and the pre-push sweep skipped every commit that touched no gated path, and most documents are
  ungated — a docs-only commit that bypassed the commit gate had its pointers read by nothing.
  `check_commits` now reads them; test
  `test_ci_reads_the_pointers_of_a_commit_that_touches_no_gated_path`, which failed before the fix.
- `test-the-contract` — **finding:** `_added_lines` now carries each line's file, and nothing
  pinned that, or that a content line beginning `++` is not a header. Test
  `test_added_lines_carry_the_file_they_are_in`. Its header detection also reset only on
  `diff --git`; a merge's `diff --cc` would have left the previous file's hunk open. It resets
  on any `diff ` line.

## Pass 2 — findings: 0

Every lever over the final diff, and the rule over every line the commit adds (clean).
Considered and declined:

- A permanent whole-tree check. It would catch a heading rename that kills an existing pointer,
  but the pointers this rule reads point into append-only records, whose IDs do not move. The
  pointer that does die that way is the heading-name one, which carries no digit; it is a
  backlog item.
- Renumbering `docs/uae-regulatory.md`. Its five numbered headings are the five requirements it
  maps, repeated in its own status table. The one pointer into it now names the heading; the
  document is reference material with its own structure.
- Changing records under `.agent-rfc/`, `CHANGELOG.md` and `docs/PRODUCT_ARCHIVE.md` that carry
  old pointers, legacy fixture text (`scripts/test/fixtures/legacy_profile_block.zshrc`), and
  test strings that are deliberate examples (`scripts/test/test_gate_shell.py`). History says
  what was true when it was written. The rule reads added lines, so none of these is re-judged.

**The sweep, for the record** — dead pointers in living files, each fixed: `portal/README.md`
(a manual section and part that G5b renamed), `templates/uae-sovereign/README.md` (a numbered
heading), `docs/PRODUCT_BACKLOG.md` (a section a review record never had — the slice has its own
record), and three archive entries that exist nowhere, cited from `install-ai-stack.sh`,
`.github/workflows/release.yml` and `scripts/cost_router.py`. The explanations around those
three stayed; only the pointer went.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_artifacts.py (+22: the verdict rules, both directions;
                          resolution beside the file; no registry; the example marker;
                          added lines with their files; the commit gate end to end; CI over
                          a docs-only commit); test_gate_models.py (+1: which types are
                          append-only)
Mutation-checked:          yes — fourteen, each reverted; one survivor became finding 3
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json; templates/governance.json
                          regenerated from agent-rules.yaml
KG query:                 kg:b1786556d021
Gates run locally:         ruff, the full pytest run (1691 passed, 10 skipped), the rule over
                          this commit's added lines, `agentsmith gates run`
Declared gaps:             (1) a pointer by heading name dies unread when the heading is
                              renamed — backlog;
                          (2) a pointer into another repo's document is refused as not in
                              this repo; it carries the example marker or names the section
                              in words;
                          (3) a number followed at once by `-<digit>` is read as a date or a
                              range and skipped, so `X.md 5.10-5.12` is not read.
```
