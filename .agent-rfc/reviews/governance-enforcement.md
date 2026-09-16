# Review — governance enforcement

Design: `.agent-rfc/designs/governance-enforcement.md`. Slices G1–G7; this record grows one section per slice.

Reviewed against `docs/review-levers.md` (every lever, every pass) and `docs/validation-checklist.md`.

## G1 — rules registry, design-time pillars, deviations, approvals

**Built evidence (2026-09-16, this machine):**

- **Failing tests first.** `test_gate_models.py`, `test_gate_tracing.py`, `test_cli_approve.py` and
  `test_generate_ide_config_governance.py` were written before the modules they cover and failed at collection.
- **Gates:** `scripts/test/` 714 passed (before the pass-1 fixes; 720+ after, see below), `runtime/test/` 664 passed
  and 10 skipped, `ruff check .` clean.
- **Defects the tests found during the build, each fixed and pinned:**
  - importing the gate's own modules wrote `scripts/__pycache__/` into the repo being checked, which the stop and
    commit gates then reported as gated changes nobody made (`sys.dont_write_bytecode`);
  - `open("/dev/tty", "r+")` raises `UnsupportedOperation` — the approval command would have refused every real
    terminal, not just an agent's (separate read and write handles);
  - the CLI resolved `gate_models.py` only through the machine install, so a stale `~/.agent-framework` gave
    `ModuleNotFoundError` instead of "re-run install-ai-stack.sh";
  - a hook run emitted no span at all, because the test repo — shaped like a vendored tenant — carried no
    `runtime/`. Real tenants do; the fixture now does too, and session start reports the not-emitted state.
- **Mutation checks (each reverted after):**
  - `check_pillars` no longer requiring an answer → `test_a_missing_pillar_is_named` and
    `test_a_design_must_answer_every_pillar_it_is_asked` fail;
  - `Approval.channel` widened from `Literal["tty"]` to `str` → `test_an_approval_record_not_made_by_the_command_is_rejected` fails;
  - the launcher treating exit 3 as an answer → both launcher tests fail;
  - `agentsmith approve` falling back to stdin → `test_an_agent_shell_cannot_record_an_approval` fails.

## Pass 1 — findings: 5

**Group 6**

- `ambiguous-signals`, `test-the-contract` — **finding:** the span's decision was inferred by matching
  `'"permissionDecision": "deny"'` in the text a hook had printed. A formatting change to that JSON would have
  relabelled every deny as an allow, silently. The code that decides now records the decision (`_record`), and a
  test asserts it from the exported span.
- `ambiguous-signals` — **finding:** every span was stamped `ide=claude`, including `commit-msg` and `ci` runs from
  a plain shell. It now reads `AGENTSMITH_IDE` (G2's adapters set it) and says `unknown` otherwise.

**Group 3**

- `gate-integrity` — **finding:** `.agenticframework/approvals.jsonl` is gated, so a design whose `scope` named it
  would have unlocked it — and an agent that can write that file can approve its own deviation. The edit gate now
  denies it whatever any design says, with a test that names it in a design's scope first.
- `declared-vs-enforced` — **finding:** `Extends` declared `stack_rules` and `test_command`, which nothing read. A
  tenant would have set them and believed they were in force. Dropped; `session_start` is wired into the
  session-start context instead, with a test.

**Group 2**

- `guards-must-be-able-to-fail` — **finding:** `agentsmith design new` pre-filled every pillar as
  `applies — TODO: <question>`, which the gate accepts. The skeleton now writes `TODO — <question>`, which is not a
  valid verdict, so the gate rejects it until a person answers.

Other levers in Groups 1–4, 6: OK (Group 5 and 7 n/a — no screen, no session).

## Pass 2 — findings: 3

- `when-the-fallback-fails` — **finding:** the spool exporter let `OSError` escape into the batch processor on a
  read-only or full state directory: a stack trace on a hook's stderr, and nothing saying spans were lost. It now
  returns `FAILURE` and reports `spool write failed: …` at session start (`test_a_spool_that_cannot_be_written_is_reported_not_raised`).
- `docs-match-behaviour` — **finding:** the design described span attributes as `gate.*` (the runtime namespaces
  them `agent.*`), claimed the repo's `.venv` was tried only in the framework checkout, and still listed the two
  `extends` keys that were dropped. Corrected, along with how `agent.ide` and the decision are obtained.
- `docs-match-behaviour` — **finding:** `docs/process-gates.md` did not say that the approvals file is never
  editable (and how to commit one), nor what session start now reports. Both added.

Every other lever re-checked over the final tree: OK.

## Pass 3 — findings: 0

- Every lever again, over the whole diff: the registry and its compilation, the records checks, the approval
  command, the launcher, the tracing spool, the generator, the workflow, and the docs.
- `one-catalog`: the CLI writes approvals through the gate's own `gate_models.Approval`, so the record written and
  the record accepted are one definition.
- `minimal-host-dependency`: the gate's needs are one file, `scripts/requirements-gate.txt`, which travels with the
  vendored gate and is what CI installs.
- `run-the-gates-ci-lists`: ruff, `scripts/test/`, `runtime/test/` and the curated mutation check were run; mypy is
  a declared gap below.
- Gates re-run after the last fix: see the sign-off.

## Pass 4 — findings: 2

Found while vendoring G1 into OTS (the tenant review, `OTS/.agent-rfc/reviews/governance-enforcement-tenant.md`),
fixed here because the code is the framework's, then re-vendored.

- `environment-parity` — **finding:** `generate-ide-config.py` defaulted the project name to a git-remote basename
  and the owner to `unknown@unknown`, while CI's drift check runs it with no arguments. A tenant's committed rule
  files could therefore only match CI's generation if they carried the placeholder. It now falls back to the repo's
  own `.agenticframework/tenant.yaml` (`tenant.name`, `tenant.owner`, `framework.version`)
  (`test_the_generator_reads_the_tenants_own_declaration`).
- `ambiguous-signals` — **finding:** session start listed every active design by name, including ones that unlock
  nothing (an unanswered pillar, an unapproved deviation). Listed by name, they read as in force. Each is now
  marked "INCOMPLETE, unlocks nothing: <reason>" (`test_session_start_says_which_active_designs_unlock_nothing`).

Also in this pass, `extends` regained `rules_extra` and `test_command` — this time consumed by the generator, which
renders a repo's own notes and test command into all six rule files, so tenant-specific instructions are generated
and drift-checked rather than hand-edited into a generated file
(`test_a_repos_own_notes_and_test_command_ride_in_every_generated_file`).

## Pass 5 — findings: 1

- `declared-vs-enforced` — **finding:** `AGENTSMITH_IDE` and `AGENTSMITH_PYTHON` are read by the gate and the
  launcher and were documented nowhere; the repo's own documentation gate caught it
  (`test_every_env_var_the_code_reads_is_documented`). Both are now in UserManual.md's runtime-flags table — an
  undiscoverable knob is not configurable, and `AGENTSMITH_PYTHON` is the fix people will need when a hook cannot run.
- Every other lever again over the final tree, including the two fixes above and the OTS vendoring.
- The vendored copies in OTS are byte-identical to this checkout (diffed per file in the tenant review).

## Pass 6 — findings: 0

- Final tree, every lever. `scripts/test/` 721 passed, `runtime/test/` 664 passed and 10 skipped, ruff clean.

## Pass 7 — findings: 1

Run after the handover, against the committed slice (`dde56b3`) rather than the working tree —
`process_gate.py ci` over the range a push would check, which the passes above had not covered.

- `two-owners-two-cadences`, `gate-integrity` — **finding:** the registry's design-time
  requirements were retroactive. `Config` defaults `registry` when the key is absent, so `ci`
  applied `## Pillars`, `## Deviations`, `## Dependencies` and the sign-off block to every commit
  in the range — including `685c296` and `4f8e26a`, made before G1 existed, whose designs could
  not have carried them. Self-Test's `process-gates` job would have failed on the next push, with
  no fix available short of rewriting history. Declaring `registry` in
  `.agenticframework/process-gates.json` is now what adopts those rules: a commit whose own config
  omits it is judged by the pre-registry sections, exactly as a repo that had not adopted the gates
  at all is (`PRE_REGISTRY_SECTIONS`). AgentSmith declares it, so G1 onward is held to it; OTS and
  KYC Sentinel adopt it with their own slices. Three tests pin it — history passes, an adopting
  config fails on all four requirements, and this repo is adopted — and three mutations (the flag
  ignored, the sign-off always required, adoption assumed) are each caught.

## Pass 8 — findings: 2

Both found by running the gate list CI actually runs, over the whole tree rather than the files
this slice touched (`run-the-gates-ci-lists`). Pass 6 and the sign-off had reported ruff and the
two suites only, so neither had been exercised since the last files were added.

- `run-the-gates-ci-lists`, `one-catalog` — **finding:**
  `test_security_registry.py::test_scripts_has_exactly_one_script_loader` failed:
  `test_generate_ide_config_governance.py` hand-rolled `spec_from_file_location` for the
  hyphenated generator, the fifteenth reinvention of the loader `_shared.load_script` exists to be.
  It uses the shared loader now.
- `docs-match-behaviour` — **finding:** the SPECS.md tree drift check failed —
  `scripts/gate_models.py`, `scripts/gate_tracing.py` and `scripts/requirements-gate.txt` were
  shipped without an entry, so the repo's own map did not describe three new files. All three
  added, with what they are for.

## Pass 9 — findings: 0

Whole gate list again on the final tree: `scripts/test/` and `runtime/test/` (1388 passed,
10 skipped), `ruff check .`, SPECS tree drift (93 second-level entries), `--check-hooks`,
`--check-kg`, the registry drift check, `bash -n` and ShellCheck on the installer and every hook,
and `process_gate.py ci` over `4ef685e..HEAD`. The curated mutation check runs against the commit,
since it rewrites tracked files.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_models.py (35), test_gate_tracing.py (7),
                          test_cli_approve.py (5), test_generate_ide_config_governance.py (10),
                          test_process_gate.py (+13)
Mutation-checked:          yes — four mutations, each reverted: pillar answers not required,
                          approval channel widened, launcher accepting exit 3, approval reading stdin
Fixtures re-pinned:        yes — templates/governance.json regenerated from agent-rules.yaml;
                          the gated-repo fixture now carries runtime/ and the registry, as a
                          vendored tenant does
Gates run locally:         ruff check . (clean), scripts/test/ and runtime/test/ (all pass),
                          scripts/mutation_check.py (curated: 66 of 67 caught; the one survivor
                          is pre-existing and in code this change does not touch — logged),
                          generate-ide-config.py --registry --check-only. Tree = the working tree CI would check out, apart from
                          being uncommitted.
Declared gaps:             (1) mypy could not run in this local venv — its numpy stub needs
                              Python 3.12+ syntax while the project pins python_version 3.11;
                              unrelated to this change, and CI runs it on the locked environment;
                          (2) KYC Sentinel's own CI runs the framework's gate with a bare
                              python3 and will exit 3 until it installs
                              scripts/requirements-gate.txt — logged in FIXES_AND_CLEANUP.md;
                          (3) closed 2026-09-16 — the owner recorded D3 (A-597cd675) and D4
                              (A-8ad5e81b) with `agentsmith approve` at a terminal; both ids are
                              in the design's `## Deviations`, and the gate resolves them;
                          (4) the OTS side (T1) and the other IDEs' hooks (G2) are separate
                              slices, so today only Claude Code's hooks call the new checks.
```

## Verified at handover — 2026-09-16

This session took the working tree over from the one that built G1 and re-ran the gate list
before committing, rather than trusting the record above: `ruff check .` clean; `scripts/test/`
and `runtime/test/` 1385 passed, 10 skipped; SPECS.md tree drift; `verify_system.py
--check-hooks`; `--check-kg` (it regenerated the graph for the new modules — the refreshed
`.agent-rfc/fixtures/knowledge_graph.json` is in this commit, so CI's single run sees it current);
`generate-ide-config.py --registry --check-only` (registry matches `agent-rules.yaml`);
`bash -n` on the installer and every hook; ShellCheck 0 warnings. The stop gate passes on this
tree. The curated mutation check runs against the commit, since it rewrites tracked files.
