# Review — three passes of the documentation against the code

Design: `.agent-rfc/designs/docs-vs-code-audit.md`. Owner, 2026-09-26: "Do three more review passes
of the documentation against the code unless no findings before the third pass."

All three passes found something, so all three ran. **7 findings**, and the most consequential was in
the third. Each pass checked a different class of claim mechanically; the scripts were written to the
scratch directory, and the one check worth keeping became a test.

## Pass 1 — findings: 3

**The command surface.** Every `agentsmith …` invocation and every `--flag` in the documents, resolved
against `build_parser()`; then the Command Reference table's flag column against what each command
actually accepts.

Clean: all 26 leaf commands are documented, no documented command fails to resolve, and no documented
flag is missing from its command. The two apparent failures were prose (*"removes the agentsmith link
and…"*, *"agentsmith is at ~/.local/bin"*).

1. `docs-match-behaviour` — **`agentsmith tenant init`'s reference row documented two of seven
   options.** It omitted `--architecture` (five structural styles), `--agentic` (the whole agent
   layer), `--force`, `--root` and `--allow-framework-root` — while `tenant adopt`'s row documented
   `--architecture` and `--agentic`. Two sibling commands documented inconsistently, so a reader
   would conclude `init` cannot do what `adopt` can and choose `adopt` for the wrong reason.
2. `docs-match-behaviour` — **`agentsmith gate`'s row omitted `--ide`**, the flag that reads the
   payload in an IDE's dialect instead of the neutral profile. That is precisely what an integrator
   needs, on the command the contract exists for.
3. `docs-match-behaviour` — **`agentsmith uninstall`'s row omitted `--legacy-profile-only`**, the
   flag that removes just the shell-function block a pre-2.0.0 install appended — which was 2.0.0's
   headline change.

## Pass 2 — findings: 1

**Paths and written files.** Every repository path a document names in backticks, resolved against
the filesystem; then what the documents say a command writes, against what it writes.

The path half is clean. It took two detector fixes to establish that, and both are worth recording
because the first version of a check reporting 213 problems is `check-that-fires-on-everything` in
reverse: a bare basename (`cost_router.py`) is a documentation convention, not a broken path, and
`lstrip("./")` silently ate the leading dot of every `.agent-rfc/…` and `.github/…`. Of the 24
genuinely unresolvable, all are tenant-side files, machine state under `~/.agent-framework/state/`,
repository slugs, dotted module paths, or `scripts/thing.py` — a placeholder inside a gate error
message. `.github/hooks/agentsmith.json` is unresolvable and the table that names it already says
"schema not verified", which is the honest state rather than a defect.

1. `docs-match-behaviour` — **the manual's adopt section is framed "What it keeps" and names eight
   files; adopt writes twenty-eight.** Unnamed: `GEMINI.md` and `.github/copilot-instructions.md`
   (so a Gemini CLI or Copilot user is not told their rule file gets a block), `.cursor/hooks.json`,
   six `.agents/skills/*/skill.md`, `.agent-history.log`, `tenant.yaml`, `process-gates.json`, and
   three of the four gate hooks. A reader deciding whether to run this on a real repository deserves
   the footprint. Found by running adopt on a throwaway repository and diffing the written set
   against the prose — the second half of the pass, which is why a pass that looked like zero was
   not reported as zero.

## Pass 3 — findings: 3

**Behavioural claims.** Exit codes, defaults and resolution orders, checked by reading the code they
describe. Defaults were low yield — three flags carry one, two are stated. Resolution orders were
not, which was the expectation: the two live defects found yesterday were both orders.

Verified correct: the gate launcher's four-interpreter order, the model-profile precedence
(`AGENT_MODEL_PROFILE` → `AI_STACK_MODE` → `state/mode` → `default_profile`), the judge-model
precedence, and `exit 3` as "cannot run here".

1. `docs-match-behaviour` **and the worst of the day** — **`docs/DESIGN.md` documented `resolve()`'s
   precedence backwards.** It said *"explicit → environment → `tenant.yaml` → documented default or
   raise"*. The code is explicit → `.env` → `tenant.yaml` → **ambient `os.environ` last** → default.
   Two errors: `.env` was omitted entirely, and the ambient environment was placed second instead of
   last — the exact inversion `runtime/config.py`'s own docstring exists to warn against, under the
   heading *"PRECEDENCE, and why it is not simply 'environment wins'"*. That docstring ties the
   inversion to a real 30× budget breach: KYC Sentinel declared a $5 monthly cap while the gateway
   enforced a $150 default. A reader of DESIGN.md would have believed an exported variable overrides
   a declared control, which is both wrong and the security-relevant direction to be wrong in.
   `docs/UserManual.md` had it right, so the canonical design document contradicted both the code
   and the manual.
2. `ambiguous-signals` — **"the gate fails closed" was true of three callers out of five.** With no
   usable interpreter, `pre-edit` denies, `commit-msg`/`pre-push`/`ci` block — and `session-start`
   and `stop` warn on stderr and exit 0, which `docs/process-gates.md` never said. The strongest
   claim in that document was unqualified, so a reader would believe a broken install stops
   everything. It now says which callers block, which warn, and why blocking every turn of a session
   would make the IDE unusable rather than safe.
3. `pin-unremovable-duplicates` — **`agentsmith hooks bypass-check` has no reference row**, found by
   the test written in Pass 3, not by Pass 1. Pass 1's sweep grepped `agentsmith hooks` and matched
   the parent, so it reported the command documented: a false negative in my own check, which is the
   argument for the test over the audit. It *is* documented, in its own prose section, and its parent
   is marked "internal: called by the git hooks" — so the exemption is legitimate and now explicit.

## The check that became a test

Pass 1's extraction is the only one that earned permanence: the Command Reference table is a second
copy of the CLI surface across a boundary that cannot be merged, which is exactly
`pin-unremovable-duplicates`' case for a test that PARSES the other side. Added to
`scripts/test/test_cli_install.py`, beside the existing test that pins the compat wrappers the same
way and whose `_leaf_paths` helper it reuses:

- `test_every_command_has_a_reference_row` — and the exemption list is pinned in both directions, so
  a command that stops existing cannot leave a stale exemption behind;
- `test_a_command_kept_out_of_the_table_is_still_documented` — without it `_NOT_DAILY_COMMANDS` would
  be a way to make a command vanish;
- `test_every_reference_row_lists_the_flags_its_command_accepts` — the check that found Pass 1's
  three findings.

Both new assertions were run against the reverted fixes and both failed, which is the only evidence
that a test of prose is a test at all.

The other two passes' extractions stay in the scratch directory. Pass 2's path check needed two
corrections to stop reporting conventions as defects and would cost more in false alarms than it
returns; Pass 3's claims are prose that no parser can bound.

## Pass 4 — findings: 0

- ruff, mypy, the artifacts registry check, the doc suites, and `test_cli_install.py` (19): green.
- Re-ran Pass 1's extraction against the corrected manual: no command unresolved, no row missing a
  flag, no flag missing a command.
- The `resolve()` correction checked against `runtime/config.py`'s docstring clause by clause, and
  `docs/` grepped for any sibling stating the order the old way: none.

## Stated limits

- **Three claims no check can bound.** That `agentsmith conformance` lets a third party self-certify
  (true of the suite, never exercised by a third party); that the two generated workflows behave as
  documented on GitHub (they have still never run); and the compliance-mapping tables, which are
  claims about frameworks rather than about this code.
- **CHANGELOG.md was excluded** from the path pass. It names files that deliberately no longer exist
  — `SPECS.md`, `FIXES_AND_CLEANUP.md`, `review-lever-scalps.md` — because recording a rename is its
  job. Nothing checks that its historical paths were real when written.
- **Pass 2's finding was found by running adopt, not by the pass's own extraction.** The mechanical
  half of that pass returned nothing; had I stopped there I would have reported a clean pass and
  missed it. Nothing in this repository would have caught it either.
- **The new tests pin the table's flag coverage, not its accuracy.** A row can describe a flag
  wrongly and still pass.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the new tests reuse `_leaf_paths` rather than a
                                          second parser walk
Group 2 · Quality / safety            [x] checked — the precedence correction is the one with a
                                          security direction, and it now matches the code
Group 3 · Architecture / hygiene      [x] checked — DESIGN.md no longer contradicts both the code
                                          and the manual on the same question
Group 4 · Process                     [x] checked — three passes as asked, each a different class of
                                          claim; a fourth confirmed zero
Group 5 · Intuitive UI                [x] checked — adopt's 28-file footprint is a table a reader can
                                          act on before running it
Group 6 · Signal integrity            [x] checked — "fails closed" now names which callers block and
                                          which warn
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_cli_install.py (+3), both new assertions confirmed
                          failing against the reverted fixes
Mutation-checked:          the two new table tests were each run against a restored defect; no
                          production code changed, so no mutation suite applies
Fixtures re-pinned:        not required — documentation and tests only, no code in the graph changed
KG query:                 kg:625ffaf95022
Gates run locally:         ruff, mypy in a clean environment, the artifacts check, the doc suites and
                          test_cli_install.py
Declared gaps:             (1) three claims no check can bound; (2) CHANGELOG paths unchecked;
                              (3) Pass 2's finding came from running adopt, not from its extraction;
                              (4) the new tests pin coverage, not accuracy
```
