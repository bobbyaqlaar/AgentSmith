---
status: done
scope:
  - scripts/**
  - templates/agent-rules.yaml
  - templates/governance.json
---
# `fail_closed` is declared seven times and read nowhere

## Problem

`Adapter.fail_closed` (`scripts/gate_ides.py`, mirrored in
`scripts/gate_models.py` and set per IDE in `templates/governance.json`'s
`ides` list) appears exactly twice in the repository — both times as a field
declaration. **Nothing reads the value.** Found in the lever review recorded in
`.agent-rfc/reviews/vacuous-sweep-guards.md`, which recorded it rather than
guessing at a fix.

Two things are wrong, and the second explains why the first went unnoticed.

**1. Two sources of truth, and the declared one is inert.** The generated Cursor
config does carry `failClosed: true` — twice, on `preToolUse` and
`beforeShellExecution` — but as a **hardcoded literal** inside
`render_config`'s cursor branch. Set `fail_closed: false` in the registry and
the generated config still says `true`. The registry records an intent that
changes nothing.

**2. The name and the values disagree.** Read as "does the edit gate fail closed
for this IDE?", the values are wrong: `claude` is `False` while its own `note`
says "the shell fallback prints a deny", and `.githooks/process-gate` does
exactly that. Read as "does this IDE's generated config need a `failClosed`
key?", the values are right — only Cursor's vendor schema has one — but then the
`True` on `neutral`, which emits no config at all, means nothing.

The introducing design (`.agent-rfc/designs/governance-enforcement.md`) is
clear about the intent and about why one boolean cannot carry it:

> **Fail-closed where the IDE allows it:** Cursor: `failClosed: true`; Claude:
> the existing shell fallback prints a deny; Antigravity and VS Code fail open by
> design, so the stated limit is that git and the sweep still hold.

Three IDEs, three different mechanisms, one shared property. The field collapsed
them into a boolean whose name matched the property and whose values matched the
mechanism — so a reader learns the opposite of the truth for Claude, which is the
IDE this repository runs and `DEFAULT_IDE`.

## Approach

Keep the property, fix the values to mean it, and give it a reader.

The value lives in `templates/agent-rules.yaml`, not in
`templates/governance.json`: the JSON is generated from the YAML by
`scripts/generate-ide-config.py --registry` and says so in its own `_about`.
This design first named only the JSON, which is why the scope had to be widened
once the change landed where it belonged — recorded in the review.

**The field means: the edit gate fails closed for this IDE** — a governance fact
a tenant choosing an IDE needs, and the only reading worth carrying in a file
called `governance.json`. Values become:

| adapter | fail_closed | the mechanism that makes it true |
|---|---|---|
| `cursor` | true | `failClosed: true` in its generated `.cursor/hooks.json` |
| `claude` | **true** (was false) | `.githooks/process-gate`'s pre-edit fallback prints a deny |
| `neutral` | true | contract/gate/v1: a provider that cannot answer falls through to the framework's own gate, which denies |
| `antigravity`, `copilot`, `gemini`, `codex` | false | fail open by design; git and the sweep hold |

**The reader is a test, because the mechanisms differ per IDE and no single line
of production code can consult them.** `scripts/test/test_fail_closed_declared.py`
asserts, for every adapter:

- declared `true` → its named mechanism is present. Cursor: the generated config
  carries `failClosed` on every hook that can deny. Claude: the launcher emits a
  `permissionDecision: deny` for `pre-edit`. Neutral: the contract states the
  fall-through.
- declared `false` → it claims no mechanism, so a future edit that adds one
  without updating the registry fails here rather than passing silently.

**And the generator stops hardcoding it.** `render_config`'s cursor branch reads
`ADAPTERS["cursor"].fail_closed`, so the registry is the single source and the
test above is checking a real dependency rather than two constants that happen to
agree.

Not attempted: making one boolean drive all three mechanisms. They are a config
key, a shell fallback and a protocol rule; a reader that pretended otherwise
would be the same mistake in a new place.

## Pillars

- P1 applies — this design before the edit; scope `scripts/**` and `templates/governance.json`, reviewed in `.agent-rfc/reviews/fail-closed-has-a-reader.md`, with the per-IDE statement corrected in `docs/process-gates.md`.
- P2 applies — no new concept: the field, the registry and `render_config` all exist. One value changes (`claude`), one literal becomes a field read in `scripts/gate_ides.py`, and one test file is added. The `ides` registry is already drift-checked against `ADAPTERS` by `scripts/test/test_gate_contract.py`, so the two cannot diverge. No dependencies added.
- P3 n/a — config generation and a test; no traced execution path is added.
- P4 applies — `scripts/test/test_fail_closed_declared.py` fails before this change on `claude`, which declares `false` while `.githooks/process-gate` denies for it; and its Cursor half fails if the `failClosed` literal is restored in place of the field read. Both proven by making the change and watching the failure, not by reasoning.
- P7 applies — Python, `json` and the existing `ADAPTERS` table; the generated Cursor config stays valid against that vendor's documented schema, which is what `scripts/test/test_gate_contract.py` already pins.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — the test reads `.githooks/process-gate` and `contract/gate/v1/protocol.md` as text from this repository; it matches fixed strings and never executes them.
- P12 applies — no credential is read or written; `render_config` writes hook configs, which carry commands and timeouts only.
- P13 applies — **a declared control gains an enforcer, and nothing gets weaker.** The registry stops being decorative: an adapter that declares `fail_closed` must show the mechanism, and one that does not must not have it. Correcting `claude` to `true` does not change behaviour — the launcher already denied — it stops the registry misreporting it, which is the half that was unprovable before.
- P14 applies — `templates/governance.json` is a checked fixture: its `ides` list is diffed against `ADAPTERS` by `scripts/test/test_gate_contract.py`, so the value change lands in both. `.agent-rfc/fixtures/knowledge_graph.json` re-pinned with `map_codebase.run_map(force=True)`.
- P15 applies — this is the pillar the slice is about. One boolean carried two meanings, and for `DEFAULT_IDE` it reported the opposite of the truth. After this it carries one, its values match it, and the test names which mechanism makes each `true` true.
- P16 applies — the fail-closed path itself is a recovery rung: when the gate cannot run, `.githooks/process-gate` denies the edit rather than admitting it. This slice does not change that rung; it makes the registry describe it correctly, so a tenant choosing an IDE learns whether that rung exists for them before they need it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the field this slice is about: declared seven times, read nowhere.
- `provenance-and-precedence` — two sources for one property, with the inert one presented as authoritative.
- `ambiguous-signals` — a name that says "does it fail closed" over values that answer "does it need a config key".
- `docs-match-behaviour` — `docs/process-gates.md` states one blanket rule where the property is per IDE.
- `guards-must-be-able-to-fail` — the new test is proven to fail by restoring the hardcoded literal.
- `every-line-earns-its-place` — one value corrected, one literal replaced by a field read; no abstraction introduced to unify three genuinely different mechanisms.
