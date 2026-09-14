# Review — one `agentsmith` command, machine state in a file (slice B)

Design: `.agent-rfc/designs/agentsmith-cli.md`. Reviewed against
`docs/review-levers.md`, scoped by what the branch ships: `runtime/machine/`,
`runtime/cli.py`, the gateway and OTLP precedence changes, all four hooks, the
installer's Steps 3/7/9, the compat wrappers, every renamed reference in code,
templates, enterprise, portal and docs, and the Self-Test gates.

Built evidence before review:
- the real installer on this Mac: package installed into
  `~/.agent-framework/.venv`, linked at `~/.local/bin/agentsmith`,
  `state/install-mode` written, the 830-line block removed from `~/.zshrc` with
  every other line kept (diffed against a copy taken first; `.agentsmith-bak`
  identical to it; `zsh -n` clean);
- from `env -i` with no profile: `agentsmith version|mode|models|status` run;
  `agentsmith mode local` wrote `state/mode`, and a bare Python process's
  `_active_profile_name` picked `local` over a registry default of `hybrid`;
- the real templates in a fresh `git init`: a normal commit passes, a
  guardrail violation is blocked, `DISABLE_AI_STACK=true` bypasses (no policy);
- `test_hook_bypass.py` end to end through the real CLI: a `disabled` policy
  refuses the bypass, the hook runs, and the audit fallback log records it;
- full suite 1307 passed (3.14); on a Python 3.11 venv built from the lock,
  1297 passed with 8 `test_scratch_tenants` failures that are that venv's
  artefact (the test symlinks `python3` to `sys.executable`, and a symlinked
  venv interpreter loses its site-packages) — CI uses a real interpreter;
  mypy clean on 3.11; `ruff check .`; `bash -n`/`zsh -n`; ShellCheck 0 warnings;
  SPECS tree drift; `verify_system.py --check-hooks`/`--check-kg`;
  `mutation_check.py` only its known local survivor (FIXES_AND_CLEANUP.md);
- found while building, each with a test: installer messages whose backticks
  would have EXECUTED `agentsmith …` as command substitution
  (`test_no_output_string_runs_a_command_by_accident`); a tenant's own
  `runtime/` shadowing ours when the upgrade test ran with the working
  directory on `sys.path`;
- 16 mutations of the new behaviour (hook policy check, checker failure,
  disabled/unreadable policy, token expiry, gateway and OTLP fallbacks, enterprise
  git config, script lookup order, blank-line removal, upgrade's status check,
  state-dir override, tenant_created, mode off policy, installer package step,
  profile removal) — 15 caught.

## Pass 1 — findings: 7

- `test-that-cannot-fail` — the 16th mutation survived: `state_dir()` ignoring
  the process's `AGENTSMITH_STATE_DIR`. The test compared against the fake
  HOME's default, which is what the broken code also returned. It now sets the
  process override somewhere else first; the mutation is caught.
- `no-redundant-artifacts` — `state.write_install_mode` had no caller outside
  the tests: the installer writes the file with `printf`. Removed; the tests
  write the file the way Step 7 does.
- `minimal-host-dependency` — found running the real installer: installing the
  package from the checkout leaves setuptools' in-tree `build/` in the checkout,
  untracked and not ignored — one `git add -A` from being committed. Removed it
  and ignored `/build/` (root only; no tracked path contains one).
- `grep-for-siblings` — the doc sweep turned up `tenant_created`: OPERATIONS.md,
  the portal's audit route and its event types all name
  `tenant init → tenant_created`, and nothing had written it since the scaffold
  moved out of the shell profile. `agentsmith tenant init` now records it when
  it writes `tenant.yaml`; tested once-only.
- `gate-integrity` — `test_documented_env_vars_exist` counts any tracked `.txt`
  as code, so the legacy-profile fixture made `OS_LLM_BASE_URL` look read while
  nothing reads it. Fixture renamed `.zshrc`; the two removed names go in the
  test's ALLOWED list with the reason, and SPECS.md's row is gone.
- `docs-match-behaviour` — `templates/agent-rules.yaml` told every generated
  CLAUDE.md/.cursorrules that the dashboard sets `OTEL_EXPORTER_OTLP_ENDPOINT`
  in the shell. Now names the recorded endpoint. enterprise/README.md also now
  says that an MDM machine with the hook bundle but no `agentsmith` refuses every
  bypass, break-glass included.
- `ambiguous-signals` — `agentsmith status` printed `Hooks: muted` whenever a
  bypass was requested, including under an org policy that refuses it. It now
  says the policy decides, and — tested — records no audit event for looking.

Also added `scripts/test/conftest.py`: a run collecting only `scripts/test/`
had no state isolation (646 passed with this Mac's mode file present).

Not changed: KYC Sentinel's `models.yaml` and OTS's copied workflow still
mention `ai-mode-*`/`ai-tenant-init` in comments — tenant-owned copies that move
on their own cadence. `agentsmith dashboard start` records the endpoint when it
launches a standalone Phoenix even if that process later dies — as the shell
export did; `agentsmith check` reports Phoenix offline.

## Pass 2 — findings: 3

Re-read `runtime/machine/` line by line against the levers, and ran the
commands the manual now advertises.

- `docs-match-behaviour` / `implemented-not-invoked` — `agentsmith doctor
  --check-kg`, the form UserManual.md §17 documents, failed with argparse's
  "unrecognized arguments": a positional with `nargs="*"` never receives an
  option-looking token. Pre-existing since the command was added; reproduced
  from `~/.local/bin/agentsmith`. `main` now forwards unknown arguments to
  `doctor` only and still rejects them everywhere else; tested, mutation caught.
- `guards-must-be-able-to-fail` — `bypass_decision` read any `bypass_policy`
  value other than `disabled`/`break-glass` as "no restriction", so a typo
  (`disable`) in an enterprise policy granted every bypass. An unrecognised value
  now refuses; a policy file with no `bypass_policy` still restricts nothing.
  enterprise/README.md and OPERATIONS.md §G.4 list both rows. Tested, mutation
  caught.
- `out-of-order-and-repeated` — `dashboard stop` sent SIGTERM to the process
  group named in `state/phoenix.pid` without checking it: after a reboot, or
  once the number is reused, that is some other process group. It now signals
  only if `ps` still shows a Phoenix command, else falls back to the pattern
  kill. Tested with a live non-Phoenix pid; mutation caught.

## Pass 3 — findings: 1

Re-ran the real installer a second time (exit 0, `~/.zshrc` byte-identical,
nothing untracked left in the checkout), `agentsmith doctor --check-hooks` from
the checkout (passed), and the gate list on 3.14 and on a 3.11 venv from the lock
(1291 passed with the venv-artefact scratch test deselected; mypy clean).
Re-read the installer's Steps 3 and 7 as built.

- `docs-match-behaviour` / `provenance-and-precedence` — Step 7's warning for a
  block it could not remove said the functions "shadow nothing". The block
  exports `AI_STACK_MODE`, which outranks `state/mode`, so every shell that loads
  it pins the mode — the one thing slice B exists to stop. The warning now says
  so, and the success path notes that terminals opened before the install carry
  that export until they close.

## Pass 4 — findings: 0

Full suite, `ruff check .`, `bash -n`/`zsh -n` on the installer, hooks, compat
file and enterprise scripts, ShellCheck (0 warnings), SPECS tree drift and
`verify_system.py --check-kg` after the last edit. Re-read the CHANGELOG entry,
UserManual §1/§16/§17, SPECS §3/§5/§6/§7, OPERATIONS §0/§1/§8/§9/§10/§G.4,
enterprise/README.md and the three new FIXES_AND_CLEANUP.md entries against
`runtime/machine/` and the installer as built; each command the manual lists
parses (`test_every_shipped_command_is_in_the_canonical_reference`).
