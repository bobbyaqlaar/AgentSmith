# Review — the shell pre-check's parse: one walk, and a quoted path is a quote

Design: `.agent-rfc/designs/shell-gate-one-walk.md`. Owner's instruction, 2026-10-16: "ensure that
the lines of code is as optimised as is possible".

**Built evidence (2026-10-16):**

- **The claim is measured, not asserted.** `ast` over the file before and after: **104 executable
  statements both times** (docstrings excluded). `_config_refusal` 38 → 30 lines, `_subcommand_at`
  12 → `_git_subcommand` 7 plus `_walk` 13 (shared). Raw file length **+6 lines**. So this slice
  removes a duplicated parse and two duplicated sentences; it does not shrink the file, and the
  design says so rather than implying a size win.
- **Behaviour pinned by the previous slice's mutants**, re-run against the refactored code and each
  reverted: 16 mutants — no read check, no-value-as-write, no unset check, no section check, reads
  before removals, walk skips no values, no verb pop, subcommand is first word, no env skip, no
  `env` word, no `GIT_CONFIG*` check, case-sensitive `-c`, no `--config-env=` prefix, re-arm
  refused, any section name, commit flags from all args. **16 of 16 caught** after pass 1.
- **Nothing a caller sees changed, over 1,611 commands.** The committed version and this one were
  loaded side by side and asked the same corpus — every command string in the test file, plus the
  cross-product of 6 environment prefixes, 7 global-option forms and 36 subcommands, plus the
  protected-path writes and their quoted forms: **1,008 refused, 603 allowed, 0 differences**,
  string for string. That is the evidence for "no behaviour change"; the 107 tests passing is the
  weaker claim.

## Pass 1 — findings: 1

- `test-that-cannot-fail` — **finding:** the mutant "subcommand is first word" (`if True` in place
  of `if not word.startswith("-")`) **survived**. `_walk` already skips `-C`/`--git-dir` *with*
  their values, so no existing case put a **valueless** global flag before the subcommand: nothing
  asserted that `git --no-pager commit --no-verify` is still refused. The code was right and the
  test was blind. Three cases added — `git --no-pager commit --no-verify -m x`,
  `git --literal-pathspecs push --no-verify`, `git --no-pager config core.hooksPath /dev/null` —
  and the mutant is now caught. 104 → 107 tests.

## Pass 2 — findings: 1

- `backlog-discipline` / `docs-match-behaviour` — **finding:** the CHANGELOG line for this slice was
  appended to the entry of the previous one, which has since been **released in v2.0.0** — editing a
  released section rewrites history and would have claimed today's refactor shipped in September.
  Caught by reading which `## [` heading the line fell under (`awk` over the line number), not by
  looking at the diff. The line is removed from the 2.0.0 section and the slice has its own
  `[Unreleased]` entry.

## Pass 3 — findings: 0

Every lever group `--impact` names over the final diff, plus the whole-file read. Considered and
declined, each for a stated reason:

- Expanding `(flags.add if word.startswith("-") else operands.append)(word)` into a four-line
  `if`/`else` for legibility. It is one statement doing one thing and the surrounding code is
  written at the same density; the expansion costs lines without buying clarity for a reader who
  has read `_walk` directly above it.
- Building `typed` and `gone` only inside the branches that return them, to spare the read path two
  string operations. The gate runs once per shell command; the cost is unmeasurable and the
  duplication is not. Left where the reader can see both messages come from one place.
- Merging `_GIT_OPTION_VALUE` and `_CONFIG_OPTION_VALUE` into one set and walking once. It would
  save a few lines and let a git-level flag be read as a `git config` action — the two levels have
  different vocabularies, and `-l`/`--get` mean nothing to `git` itself. Refused on
  `validate-on-the-receiving-side`.
- Registering these mutants in `scripts/mutation_check.py` so CI re-runs them. Still its own change;
  the 16 are recorded here and in the previous slice's record. Unchanged from that slice's view.

## Pass 4 — findings: 1

- `validate-on-the-receiving-side` / `guards-must-be-able-to-fail` — **finding, fixed in this
  slice** (the handoff this record first proposed was withdrawn: a second active design covering the
  same two files has no review record of its own until its work is done, which the stop gate
  refused — correctly. One slice, one record, and the differential corpus below keeps the two
  claims apart):
  `_redirect_targets` scans the **raw** segment text, so a protected path written inside quotes is
  refused as if it were a redirect. Confirmed twice, both times against this review's own work: the
  gate refused the shell command that ran the differential check above, because the corpus
  contained a quoted `> <an IDE hook config>` string, and then refused the command writing *this
  paragraph*. Quoting an interpreter string or grepping for the pattern in `docs/` is refused the
  same way; only a bare redirect should be.
  It is the same false-positive class the previous slice fixed for `git commit --no-verify` by
  tokenising the line, and `_segments` already yields the operator as its own token, so the fix is
  to read redirects from the tokens rather than from the text.

## Pass 5 — findings: 1

Building that fix, tests first (4 quoted forms that must pass, 7 redirect forms that must still
refuse, the unbalanced-quote line, and an operator with nothing after it). 4 failed before the fix,
as intended — and one of the four was a surprise:

- `guards-must-be-able-to-fail` — **finding:** `echo x >| <an IDE hook config>` was **never
  refused**, by the old rule or the new tests' expectation of it. The old pattern
  (`>>?\s*([^\s;|&]+)`) excludes `|` and `&` from a target, so after `>|` it captured nothing and
  the write passed. `>&` had the same hole. Reading the operator as a token closes both: this slice
  **strictens** two forms while narrowing the quoted ones. Both are in the CHANGELOG entry and
  measured below, rather than being described as one "fix".

## Pass 6 — findings: 1

The mutants re-run over the finished slice — 21 now, the 16 of the earlier slices plus five for the
redirect reading (text instead of tokens, no fallback, each operator dropped from `_REDIRECTS`,
reading past the last token).

- `test-that-cannot-fail` — **finding:** "no fallback when unparsed" **survived**. The test for the
  unbalanced-quote line used `echo 'x > <path>` *with spaces*, and the crude split happens to yield
  `>` as its own token there, so the token rule caught it and the fallback was never exercised. The
  case that pins it is the **glued** form, `echo 'x >.githooks/commit-msg`, where the split leaves
  `>.githooks/commit-msg` as one word and only the character reading finds it. Test rewritten to
  assert both, and the mutant is caught: **21 of 21**.

## Pass 7 — findings: 0

- **Differential corpus, 1,684 commands**, this slice against the commit before it: **28
  differences, every one intended** — 10 quoted mentions now allowed, 18 `>|`/`>&` writes now
  refused, and the other 1,653 verdicts identical, string for string. That is the measurement that
  separates the refactor's "nothing changed" from the fix's "exactly this changed".
- **Verified live, which is how the defect was found.** The hook in this checkout runs this code,
  so the literal command that the gate refused twice during pass 4 —
  `echo 'x > .githooks/commit-msg'` — now runs. The refusal of a real redirect to the same path is
  unchanged.
- `docs-match-behaviour` — `docs/process-gates.md`'s shell surface says a write is the operator in
  the tokens, names the two newly-refused operators, and states the unbalanced-quote fallback; the
  module docstring and the doc both add a redirect through a variable (`> $CONFIG`) to the stated
  limits, where it was previously unmentioned and unread.
- Final read of the whole diff: `_segments` returning its tokenised flag, `_redirect_targets` over
  tokens, `_redirect_targets_in_text` keeping the old reading, the one call site, `_walk`,
  `_git_subcommand`, `_config_refusal`, the three message templates, the two flag checks, and the
  tests. Nothing else.

## Pass 8 — findings: 2

The stop gate refused the turn here: the record was older than the last edit to the code it covers,
which is the rule working — pass 7 was written, then the file was edited twice more. Both of those
edits came from reading the diff as a stranger would, and both are recorded now rather than
slipped in:

- `docs-match-behaviour` — **finding:** the comment above `_REDIRECTS` named four operators where
  the set holds six (`>&` and `&>>` were missing from the prose). It now describes the rule —
  truncate, append, both streams in two spellings, the noclobber override — and adds that `>&2`
  names a file descriptor, not a path, so no protected path can match it (verified: that line is
  allowed).
- `no-redundant-artifacts` — **finding:** the docstring line carrying the quoted example ran past
  the file's 120-column limit once the example was inlined; rewrapped. `awk` over the file confirms
  the longest line is now 120, which `ruff` accepts.

## Pass 9 — findings: 0

Whole file read once more, top to bottom, after those two edits: the stated limit in the module
docstring, `_segments`'s tokenised flag, both redirect readers and the single call site, `_walk`,
`_git_subcommand`, `_config_refusal` and its templates, `_git_refusal`, `refusal`. 120 tests, 21 of
21 mutants, `ruff` clean, and the 1,684-command corpus re-run against the committed version with
the same 28 accounted-for differences.

## Pass 10 — findings: 0

The committed state, after this slice was held aside for the sibling commit
(`fix(kg): the graph maps this repository…`, `a34c79d`) and restored. Worth recording, because the
restore is the kind of step that loses work quietly:

- `git stash pop` **conflicted** on `.agent-rfc/fixtures/knowledge_graph.json` and `CHANGELOG.md`:
  `git stash push -- <paths>` had also captured the index state of those two, which the sibling
  commit then changed. Recovered deterministically instead of merging — the two shared files taken
  from `HEAD`, this slice's five files restored byte-for-byte from copies made outside the repo
  before the stash, the CHANGELOG entries re-inserted from the held text, the stash dropped. Zero
  conflict markers remain in either file, checked by `grep`.
- Re-verified on the restored tree: **138 tests pass** — `test_gate_shell.py` 120,
  `test_knowledge_graph.py` 12, `test_bare_except_tree.py` 2, `test_documented_env_vars_exist.py`
  4 — `ruff check scripts/` clean, fixture regenerated to **592 nodes, 215 edges** (the sibling's
  590 plus this slice's two record nodes), no `worktree` or `.claude` path in it.
- Six gates re-run by name on this exact tree, all passing: the process gate itself, commit
  guardrails, ruff, py_compile, `--check-kg`, `bash -n`.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the point of the slice
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_shell.py — 3 cases added (104 → 107); no test changed
                          its expectation, because no behaviour changed
Mutation-checked:          21 hand mutants over this file, 21 of 21 caught, each reverted — the
                          16 of the earlier slice plus five for reading redirects from tokens.
                          Two survived first and exposed real test holes (passes 1 and 6).
                          `gate_shell.py` is a target in no curated suite
                          (`mutation_check.py --list` checked), so these are its coverage
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:c8007b99b80a
Gates run locally:         six gates by name on the committed tree, all passing — the process
                          gate itself, commit guardrails, ruff, py_compile, --check-kg,
                          bash -n/zsh -n; and on the same code before the sibling commit,
                          fourteen by name (adding DESIGN.md tree drift, redaction, on-prem
                          template, delivery evidence, delivery-model unit tests and the two
                          npm suites) with mypy skipped — it needs an install step and its
                          scope is `files = ["runtime"]`, so it never covered scripts/.
                          Full pytest on this code: 2396 passed, 1 failed, that failure being
                          the sibling slice's `# fail-open:` marker, fixed and re-run green.
                          NOT run locally: the full `gates run`, whose curated-mutation step
                          derives its scope from the knowledge graph and ran four hours
                          unsharded; CI shards it four ways in 10-12 minutes
Declared gaps:             unchanged from .agent-rfc/reviews/shell-gate-config-reads.md —
                          `git config --edit`, writes straight into `.git/config`, an earlier
                          `export GIT_CONFIG_…`, `env` with options of its own. mypy does not
                          cover `scripts/` ([tool.mypy] files = ["runtime"]), so the new
                          annotations are for the reader
```
