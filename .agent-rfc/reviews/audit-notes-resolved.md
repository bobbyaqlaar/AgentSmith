# Review — the four things the audits left open

Design: `.agent-rfc/designs/audit-notes-resolved.md`. Owner, 2026-09-26: "Resolve the findings shown
in the Honest notes."

Two of the four were defects in this repository, not in how I ran the audits. **7 findings** across the four notes —
the seventh found by the full suite after the first six were fixed — all fixed, and five of them now
pinned by tests.

## Pass 1 — findings: 4

**Note 3 — the gate's own message.** `scripts/process_gate.py:338` anchors `_PASS` on `\s*$`, so
`## Pass 4 — findings: 1 (CI, 2026-09-24)` matches nothing and the heading **disappears**.
`check_review` then reads the hole it left as a numbering error: *"passes are numbered [1, 2, 3, 5],
expected 1..4 in order"*. One message for two causes, and it sent me to the numbers three times in
one session rather than to the syntax — the third time while writing the review that recorded the
first two.

1. `ambiguous-signals` — fixed with `_PASS_LOOSE`, a scan for anything meant to be a pass heading.
   When the strict form did not capture one, `check_review` returns *that line, quoted*, and returns
   early — every check below it reads a pass list the heading is missing from, so their answers would
   describe a document the author did not write. The strict form is unchanged: the fault was the
   diagnosis, not the rule. `test_a_real_numbering_gap_is_still_reported_as_one` keeps the new
   message from swallowing the case it was confused with.

**Note 2 — the env-var gate scans no shell.** `_source_files()` globbed `runtime/*.py`,
`scripts/*.py`, `runtime/workflows/*.py`, `portal/*.py` — one level deep.

2. `check-that-fires-on-everything` — **`install-ai-stack.sh`, `hooks/*`, `.githooks/*` and the
   on-prem scripts were outside every gate in this repository.** 19 shell files reading 20
   environment inputs, none of them swept. This is the defect the file's own docstring records for
   the portal — *"a glob that reaches for a directory written in another language is not coverage"* —
   one language further along.
3. `grep-for-siblings` — the same glob also missed five Python directories: `runtime/machine/`,
   `scripts/security/`, `scripts/security/runners/`, `examples/oil-price-agent/` and its
   `workflows/`. The sweep now runs recursively and reaches **105** files where it reached far fewer;
   `portal/*.py` is gone, since the portal is TypeScript and matched nothing by construction.
4. `no-redundant-artifacts` — the `portal/*.py` glob had been dead since the file was written, which
   its docstring already said, and had been left in.

**Note 4 — the pillar tests pinned presence, not correctness.** `### Pillar 15 — Anything At All`
satisfied them. Now `test_a_pillar_section_carries_the_registry_name_and_says_something` compares the
heading against the registry's name — on words, so "Cost-Optimization" and "Cost-Optimisation" agree
— and refuses a section under 25 words.

## Pass 2 — findings: 2

The shell rule is where the work was, and my first two versions of it were wrong. Both are recorded
because a detector that miscounts is worse than none: it produces a number that looks like a finding.

1. `test-that-cannot-fail` — **the first rule called three obvious locals environment inputs.**
   Keying on `${VAR:-default}` treats *shape* as evidence, so `RFC_COUNT`, `VENV_VERSION` and
   `GITIGNORE_CHOICE` — each assigned on one line and read with a default on the next — were
   reported. The rule is now: a name assigned anywhere in the file is a **local**, however it is later
   read. `test_a_shell_input_is_told_from_a_local` names all five.
2. `ambiguous-signals` — **a comment counted as an assignment.** `hooks/post-checkout` opens with
   `# Requested by DISABLE_AI_STACK=true for one command`, so the most important input in the file was
   classified as a local by prose *about* it. Comments now decide nothing in either direction
   (`_strip_shell_comments`, the same word-boundary `#` rule `runtime/config._dotenv_value` uses).
   `test_the_shell_sweep_finds_shell_files` carries `DISABLE_AI_STACK`, `AGENTSMITH_DIR` and
   `AGENTSMITH_PYTHON` as positive controls, so the rule cannot quietly stop finding inputs.

Also fixed here: the thin-body half of the new pillar test **could not fail**. It paired bodies to
pillars by position — `zip(_registry_pillars(), bodies)` over a positional `re.split` — which
misaligns the moment a `### Pillar` heading appears anywhere else in the document. Keyed on the id
now, and both halves were run against a wrong name and a gutted section and both failed.

## Pass 3 — findings: 2

**Note 1 — the two passes the stopping rule skipped.** Both ran.

*Config keys* — clean, and established properly rather than assumed. All 11 keys a repo may set in
`.agenticframework/process-gates.json` are read by the gate and documented in `docs/process-gates.md`.
My first extraction reported a twelfth, `shas`, which is a key of `.git/agentsmith/verified` and not
of the config at all: the slice I took of `class Config` over-ran to the end of the file.

*Stated counts* — two wrong:

1. `docs-match-behaviour` — **`CHANGELOG.md` says "the 18 `ai-*` shell functions" twice and there
   were 17.** `git show v1.3.0:install-ai-stack.sh` defines 17, and `templates/shell/ai-compat.sh`
   provides 17. It sits in the 2.0.x compatibility-matrix row, which is what a tenant reads to
   understand the breaking change, so it is a claim about the change rather than a record of a rename.
   Corrected in both places. `docs/REVIEW_LOG.md:19` says 15 and is **left**: a review record states
   what was true on its date.
2. `docs-match-behaviour` — **"6 in each tenant CI template" is 6, 6 and 7.** `ci-go.yml` carries
   seven `# agentsmith:gate` tags, `ci-python-fastapi.yml` and `ci-ts-react.yml` six each, and
   `agentsmith-gates.yml` one — 20 across the templates against 19 in the framework's own workflows.
   The backlog row now says all four numbers instead of one that is right twice out of three.

## Pass 4 — findings: 1

Surfaced by the full suite, not by a pass: `test_every_documented_env_var_is_read_somewhere` failed
on **`SEMVER_LOOP_GUARD`**, "documented but read by nothing" — named in the previous round's review
record, and read at `hooks/post-commit:20`, which I had verified myself.

1. `grep-for-siblings` — **the reverse env-var test has the same shell blind spot, by a different
   route, and I fixed only the forward one.** `CODE_SUFFIXES` includes `.sh`, so shell looked covered;
   every git hook is **extensionless**, so `hooks/*` and `.githooks/*` were invisible — and that is
   where `SEMVER_LOOP_GUARD`, `DISABLE_AI_STACK`, `AGENT_KG_DEFER` and `AGENTSMITH_AUTOPUSH` are read.
   Writing one of them into a document was enough to make the test call it unimplemented. Fixed with
   `_is_source`, and `test_the_sweep_reaches_extensionless_shell` carries three positive controls.

   **This corrects Round 2 Pass 1 of `.agent-rfc/reviews/docs-vs-code-audit-2.md`**, which reported
   zero findings partly on the grounds that "both directions are already tested". Both directions
   were tested and both were blind to the language the installer and every hook are written in. The
   pass was wrong, not merely narrow.

## Pass 5 — findings: 0

- Every new assertion run against a reverted fix: the unparseable heading, a real numbering gap, a
  wrong pillar name, a gutted pillar body, and the shell sweep's positive controls. All failed.
- ruff, mypy in a clean environment, and the full Python suite.
- The widened sweeps confirmed to reach further rather than merely to be rewritten: 105 Python files,
  19 shell files, 20 shell inputs.

## Stated limits

- **Counts in prose are still mostly unpinned.** The pillar count is now asserted against the
  registry; the `ai-*` count is not, and should not be — it is a historical claim about what a
  released installer did, so pinning it to the live shim would make it wrong the next time the shim
  changes. Corrected, not defended.
- **The shell rule is a heuristic.** It reads `VAR=` as an assignment wherever a shell word boundary
  allows, plus `for` and `read` targets, with comments stripped. A name assigned only inside a
  heredoc, or by `eval`, would still be called an input. Three positive controls guard the other
  direction.
- **`_strip_shell_comments` does not know about quotes.** A `#` inside a double-quoted string starts a
  comment as far as it is concerned, so an assignment after one on the same line would be missed.
  Nothing in this repository does that, and the failure direction is a false *input*, which is
  noticed rather than silent.
- **The 25-word floor on a pillar section is arbitrary.** It catches a stub, not a section that says
  the wrong thing at length.
- **`docs/PRODUCT_ARCHIVE.md` and `docs/REVIEW_LOG.md` keep their old counts** deliberately: recording
  what was true when written is their job.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one shell rule, one comment stripper, reused by
                                          all three shell tests
Group 2 · Quality / safety            [x] checked — the env-var control now covers the language the
                                          installer and every hook are written in
Group 3 · Architecture / hygiene      [x] checked — a dead glob removed, and the sweep reaches the
                                          directories it always claimed to
Group 4 · Process                     [x] checked — four passes; passes 2 and 3 found defects in the
                                          work of pass 1, including a test that could not fail
Group 5 · Intuitive UI                [x] checked — the gate now quotes the heading it could not
                                          parse instead of blaming the numbering
Group 6 · Signal integrity            [x] checked — "did not parse" and "numbered wrong" are
                                          different messages, which was the whole finding
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_process_gate.py (+2), test_env_var_documentation.py (+3),
                          test_documented_env_vars_exist.py (+1),
                          test_design_and_validation_docs.py (+1, and one existing test keyed on id
                          so its second half can fail)
Mutation-checked:          every new assertion run against a reverted fix; scripts/process_gate.py
                          changed, so the gate suites ran in full
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:ce20a3ff81a0
Gates run locally:         ruff, mypy in a clean environment, the full Python suite
Declared gaps:             (1) prose counts mostly unpinned, deliberately for the historical one;
                              (2) the shell rule is a heuristic and does not read heredocs or eval;
                              (3) comment stripping is quote-unaware; (4) the 25-word floor catches a
                              stub, not a wrong section
```
