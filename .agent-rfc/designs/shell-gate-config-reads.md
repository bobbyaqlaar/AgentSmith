---
status: active
scope:
  - scripts/gate_shell.py
  - scripts/test/test_gate_shell.py
---
# The shell pre-check reads `git config` the way git does

## Problem

The G2b shell pre-check (`scripts/gate_shell.py`, design `.agent-rfc/designs/governance-enforcement.md`)
refuses a read as if it were a write. Observed 2026-09-18 in KYC Sentinel: `git config core.hooksPath`
— asking what the hooks path is — was refused with "`git config core.hooksPath <empty>` points this
repo away from .githooks". `git config --get core.hooksPath` and `--get-all` were refused the same way.

The cause is in `_git_refusal`'s `config` branch: it drops every word starting with `-`, so it
cannot tell `--get` from `--add`, and it reads "no value after the key" as "the empty value". A
query and a write that empties the setting look identical to it.

A gate that refuses the question "is this repo armed?" teaches the agent that the gate is noise,
and pushes the check into a place the gate cannot see (a script, `bash -c`). Refusing the wrong
thing is how a gate gets turned off.

Found while tracing the same function: the subcommand is "the first word not starting with `-`",
so a global option that takes a separate value is read as the subcommand. `git -C ../kyc commit
--no-verify` and `git -c user.name=x commit --no-verify` both pass — the subcommand is taken to
be `../kyc` and `user.name=x`. Same function, same parse, fixed here.

Found in review pass 1 (`.agent-rfc/reviews/shell-gate-config-reads.md`), the same flaw one level
up and one level across: `refusal` took the first word of a segment as the program, so
`GIT_EDITOR=true git commit --no-verify` or `env git push --no-verify` skipped every check; the
`-c` check matched two spellings of the key where git reads it case-insensitively, and missed
`--config-env=core.hooksPath=…` and `GIT_CONFIG_KEY_<n>=core.hooksPath` / `GIT_CONFIG_PARAMETERS`,
which are `-c` by another route.

## Approach

**Find the subcommand the way git does.** Skip global options, and skip the value after the ones
that take a separate value (`-C`, `-c`, `--git-dir`, `--work-tree`, `--namespace`,
`--config-env`, `--super-prefix`). The first word after that is the subcommand. The
`-c core.hooksPath=…` check still runs over every argument first.

**Read past what is in front of a command.** `NAME=value` words and `env` before the program are
the command's environment, not the command (`_environment_and_command`). A `GIT_CONFIG*`
assignment naming `core.hooksPath` is refused as `-c` is. The `-c` check lowercases the argument
and strips a `--config-env=` prefix before matching.

**Parse the `config` arguments by what they do**, using only the words after `config`:

- Options that take a separate value (`--file`/`-f`, `--blob`, `--type`, `--default`,
  `--comment`, `--value`, `--url`) consume the next word, so a file path is never mistaken for a
  key or a value.
- git ≥ 2.46 subcommand forms (`get`, `list`, `set`, `unset`, `remove-section`, `rename-section`,
  `edit`) are read as the verb when they are the first operand; `get` and `list` are reads.
- **Removals of the setting** — `--unset`, `--unset-all`, `unset` naming `core.hooksPath`, and
  `--remove-section`/`--rename-section`/`remove-section`/`rename-section` naming the `core`
  section — are refused: with no hooks path git runs `.git/hooks`, which holds none of the gates,
  so the gate is off. Checked before reads, so a malformed mix (`--get --unset`, which git itself rejects) is
  refused, not passed.
- **Reads** — `--get`, `--get-all`, `--get-regexp`, `--get-urlmatch`, `--list`/`-l`, `get`,
  `list`, or the key with no value after it — return None. `--show-origin`, `--show-scope`,
  `--global`, `--local` are flags that change neither.
- **Writes** — the key followed by a value (plain, `--add`, `--replace-all`, `set`, with any scope
  flag) — are refused unless the value is the repo's hooks path, as today. `''` is a value, not
  an absent one, so `git config core.hooksPath ''` stays refused.

Key and section names are case-insensitive in git and are compared lowercased.

**Stated limit, unchanged in kind:** `git config --edit` opens an editor on the whole file, and a
write straight into `.git/config` never names `core.hooksPath` on the command line. Neither is
read here — the same class as `bash -c "$(…)"`, as are an `export GIT_CONFIG_…` on an earlier
line and `env` given options of its own — and the sweep re-arms an unset hooks path
whatever did it. Written into `docs/process-gates.md` beside the existing limit.

## Pillars

- P1 applies — this note precedes the code: `.agent-rfc/designs/shell-gate-config-reads.md`, scope `scripts/gate_shell.py` and its test.
- P2 n/a — no dependency added; the parse is the standard library `shlex` tokenisation already in `_segments`.
- P3 n/a — `refusal` is a pure function; the hook that calls it already reports through its existing path.
- P4 applies — failing tests first in `scripts/test/test_gate_shell.py`: reads allowed, each write form refused, `--unset` and `--remove-section core` refused, `-C`/`-c` before the subcommand, an environment prefix before the program.
- P7 applies — typed helpers in `scripts/gate_shell.py` (`_subcommand_at`, `_config_refusal`) with `Optional[str]` returns, matching `_git_refusal`, and `_environment_and_command` returning a typed `Tuple`.
- P8 n/a — no telemetry wiring.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 applies — the command line is text an agent wrote; `_segments` tokenises it as data and `_config_refusal` only classifies words, never evaluates them.
- P12 n/a — no credentials.
- P13 applies — narrowed only where git itself reads (`--get`, no value); every write refused before is still refused (`test_a_command_that_skips_the_gate_is_refused` keeps its cases), and `--unset`, `--remove-section core`, `git -C … commit --no-verify` are newly refused.
- P14 applies — the expected verdicts are literal command lines in `scripts/test/test_gate_shell.py`, not recomputed from the parser.
- P15 applies — "no value" (a read) and "the empty value" (a write) were one signal; `_config_refusal` separates them, and the refusal names which write it saw.
- P16 applies — a line that does not tokenise still falls back to the crude split in `_segments`; the config parse on that output refuses writes the same way, so a parse failure never passes a write.

## Deviations

none

## Dependencies

None added.

## Levers

- `guards-must-be-able-to-fail` — each write form and each removal has a test that must be refused, beside the reads that must pass.
- `ambiguous-signals` — "no value after the key" and "an empty value" were read as one thing.
- `grep-for-siblings` — the subcommand parse the config branch sits on had the same flaw (options read as words); `git -C` and `git -c` before the subcommand fixed with it.
- `declared-vs-enforced` — `git config --edit` and direct writes to `.git/config` are written down as unread, not implied covered.
- `docs-match-behaviour` — `docs/process-gates.md`'s shell-surface table says reads pass and removals are refused.
