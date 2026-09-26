# Review — siblings of the three defects the last slice fixed

Design: `.agent-rfc/designs/sibling-sweep.md`. Owner, 2026-09-26: "The findings indicate more full
passes until no more findings come up. Go for up to 3 passes if no findings come up in the meantime."

Three passes ran and the full suite then found two more. **5 findings**, plus three collections
hardened in passing. Pass 3 found nothing and its extraction was not fit for purpose, which is where
the sweeping stopped; passes 4's findings came from running everything, which is twice now that the
suite has caught what a pass did not.

## Pass 1 — findings: 2

Swept for siblings of the three classes the previous slice fixed, rather than for more documentation.

1. `check-that-fires-on-everything` — **`examples/**/test*.py` in
   `scripts/test/test_no_tenant_repo_dependency.py` matches nothing.** There are no test files under
   `examples/`, and the test's own guard — `assert len(sources) >= 40` — is satisfied by the other two
   globs, so the dead member contributes zero invisibly. The same shape as `portal/*.py` in the
   env-var test and `.sh` in the reverse one: **an aggregate assertion the surviving members satisfy.**
   Three occurrences in two days is the argument for a guard over a fourth fix, so
   `test_every_ls_files_glob_in_a_test_matches_something` now asserts that every `ls-files` glob any
   test passes resolves to at least one tracked file — 34 globs, and it refuses to run on fewer than
   20 in case the extraction itself breaks.
2. `ambiguous-signals` — **a malformed pillar answer is reported as an absent one.** `_ANSWER` in
   `scripts/gate_models.py` drops a line it cannot parse, and `check_pillars` then reports the pillar
   as unanswered: `- P3: applies — ...`, a colon where a space belongs, yields *"'## Pillars' does not
   answer P3"* and never quotes the line, so the author is told they omitted something that is on the
   page. Sibling of `_PASS`, milder — the message at least names P3, where `_PASS` pointed at other
   passes' numbers. Fixed with `_MEANT_AS_ANSWER`, the same remedy, and
   `test_a_pillar_that_is_genuinely_absent_is_still_reported_as_absent` keeps the diagnosis from
   swallowing the case it was confused with.

Checked and **not** siblings, recorded so the sweep is not mistaken for a partial one:

- **`_KG_QUERY`** is anchored the same way as `_PASS`, and a line it cannot parse is reported as
  "records no 'KG query:' line" — which is what happened, with the required form spelled out. Right
  message for the right cause.
- **Positional pairing.** One `zip` in shipped code (`scripts/mutation_check.py`, `strict=True` over
  two fixed 2-tuples) and one parse-then-pair in a test
  (`scripts/test/test_framework_python_env.py:82`, which **asserts** the two lengths match before
  pairing — the pattern my own broken test should have used). No siblings; the repository already does
  this right where it does it.

## Pass 2 — findings: 1

Sought the shape underneath all three glob defects — a sweep whose assertions all sit inside a loop
over a collection that could be empty. 40 candidates, of which most iterate a literal defined in the
test and cannot be empty; narrowing to collections **derived** from a call, a parse or the filesystem
left 11, and reading those left three that could empty by accident.

1. `test-that-cannot-fail` — **`test_every_stacks_ci_runs_the_strict_security_harness` loops over
   `TEMPLATES.glob("ci-*.yml")` with no floor.** Rename the stack templates and a test whose whole
   purpose is "Go and TS tenants were never graded" passes over nothing. A floor of three is now
   asserted before the loop.

Hardened in the same pass, and described as hardening rather than as defects because emptiness is not
reachable by accident today:

- `gi.IDES` is iterated by two tests in `scripts/test/test_gate_ides.py` with no floor, so emptying
  the IDE catalogue would pass both "every IDE has a parser" and "every IDE hook config is gated".
  One floor added, named as guarding the two.
- `_steps()` in `scripts/test/test_rollback_notify.py` returns a parsed `runs.steps`; `steps: []`
  would make every sweep over it vacuous. It now refuses an empty list at the source, so all its
  callers inherit the floor.

## Pass 3 — findings: 0

Sought the shape behind the bare-token assertion that stayed green last week: `assert "X" in text`
where a weaker form also satisfies X. 918 asserted literals, 177 of which appear in more than one
shipped form — and **every one sampled is a substring that also appears in a comment or in prose**,
which is normal and not a defect. The extraction cannot tell "this assertion is too weak" from "this
string is also discussed in a comment", so its 177 hits are noise, not findings. Recorded as an
unfit extraction rather than presented as a clean pass, because the two are different claims: I did
not establish that the class is absent, only that this method cannot find it.

That is where the owner's rule stops the exercise.

## Pass 4 — findings: 2

Surfaced by the full suite after passes 1–3, not by a pass — the same way the previous slice's seventh
finding arrived. Recorded as a pass because it changed the code.

1. `one-catalog` — **the two env-var checks disagreed about what documentation is, and neither can tell
   an environment variable from any other all-caps token.** Both globbed every tracked `*.md`, so
   design and review records counted as documentation offering a knob. Writing
   `SEMVER_LOOP_GUARD` into a review tripped the reverse check once; writing `CODE_SUFFIXES` — a Python
   constant in a test file, not a variable at all — tripped it again. Fixed by agreeing, in one place,
   that `.agent-rfc/**` holds **records** rather than documentation: `doc_files()` lives with the
   forward check and the reverse one imports it, so "documented" now means one thing in both
   directions. It had meant two: records were documentation to the forward check and would not have
   been to the reverse.
2. `docs-match-behaviour` — **and excluding records surfaced a real gap it had been masking.**
   `CLAUDE_PROJECT_DIR` is read by `.githooks/process-gate` and appeared in no user-facing document —
   only inside `.agent-rfc/` records. It decides which repository the gate believes it was invoked in,
   third in a chain after `git rev-parse --show-toplevel`, and it is deliberately not preferred
   because it names the *session's* project rather than the repository being committed to. Now in
   `docs/UserManual.md`'s Runtime Flags table with that reasoning, which is what somebody debugging a
   gate that judged the wrong repository would need.

   Worth stating plainly: narrowing a sweep normally loses coverage. Here it **gained** a finding,
   because the wider version accepted a record as documentation and so believed a variable was
   documented when no reader could find it.

## Pass 5 — findings: 0

Verification of passes 1–4, by running rather than re-reading:

- **Both new assertions fail against a reverted fix**: restoring the dead
  `examples/**/test*.py` glob fails `test_every_ls_files_glob_in_a_test_matches_something`, and
  neutering `_MEANT_AS_ANSWER` fails `test_a_malformed_pillar_answer_is_quoted_not_read_as_missing`,
  while `test_a_pillar_that_is_genuinely_absent_is_still_reported_as_absent` keeps passing.
- **The shared `doc_files()` holds in both directions**: `test_env_var_documentation.py` and
  `test_documented_env_vars_exist.py` both pass with records excluded, and the forward check's shell
  positive controls (`DISABLE_AI_STACK`, `AGENTSMITH_DIR`, `AGENTSMITH_PYTHON`) still resolve.
- **`CLAUDE_PROJECT_DIR`** is in `docs/UserManual.md`'s Runtime Flags table, so the check that found
  it now passes for the reason it was meant to.
- ruff, mypy in a clean environment, and the full suite: **1941 passed, 10 skipped**.

## Stated limits

- **The weak-assertion class is unexamined, not cleared.** Pass 3 failed to build a detector for it.
  Reading assertions by hand across 918 literals is the only route left, and it is not one this
  method reached.
- **The new glob guard checks resolution, not intent.** A glob that resolves to one file when it
  should reach fifty passes.
- **Floors are arbitrary numbers.** `>= 3` stack templates and `>= 6` IDEs encode today's counts; they
  catch a collapse to zero, not a silent drop from six to four.
- **`_MEANT_AS_ANSWER` keys on `- P<digits>`.** An answer written without the leading dash, or with
  the pillar id spelled differently, is still dropped silently.
- **Neither env-var check can tell a variable from any other all-caps token.** Excluding records
  removes the common false positive; a Python constant named in `docs/` would still trip it, and the
  remedy would again be a narrower notion of what a documented knob looks like, not a longer
  allowlist.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the floor for `_steps()` sits at the source so
                                          every caller inherits it, rather than at each loop
Group 2 · Quality / safety            [x] checked — no behaviour changed beyond two gate messages
Group 3 · Architecture / hygiene      [x] checked — a dead glob removed and the class it belonged to
                                          guarded rather than patched a fourth time
Group 4 · Process                     [x] checked — three passes; the third found nothing and says
                                          why its method was insufficient
Group 5 · Intuitive UI                [x] checked — a malformed pillar answer is quoted back to its
                                          author instead of reported as missing
Group 6 · Signal integrity            [x] checked — both fixes are this: "did not parse" and "is
                                          absent" stop sharing a message, and an empty sweep fails
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_no_tenant_repo_dependency.py (+1),
                          scripts/test/test_gate_models.py (+2), test_gate_ides.py (+1), floors in
                          test_workflow_template_wiring.py and test_rollback_notify.py, and one shared
                          `doc_files()` across the two env-var checks
Mutation-checked:          both new assertions run against a reverted fix and both failed;
                          scripts/gate_models.py changed, so the gate suites ran in full
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:e936ef4cf5ea
Gates run locally:         ruff, mypy in a clean environment, the full Python suite
Declared gaps:             (1) the weak-assertion class is unexamined, not cleared; (2) the glob guard
                              checks resolution, not intent; (3) floors encode today's counts;
                              (4) `_MEANT_AS_ANSWER` keys on a leading dash
```
