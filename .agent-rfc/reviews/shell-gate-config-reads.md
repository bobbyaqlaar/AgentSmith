# Review — the shell pre-check reads `git config` the way git does

Design: `.agent-rfc/designs/shell-gate-config-reads.md`. Owner's instruction, 2026-09-18: stop
`scripts/gate_shell.py` refusing read-only `git config core.hooksPath` queries (observed in KYC
Sentinel), keep every write refused, refuse `--unset core.hooksPath`.

**Built evidence (2026-09-18):**

- **Cause confirmed before the fix.** 20 of the new cases failed against the old code: every read
  form (`git config core.hooksPath`, `--get`, `--get-all`, `get`, `--show-origin`, `--file x`,
  `--default x --get`), `--remove-section core`/`--rename-section core`, and `git -C`/`git -c`
  before `commit --no-verify`. `--unset core.hooksPath` was already refused — by the bug, as
  "`<empty>`" — and is now refused on purpose, with a reason that says what it does.
- **Tests first**, `scripts/test/test_gate_shell.py`: reads pass; every write form refused
  (plain, `--add`, `--replace-all`, `--global`, `--local`, `--file`/`-f`, `--type`, `set`,
  `set --all`, `-C` before `config`); removals refused; positive controls (`--unset user.name`,
  `--remove-section alias`, re-arming with `--add`/`set`) pass.
- **Mutation checks by hand**, each reverted: 15 mutants over the new code — no read check,
  no-value-as-write, no unset check, no section check, reads before removals, no `config` option
  skip, no verb pop, no global option skip, no env skip, no `env` word, no `GIT_CONFIG*` check,
  case-sensitive `-c`, no `--config-env=` prefix, re-arm refused, any section name. **15 of 15
  caught.** Two removal cases were added before the run for "no `config` option skip"
  (`-f .git/config unset core.hooksPath`, `--file .git/config --remove-section core`): no
  existing case could see it — without the skip the file path takes the verb's slot, and
  `unset` is then read as an operand.

## Pass 1 — findings: 3

`grep-for-siblings` over `refusal` and `_git_refusal` — the same "first word is the thing"
reading, one level up and across. Each reproduced before fixing:

- **finding:** `GIT_EDITOR=true git commit --no-verify`, `env git push --no-verify` and
  `X=1 rm .githooks/commit-msg` were all allowed — `refusal` took `NAME=value` or `env` as the
  program, so one assignment in front skipped every check. Fixed: `_environment_and_command`.
- **finding:** `git -c Core.HooksPath=/dev/null commit` and
  `git --config-env=core.hooksPath=E commit` were allowed — the `-c` check matched two spellings
  of a case-insensitive key and not the `--config-env=` form. Fixed: lowercased, prefix stripped.
- **finding:** `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null
  git commit` and `GIT_CONFIG_PARAMETERS=…` were allowed — `-c` from the environment. Fixed: a
  `GIT_CONFIG*` assignment naming the key is refused.

Failing tests first for each (`test_every_spelling_of_hooks_off_for_one_call_is_refused`,
`test_an_environment_prefix_does_not_hide_the_command`: 9 failed, then passed), with
`test_an_environment_prefix_on_ordinary_work_is_not_refused` as the positive control.

## Pass 2 — findings: 2

`test-the-contract` on the refusal text, read as a user would see it:

- **finding:** after pass 1 the `-c` refusal quoted "`git core.hooksPath=/dev/null`" — the `-c`
  was lost when the message was shared with `--config-env`. It now quotes the command as typed.
- **finding:** the removal reason said `.git/hooks` "is empty"; it holds git's `*.sample` files.
  The claim that matters is that it holds none of the gates — reworded in the code, the design,
  `docs/process-gates.md` and the test docstring.

`test_the_reason_quotes_what_it_refused` pins all three message shapes.

## Pass 3 — findings: 1

- `no-redundant-artifacts` — **finding:** the module docstring line extended for the stated limit
  ran to 120 characters; reflowed.

Also checked in this pass, no finding:

- `docs-match-behaviour` — `docs/process-gates.md`'s shell-surface table has rows for the `-c`
  spellings, every write form and every removal; the read forms and the env/global-option
  reading are stated under it; the stated limit names `--edit`, `.git/config`, an earlier
  `export` and `env`'s own options.
- `declared-vs-enforced` — those four are written down as unread, in the module docstring and
  the doc, not implied covered. The sweep re-arms an unset hooks path whatever did it.
- `guards-must-be-able-to-fail` — every branch of `_config_refusal` and the two new parse
  helpers has a mutant that fails a test (above).
- `ambiguous-signals` — "no value" and `''` are separate cases (`git config core.hooksPath ''`
  is still refused; `git config core.hooksPath` passes).
- `environment-parity` — the new tests are pure calls to `refusal`; no git binary or version
  needed, so they read the same in CI.

## Pass 4 — findings: 0

Every lever group that `--impact` names (2, 4, 6) over the final diff, with the full test run and
`gates run` below. Considered and declined:

- `GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=.githooks git …` is refused though it
  re-arms for one call. Matching KEY to VALUE by index is more parser for a form nobody types;
  the refusal says what to run instead.
- `env -i git …` / `env -u X git …`: `env`'s own options still hide the command. Stated limit,
  not parsed — the same class as `bash -c`.
- Registering `gate_shell` in `scripts/mutation_check.py`. The hand mutants above are recorded;
  a suite there is its own change.

## Pass 5 — findings: 2

The commit gate refused the first commit attempt — `run-the-gates-ci-lists`: pass 4 ran
`gates run` but not the commit gate's own checks on the staged change.

- **finding:** the new case `FOO=bar agentsmith approve .agent-rfc/designs/x.md D1` reads as a <!-- xref: example -->
  pointer into a design that does not exist. It is a deliberate example; it carries the
  `xref: example` marker the rule names.
- **finding:** the Sign-off's `KG query:` was computed while the design and this record were
  untracked, so `--impact` did not count them. Recomputed with the change staged.

## Pass 6 — findings: 0

The commit gate over the staged change, `--impact` re-run on it, `test_gate_shell.py` (104
passed) and `verify_system.py --check-kg` after the edit.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_shell.py (9 tests added, 63 cases; 41 → 104)
Mutation-checked:          yes — 15 hand mutants over the new code, 15 caught, all reverted
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:76d20e7d1d60
Gates run locally:         the full pytest run (1754 passed, 10 skipped), `python3 -m
                          runtime.cli gates run`: 13 passed, 0 failed, 6 skipped (they
                          need services)
Declared gaps:             `git config --edit`, direct writes to `.git/config`, an earlier
                          `export GIT_CONFIG_…`, `env` with options — stated limits in
                          docs/process-gates.md, caught by the sweep
```
