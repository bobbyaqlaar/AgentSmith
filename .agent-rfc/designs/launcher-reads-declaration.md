---
status: done
scope:
  - .githooks/process-gate
  - scripts/test/**
  - scripts/mutation_check.py
---
# The launcher reads `providers.json` by its structure

Found 2026-10-09 committing AqlaarTeleologyStudio's move onto the evals contract.

## Problem

Measured on 2026-10-09 with the launcher AgentSmith 2.2.2 ships:

- **A port with a map in it changes the gate contract the launcher reads.** `declared_contract`
  takes the top-level `"contract"` by deleting one level of `{…}` with `sed` and keeping the *last*
  `"contract"` left. An `evals` entry that declares `no_verdict` or `not_gradable` — maps the evals
  contract allows — survives that one pass with its own `"contract": 1` inside, so the launcher reads
  gate contract **1** for a repository that declares 3. KYC Sentinel's declaration (`no_verdict` for
  three suites) has read as contract 1 since 2026-10-07: its commit and push events and its CI `ci`
  event fall back to AgentSmith's gate script by path instead of asking the declared provider. OTS's
  commit was refused outright — its fallback is a vendored script too old to know `sweep`.
- **A port whose `"command"` is not its first key reads as undeclared.** `declared_port` returns the
  first `"command"` before the first `}` after the port's name; an `evals` entry written with its
  maps first yields nothing, and the launcher says "this repository declares no evals provider —
  nothing judged" and passes the step.

## Approach

- **One reader that follows the JSON's nesting**, in the launcher, with no interpreter: `decl_get
  PATH` runs a small POSIX `awk` scanner over the declaration — strings with their escapes, objects,
  arrays, scalars — and prints the scalar at a dotted path (`contract`, `providers.gate.contract`,
  `providers.evals.command`), or nothing. `awk` is POSIX and present wherever `sed` is, and the
  launcher already runs before any Python is known to exist.
- `declared_contract` is the gate entry's own `contract`, else the top-level one, else 1 — as
  documented; `declared_port` is `none` when the port's value is the string, else its `command`,
  wherever the key sits in the object.
- **Tests** pin both readings on the declarations that broke them (KYC's and OTS's shapes), with keys
  in any order, an `_about` that quotes `"gate": "none"`, escaped quotes, and a declaration with no
  `contract`; a mutation restores the one-pass read.
- **Ships in 2.2.3** with `setup-evals-provider`; KYC and OTS take it with their next sync.

## Pillars

- P1 applies — `.agent-rfc/designs/launcher-reads-declaration.md` records both misreadings, measured, before the change.
- P2 applies — `.githooks/process-gate` keeps one reader for the declaration that both functions use.
- P3 n/a — no tracing changes.
- P4 applies — `scripts/test/test_gate_contract_v3.py` pins the readings on the declaration shapes that broke them; a mutation restores the old read.
- P7 n/a — shell, no Python models.
- P8 n/a — no telemetry wiring.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 applies — `.githooks/process-gate` reads `providers.json`, an always-governed file, as data; an unreadable or malformed declaration yields nothing, and each caller fails as it already does for a missing one.
- P12 n/a — no credentials.
- P13 applies — `.githooks/process-gate` stops a declaration's shape from changing which gate contract governs a repository, or silently undeclaring a port.
- P14 n/a — no fixtures.
- P15 applies — `.githooks/process-gate` no longer reports "no evals provider declared" for a provider that is declared.
- P16 n/a — no new fallback.

## Deviations

none

## Dependencies

none — POSIX `awk`.

## Levers

- `declared-vs-enforced` — the contract a repository declares is the one that governs it, whatever else the declaration holds.
- `validate-on-the-receiving-side` — the launcher reads the declaration as JSON, not as text that usually looks like it.
- `test-the-contract` — the evals contract's own optional maps broke the gate contract's reading; the tests use them.
