---
status: done
scope:
  - runtime/cli.py
  - runtime/config.py
  - runtime/sync.py
  - runtime/adopt.py
  - scripts/generate-ide-config.py
  - scripts/mutation_check.py
  - runtime/test/**
  - scripts/test/**
---
# The tenant's IDE is chosen once and recorded, not assumed four times

## Problem

`tenant init` writes a hook config for every IDE in `gate_ides.GENERATED` —
today `claude` and `cursor` — whatever the tenant actually uses. A team on
Cursor is given `.claude/settings.json` it never opens; a team on Claude Code is
given `.cursor/hooks.json`. Both are committed, both enter
`.agenticframework/scaffold.json`, both are vouched, and both are rewritten by
every `agentsmith sync`. Nobody has asked for the choice because there has been
no way to express it.

The same four-line loop over the same constant appears at four sites:

- `runtime/cli.py:610` — `tenant init`
- `runtime/sync.py:181` — `agentsmith sync`
- `runtime/adopt.py:485` — `tenant adopt`
- `scripts/generate-ide-config.py:244` — `--hooks`, a manual generator on no CI path

Why this matters beyond tidiness: slice 2 of the portal-intake plan collects the
author's IDE on the intake form and hands it to `tenant init --from <id>`. If
`--ide` only narrows the loop at the first site, the recorded choice is silently
reverted by the first `agentsmith sync` — a declaration nothing reads, which is
the exact pathology `.agent-rfc/designs/fail-closed-has-a-reader.md` closed one
slice ago. `runtime/config.py`'s own header records the cost of that class of
bug: a declared $5 cap against a $150 enforced default.

## Approach

**1. `--ide` on `tenant init`.** Repeatable (`action="append"`), validated
inside `init_tenant` against `gate_ides.GENERATED` — the IDEs whose config
schema is verified and which AgentSmith can therefore actually write. Omitted
means today's behaviour, so every existing invocation and fixture is unchanged.
`neutral` is excluded for free by that choice of set: it is a contract, not an
IDE, and `ADAPTERS[NEUTRAL].config_path` is `""`.

Not argparse `choices`, deliberately: the parser is built in `main()` before
`_framework_dir()` has resolved, so computing the choice set there would make
`agentsmith --help` fail whenever the machine install has moved — a worse
failure than a late rejection. `init_tenant` raises `ValueError`, which
`_cmd_tenant_init` already catches and prints as `agentsmith: <message>` with
exit 2, and the message names the alternatives from the real constant. The
allow-list property P11 relies on is unchanged; only where it is applied moves.

**2. The choice is recorded, not merely applied.** `tenant.yaml` gains a
`workspace:` block holding `ides: [...]`. `tenant.yaml` is where this belongs:
it is committed, reviewed, and its own header states that every key in it is
read by the runtime. `workspace` rather than a key under `tenant` because it
describes the author's environment, which is what slices 2–4 add more of.

**3. One reader.** `chosen_ides(root) -> tuple[str, ...]` in
`runtime/config.py`, which already owns tenant.yaml and its precedence (rule 3)
and already has `config_get` and an unparseable-file path that logs and returns
`{}`. It filters against `ADAPTERS` and falls back to `GENERATED`.

**4. The four writers call it** instead of reading `gi.GENERATED` directly. The
loops keep their shape; only the iterable changes.

**5. An IDE with no verified config schema cannot be named at all.** The
validation in point 1 refuses it and names the alternatives — `--ide gemini: no
verified config schema; choose from claude, cursor` — at the boundary, with no
code added at any of the four sites. This is truthful
rather than restrictive: `render_config` refuses to invent a schema, so a
declaration of `gemini` could never have produced a file. The four unverified
adapters are already reported by `generate-ide-config.py`'s existing
"Not generated (no verified config schema yet …)" line, and they still read and
answer gate events; only their CONFIG is unwritable.

**Deliberately not done:** `chosen_ides` is never called from the edit-gate hot
path. `.githooks/process-gate` imports `gate_ides`, and
`.agent-rfc/designs/governance-enforcement.md` records why the registry is JSON —
"so that hooks and non-Python tooling read it without pyyaml". Putting the
reader in `runtime/config.py` rather than beside `GENERATED` keeps the pyyaml
import off the path that runs on every edit. All four call sites are
provisioning commands, none of them a hook.

## Pillars

- P1 applies — `.agent-rfc/designs/chosen-ide-is-recorded.md`, with the scope above,
  written before the code.
- P2 applies — searched: four readers of `GENERATED`, one constant, no other
  caller. The minimal change is one function called from four sites; no new
  module, no new parse, no change to the loops' shape. Knowledge-graph impact:
  one added function in an existing module. No dependencies, direct or
  transitive: `tenant_config` already imports yaml where yaml is already used.
- P3 n/a — `tenant init`, `sync` and `adopt` emit no spans today; this changes
  which files they write, not whether or how they run. No new execution path.
- P4 applies — failing before, passing after: `--ide cursor` writes
  `.cursor/hooks.json` and not `.claude/settings.json`; no `--ide` writes both;
  `sync` honours the recorded choice instead of restoring both; an IDE with no
  verified schema writes nothing and says so; `--ide neutral` is refused by
  argparse. The blocking path is `chosen_ides`'s fallback, so it goes into
  `scripts/mutation_check.py` scope: a mutation that makes the fallback return
  empty must fail a test.
- P7 applies — Python: `tuple[str, ...]` return, no `Any` in the signature, the
  YAML read delegated to the existing reader rather than a second parse.
- P8 n/a — emits no telemetry.
- P9 n/a — adds no orchestration.
- P10 n/a — makes no LLM call.
- P11 applies — `runtime/config.py`'s `chosen_ides` is the receiving-side check.
  The IDE name becomes untrusted input in slice 2, when it arrives from a portal
  form, and it reaches the filesystem as
  `ADAPTERS[ide].config_path`. It is constrained at both boundaries, and both
  are allow-lists rather than filters: `init_tenant` rejecting anything outside
  `GENERATED` at the CLI boundary, and `chosen_ides` intersecting the declared list with `GENERATED` when reading
  the value back from a file a human or a portal may have written. The value
  that reaches a path is therefore always one of the framework's own constants,
  never a string from the file; an unrecognised name selects nothing and never
  reaches a path join, a shell, or a format string.
- P12 n/a — touches no credentials.
- P13 applies — `runtime/test/test_chosen_ides.py` carries the proven half; nothing
  gets weaker, and the gap first written here does not exist. An IDE hook config is an EARLY-WARNING layer, not the control. It cannot
  cover editing paths that never consult it and never could: a terminal `sed`,
  vim, an unmanaged editor, another agent, or a clone whose hooks were never
  armed all bypass it identically, whatever `workspace.ides` says — `docs/process-gates.md`
  states this ("Bash-made edits are not caught by the edit gate"). So `--ide`
  changes which editors get early feedback, not what is enforced. The enforced
  control is that every gated change carries a design and a clean review,
  checked by `commit-msg` locally and by `process_gate.py ci` over the pushed
  range `before..sha`; that check is indifferent to how the bytes reached the
  file, so a `sed` edit and a Cursor edit are the same object to it. Proven
  half: the shell hooks in `.githooks/` are installed for every tenant whatever
  `--ide` says (test), and CI checks the range rather than only the head
  (`.github/workflows/self-test.yml`, BASE/HEAD_SHA). Declared gap, pre-existing
  and neither created nor widened by this slice: the last rung DETECTS a
  violating commit but does not remove one, and with `enforce_admins: false`
  plus `hooks/post-commit` auto-push a direct push to `main` lands before the
  check runs.
- P14 applies — `scripts/test/test_scratch_tenants.py` is the fixture at risk and no
  baseline goes stale, because the default is unchanged and every scenario there
  passes no `--ide`. The
  honest addition is a scenario pinning the narrowed projection, so that
  cursor-only scaffolding has a fixture rather than only a unit test.
- P15 applies — `runtime/config.py` decides what an unreadable declaration reads as.
  Absent, empty or unparseable, `chosen_ides` returns `GENERATED` and the existing `tenant_config` warning
  says the file could not be read. The reading is always "every verified IDE",
  never "none": a broken declaration must not silently leave an editor unwired.
- P16 applies — if the tenant.yaml read raises, control goes to the `GENERATED`
  default and no file is rewritten. The next rung, `agentsmith sync`, receives
  the same fallback from the same reader, so a broken declaration is idempotent
  across runs rather than progressively removing configs.

## Deviations

none

## Dependencies

none

## Levers

- `every-line-earns-its-place` — four sites read one constant; the change adds one
  small reader and edits one word at each site. No wrapper, no class, no new
  module, and the existing `config_get` and `tenant_config` do the file handling.
- `parameterize-dont-clone` — the same four-line loop over `GENERATED` is already
  cloned at four sites. This slice parameterises the iterable rather than adding a
  fifth copy that knows about `--ide`.
- `declared-vs-enforced` — the failure this slice exists to avoid is a
  `workspace.ides` key that `sync` ignores. The reader lands in the same commit as
  the writer, and a test asserts `sync` honours it.
- `single-source-of-truth` — after this change the chosen IDEs are stated once, in
  `tenant.yaml`, and read through one function; `GENERATED` goes back to meaning
  only "which schemas are verified".
- `implemented-not-invoked` — an IDE named without a verified config schema
  produces a printed refusal, not a silently skipped iteration.
