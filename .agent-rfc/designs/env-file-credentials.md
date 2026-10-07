---
status: done
scope:
  - runtime/config.py
  - runtime/worker.py
  - scripts/_shared.py
  - scripts/verify_system.py
  - runtime/test/**
  - scripts/test/**
  - scripts/mutation_check.py
---
# A repository's `.env` wins for its credentials

The owner asked on 2026-10-07 to eliminate the risk of a stale API key exported in a shell
silently replacing the one a repository's `.env` declares.

## Problem

Measured on 2026-10-07:

- **For credentials the ambient shell wins, silently.** `runtime.config.load_env_file` mirrors
  `.env` into `os.environ` only where a variable is not already set, and every credential reader —
  the gateway, `provider_dispatch`, `cost_router`, the eval judge — reads `os.environ`. So an
  `export GEMINI_API_KEY=…` in a profile, an old terminal or a one-off command beats the key the
  repository's `.env` declares, and nothing says so. A stale or revoked key surfaces as a judge
  that "did not answer" — under the evals contract, a `no_verdict` a tenant may have declared a
  warning — or as calls billed to the wrong account.
- **The module says the opposite for everything else.** Its stated precedence puts `.env` above the
  ambient environment ("an accidental export must not beat a declaration"), and `resolve()` honours
  it for configuration keys, recording what it ignored in `shadowed_env()`. Its docstring exempts
  secrets on the grounds that "an API key has no declaration anywhere" — true when no file names
  the key, wrong when `.env` does.
- **The script-only loader** (`scripts/_shared._load_dotenv_standalone`, a deliberate mirror for
  processes without `runtime/`) has the same rule.
- **Nothing reports it.** `agentsmith doctor` (`scripts/verify_system.py`) does not look at shell
  profiles or at a shell credential that differs from the repository's `.env`; and
  `runtime/worker.py` prints each shadowed value with `repr`, so recording a credential there
  as-is would print the secret.

## Approach

- **A credential `.env` declares wins over the ambient shell.** In `load_env_file`, a key that
  names a credential — `API_KEY`, `TOKEN`, `SECRET` or `PASSWORD` as a whole `_`-separated part of
  its name (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY_JUDGE`, `OPS_PORTAL_SYNC_TOKEN`) — is written into
  `os.environ` from `.env` when the shell holds a different value, so every reader sees the
  declared key. Other keys keep today's mirror (the shell is not overwritten); `resolve()` already
  gives them the declared precedence.
- **The documented exception still works**: a key named in `tenant.yaml`'s `env_overrides` lets the
  shell win, as it does for configuration.
- **It is said, never shown.** The shadowing is recorded in `shadowed_env()` with a placeholder
  instead of the value, and the loader prints one line to stderr per key per process naming the
  variable, the file and the way to let the shell win. The worker's startup note does not `repr`
  a credential.
- **The script-only mirror follows the same rule**, reading `env_overrides` when YAML is importable
  and treating it as empty when not; a test holds its credential pattern to the runtime's.
- **`agentsmith doctor` reports** (warnings, never failures): credentials exported in `~/.zshrc`,
  `~/.zprofile`, `~/.zshenv`, `~/.bashrc`, `~/.bash_profile` and `~/.profile`, by file, line and
  name; and credentials in the current shell that differ from this repository's `.env`, by name.
  No value is printed or compared outside the process.
- **CI and deployments are unaffected by construction**: neither has a `.env` (it is gitignored, and
  KYC's image build fails on a credential in the image), so their credentials still arrive from
  secrets through the environment. A `.env` baked into an image would now win for credentials,
  which is the declaration winning, as everywhere else.

**Deliberately not done:** extending `.env`-wins to every key mirrored into `os.environ` — a wider
change to what third-party libraries see, not what the owner asked for.

## Pillars

- P1 applies — `.agent-rfc/designs/env-file-credentials.md` records the measured gap and the owner's request before code changes.
- P2 applies — `runtime/config.py` keeps one loader and one precedence; `scripts/_shared.py`'s standalone mirror is pinned to it by a test.
- P3 n/a — no traced code changes.
- P4 applies — `runtime/test/test_config.py` and `scripts/test/test_standalone_without_runtime.py` cover a shadowed credential, a permitted override, a non-credential left alone, and no value in any output; mutations restore the old mirror and print a value.
- P7 n/a — no Pydantic or async changes.
- P8 n/a — no telemetry wiring.
- P9 n/a — no orchestration.
- P10 applies — `runtime/config.py` decides which provider key the gateway and the eval judge call with; the declared one now.
- P11 n/a — no untrusted content.
- P12 applies — `runtime/config.py` makes the repository's declared credential win over an ambient one, and no credential value is printed, logged or recorded.
- P13 n/a — no gate changes.
- P14 n/a — no fixtures.
- P15 applies — `runtime/config.py` says which credential was overridden instead of a judge that silently did not answer.
- P16 applies — `runtime/config.py` keeps `env_overrides` as the reviewed route for a deliberate shell override.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — `.env` is declared to outrank the shell; for credentials it now does.
- `provenance-and-precedence` — the loader knows which channel a credential came from, and the declared one wins.
- `channel-precedence` — one stated order for `.env` and the shell, now the same for credentials as for configuration; every message names the variable, never the value.
- `pin-unremovable-duplicates` — the standalone loader's credential rule is held to the runtime's by a test.
