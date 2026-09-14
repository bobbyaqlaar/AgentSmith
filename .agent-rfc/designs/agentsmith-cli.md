---
status: done
scope:
  - install-ai-stack.sh
  - runtime/cli.py
  - runtime/machine/**
  - runtime/llm_gateway.py
  - runtime/models.yaml
  - runtime/otlp.py
  - runtime/test/**
  - pyproject.toml
  - hooks/pre-commit
  - hooks/commit-msg
  - hooks/post-commit
  - hooks/post-checkout
  - templates/shell/**
  - templates/agent-rules.yaml
  - templates/onprem-deploy/README.md
  - enterprise/**
  - scripts/**
  - portal/lib/**
  - portal/app/**
  - runtime/k8s/**
  - docker-compose.yml
  - workflow-templates/**
  - .github/workflows/self-test.yml
  - .github/workflows/release.yml
---
# One `agentsmith` command, machine state in a file (slice B)

## Problem

`install-ai-stack.sh` Step 7 appends 18 shell functions and 4 exports to
`~/.zshrc` (or `.bashrc`/`.profile`). Verified 2026-09-14:

1. **They exist only in an interactive shell.** Git GUIs, IDEs, CI, containers
   and Claude Code's desktop-app hooks never source the profile. `ai-mode-hybrid`
   exports `AI_STACK_MODE` into one terminal; the gateway
   (`runtime/llm_gateway.py:_active_profile_name`) and the hooks read the
   environment, so every other process silently runs the default profile.
2. **The org bypass policy is not enforced.** `ai-stack-off` checks
   `bypass_policy` and the break-glass token, but all four hooks exit on
   `DISABLE_AI_STACK=true` from any environment, and `hooks/pre-commit` prints
   that very command as the bypass. The control is a speed bump on one path.
3. **Untested logic in the profile.** `ai-stack-upgrade` (~200 lines, tested
   only by extracting it from the heredoc), `ai-stack-uninstall`, `ai-stack-scrub`,
   `ai-tenant-promote`, the break-glass HMAC check and the audit-log writer
   exist only as zsh text. Re-installing skips them unless `--force`, so
   machines run stale copies (this Mac's block says v1.1.0).
4. **Dead and harmful exports.** `OS_LLM_BASE_URL`/`OS_LLM_API_KEY` have no
   reader anywhere. `AGENT_PHOENIX_ENDPOINT`/`PORT` duplicate code defaults. The
   existing `agentsmith shellenv` emits `AI_STACK_MODE` exports that, evaluated
   in a profile, would pin the mode forever.
5. **Siblings.** `ai-mode-local`/`-hybrid` set git's global `init.templateDir`
   even on a `--mode enterprise` install, which promises not to.
   `ai-test-evals`, `ai-stack-promote` and `ai-tenant-promote` run
   `python3 scripts/X.py || python3 ~/.agent-framework/scripts/X.py`, so a
   tenant script that FAILS is silently re-run from the framework copy — an
   eval gate can pass on the wrong code. `agentsmith doctor` finds
   `verify_system.py` beside the installed package, where it never is.
6. **After slice A** the profile's `python3` calls use the system interpreter,
   which no longer has the framework's packages.

## Approach

### The command

`agentsmith` (console script of `agentsmith-runtime`, already declared) gains
every operator command. Logic moves to a new package `runtime/machine/`
(added to `pyproject.toml` packages; stdlib-only at import time):

| Shell function | Command |
|---|---|
| `ai-mode-local` / `ai-mode-hybrid` / `ai-stack-off` | `agentsmith mode local\|hybrid\|off` (no argument: print) |
| `ai-stack-check` / `ai-stack-status` | `agentsmith check` / `agentsmith status` |
| `ai-stack-judge-model` / `ai-stack-required-models` | `agentsmith models [--judge\|--ollama]` |
| `ai-dashboard-start` / `-stop` | `agentsmith dashboard start\|stop` |
| `ai-test-evals` / `ai-stack-promote` | `agentsmith evals` / `agentsmith promote <id> <query> <output>` |
| `ai-tenant-init` / `ai-tenant-promote` / `ai-onprem-deploy-scaffold` | `agentsmith tenant init\|promote\|onprem-scaffold` |
| `ai-stack-upgrade` | `agentsmith upgrade [--to V]` |
| `ai-stack-scrub` / `ai-stack-uninstall` | `agentsmith scrub [DIR] [--yes]` / `agentsmith uninstall [--yes] [--purge]` |
| (new, for hooks) | `agentsmith hooks bypass-check` |

Modules: `state.py` (framework home, script lookup, and the mode,
install-mode and dashboard-endpoint files), `policy.py` (org policy, break-glass token, audit log,
bypass decision), `ops.py` (check, status, models, dashboard, evals, promote,
tenant promote, onprem scaffold, scrub, uninstall, profile-block removal),
`upgrade.py`. `shellenv` is removed (point 4). The desktop notification on a
mode switch is dropped.

Script lookup (`evals`, `promote`, `tenant promote`): the tenant's
`scripts/X.py` if it exists, else `~/.agent-framework/scripts/X.py` — never
both; run with the framework environment's interpreter (`sys.executable`).
`doctor` uses the same lookup.

### Machine state in files

`~/.agent-framework/state/` (overridable by `AGENTSMITH_STATE_DIR`, for test
isolation and sandboxes; hooks honour it too):

- `mode` — one word, `local`, `hybrid` or `disabled`, written by `agentsmith
  mode`. Absent means "not chosen".
- `phoenix-endpoint` — written by `agentsmith dashboard start`, removed by
  `stop`. `runtime/otlp.py` reads it after the environment: the profile used to
  export `AGENT_PHOENIX_ENDPOINT` into every shell, and `ai-dashboard-start`
  exported `OTEL_EXPORTER_OTLP_ENDPOINT`, so dropping both without a
  replacement would silently stop local trace export.
- `install-mode` — `developer` or `enterprise`, written by the installer.
  `agentsmith mode local|hybrid|off` touch `init.templateDir` only on
  `developer`.

**Precedence** for the model profile (`_active_profile_name`):
`AGENT_MODEL_PROFILE` → `AI_STACK_MODE` in the environment → the `mode` file
(if it names a profile) → the registry's `default_profile`. The environment
still wins, so a one-off run and CI keep working; the file is what every other
process on the machine now sees. `runtime/test/conftest.py` points
`AGENTSMITH_STATE_DIR` at an empty directory, so a developer's mode never leaks
into the suite (the security harness delegates to those suites and inherits it).

### Hooks: bypass decided in one place

The four hooks replace `if DISABLE_AI_STACK=true; exit 0` with one shared block:
a bypass is requested by `DISABLE_AI_STACK=true` or a `disabled` mode file;
with no org policy file it is granted (today's behaviour); with one, the hook
asks `~/.agent-framework/.venv/bin/agentsmith hooks bypass-check`, which
applies `bypass_policy` (`disabled` → refuse; `break-glass` → a valid, unexpired
`AI_BREAK_GLASS_TOKEN`) and writes the audit event. Refused — or the command
missing — the hook runs as normal and says so: the failure mode of the check is
enforcement, not bypass. A test parses all four hooks for the identical block.
`agentsmith mode off` applies the same decision before writing the file.

### Installer

- Step 3: after the lock sync, install the framework package into the
  environment without dependencies (`--no-deps`: the lock already carries them)
  from the checkout, else from `git+$FRAMEWORK_REPO@v$FRAMEWORK_VERSION`; link
  `~/.local/bin/agentsmith` to it. If `~/.local/bin` is not on PATH, print the
  one line to add — the installer does not edit a shell profile.
- Step 7 (was: write shell functions) becomes: write `state/install-mode`;
  remove a legacy managed block from `.zshrc`/`.bashrc`/`.profile` via
  `agentsmith uninstall --legacy-profile-only` (one implementation, in
  Python; a backup `*.agentsmith-bak` is kept); warn, never edit, if an
  unmarked legacy block is found. `--force` is accepted and ignored with a
  notice.
- `templates/shell/ai-compat.sh`: optional one-line `ai-*` wrappers around the
  new commands, copied to `~/.agent-framework/shell/`, never sourced by the
  installer. A test checks each wrapper names a real subcommand. Removal is
  backlogged for the next minor release.
- Step 9 checks `agentsmith version` runs and no managed block remains; the
  closing next-steps name the new commands.

### Messages and docs

Every user-facing `ai-*` mention in code (hooks, scripts, runtime, portal/lib,
docker-compose, workflow templates, enterprise, templates) and docs
(UserManual §17 stays the canonical table, OPERATIONS, SPECS, README,
enterprise/README, CHANGELOG with **Hook interface change**, FIXES_AND_CLEANUP,
DemoScript.md) moves to `agentsmith`. `test_env_var_documentation`'s
"every command is in §17" check reads the CLI parser instead of the installer.

## Levers

- `declared-vs-enforced` — `bypass_policy` is now read by the hooks themselves, not only by the one command that sets a bypass.
- `guards-must-be-able-to-fail` — the bypass check failing to run (binary missing, policy unreadable) leaves the hooks enforcing.
- `provenance-and-precedence` — the profile's precedence (explicit profile → env → mode file → registry default) is written down and tested.
- `environment-parity` — state in a file reaches GUI, IDE and hook processes the same as a terminal; tests isolate it explicitly.
- `single-source-of-truth` — the bypass decision, profile-block removal and script lookup each have one implementation.
- `pin-unremovable-duplicates` — the hooks' shared bypass block and the compat wrappers are pinned by tests that parse them.
- `grep-for-siblings` — enterprise install mode vs `init.templateDir`, the failing-script `||` re-run, and `doctor`'s script path.
- `no-redundant-artifacts` — dead exports, `shellenv` and the profile heredoc go.
- `minimal-host-dependency` — no shell profile; `~/.local/bin` on PATH is the one host expectation, and the installer says when it is missing.
- `docs-match-behaviour` — every `ai-*` reference in code and docs moves with the commands.
- `implemented-not-invoked` — hooks call `bypass-check`, the gateway reads the mode file, the installer installs and links the command.
