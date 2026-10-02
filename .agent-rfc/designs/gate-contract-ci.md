---
status: done
scope:
  - contract/gate/v2/**
  - .agenticframework/process-gates.json
  - .githooks/process-gate
  - .github/actions/setup-agentsmith/**
  - runtime/cli.py
  - runtime/conformance.py
  - runtime/adopt.py
  - runtime/sync.py
  - scripts/process_gate.py
  - scripts/gate_models.py
  - scripts/send_dev_record.py
  - workflow-templates/agentsmith-gates.yml
  - scripts/test/**
  - runtime/test/**
  - scripts/mutation_check.py
---
# C1 — Gate contract 2: the CI event

Slice C1 of `.agent-rfc/designs/governance-contracts.md`. A tenant's CI asks its declared gate
provider whether a pushed range passes, instead of running `scripts/process_gate.py` by path.

## Problem

Every governed tenant's CI runs the gate by path:

- `workflow-templates/agentsmith-gates.yml`, which `adopt` writes, checks AgentSmith out at a ref and
  runs `python3 .agentsmith-framework/scripts/process_gate.py ci …` then
  `.agentsmith-framework/scripts/send_dev_record.py` — two framework paths in a tenant file;
- KYC Sentinel's hand-written job does the same against a checkout of AgentSmith **at no ref** —
  whatever `main` is that minute;
- OTS runs a **vendored** copy, `scripts/process_gate.py`, committed in OTS and 1,318 lines behind.

`contract/gate/v1` cannot carry this: it defines `session-start`, `pre-edit` and `stop`, and says a
provider that does not answer an event lets the caller "try the next one". For a CI check that
fall-through lands on AgentSmith's own paths — the coupling this programme removes. The launcher
(`.githooks/process-gate`) already skips the declared provider for `ci` and goes straight to the
paths.

## Approach

### Contract 2 = contract 1 + the `ci` event, with no fall-through

`contract/gate/v2/` is a new directory; `v1/` stays as published and is still served.

- **Events.** The three v1 events, unchanged, plus **`ci`**: a range of commits to judge. The event
  gains `kind: "range"` with `base` and `head` (a `base` of all zeros means "a new branch: the head
  commit only", as the gate already treats it).
- **The answer.** One decision on stdout, as in v1: `allow` (the range passes) or `deny` (it does
  not, `text` required). Two optional fields, both for a person rather than a machine: `report`, the
  markdown summary CI prints, and `annotations`, one line per problem. A provider that has nothing
  to say beyond the verdict omits both.
- **No fall-through for `ci`.** A caller that gets no decision for `ci` fails the check, naming why —
  provider not installed, not executable, or too old to know the event. It never falls back to a
  framework path. The three v1 events keep v1's fall-through, so a tenant moving to contract 2 loses
  nothing it had.
- **The declaration states the contract per port.** `providers.schema.json` (v2) lets the gate entry
  carry `"contract": 2` and `"setup"`: the provider's CI setup step, a pinned reference
  (`bobbyaqlaar/AgentSmith/.github/actions/setup-agentsmith@v2.1.0`). A top-level `"contract": 1`
  with no per-port value reads as gate contract 1, so every existing declaration means what it meant.
- **The declaration is always governed.** Under contract 2 the declaration decides whether CI
  checks anything — `"gate": "none"` turns the check off — so an unreviewed edit to it must not be
  possible. It was: a tenant `adopt` wrote gates `.agenticframework/process-gates.json` but not
  `providers.json`, and a commit setting the gate to `none` needed no design (found by this slice's
  own test). The gate now treats both files — its config and the declaration — as governed whatever
  the config lists, and the contract says a provider must: a conformance case edits the declaration
  in a fixture whose config does not list it, and expects `deny`. `adopt` adds the declaration to the
  gated list it writes, so the config says what the gate does.
- **The v2 protocol is reference documentation**, declared beside v1's in this repository's
  `.agenticframework/process-gates.json` (`extends.artifacts.reference`), as the artifact rule asks.
- **Records stay out of the contract until C3.** The AgentSmith provider sends the dev record itself
  when the portal's two variables are set, as the workflow's second step does today; the tenant's
  workflow has no record step at all. C3 publishes the record's schema and endpoint as a wire
  contract the provider implements.

### The pieces

- **`.githooks/process-gate ci`** reads the gate's contract from `providers.json`. At contract 2 it
  sends `{"kind": "range", "base": …, "head": …}` to the declared command with `ci` appended, prints
  the decision's `report`, emits its `annotations` as `::error` lines, and exits 0 on `allow`, 1 on
  `deny` or on no decision. At contract 1, or with no declaration, it does what it does today — so
  AgentSmith's own CI and every unmigrated tenant are untouched.
- **`agentsmith gate ci`** — AgentSmith as a contract-2 provider. `scripts/process_gate.py` gains the
  decision as an output of the run it already does (`cmd_ci` builds the report and the record; it now
  also returns them), and `_cmd_gate` accepts `ci`. When `AGENTSMITH_PORTAL_URL` and
  `AGENTSMITH_PORTAL_INGEST_TOKEN` are set it sends the record through `send_dev_record`'s function —
  imported, not run by path — and says in `report` whether it was sent.
- **`.github/actions/setup-agentsmith`** — the provider's own CI setup step: Python, the gate's
  requirements, and `agentsmith` on `PATH`, all from the repository at the action's own ref. A tenant
  pins the provider by pinning that ref; nothing checks AgentSmith out at `main`.
- **`workflow-templates/agentsmith-gates.yml`** becomes the shim: check out the tenant, run the
  declared provider's setup step, run `bash .githooks/process-gate ci`. No framework path, no
  `python3`, no checkout of the provider's repository. `adopt` and `sync` write it, and `sync`
  refreshes an untouched copy as it does today.
- **`providers_declaration`** writes `"contract": 2` and `"setup"` for new tenants; `sync` updates an
  untouched declaration the same way, so a tenant moves to contract 2 in the one pull request a sync
  opens.
- **Conformance.** `contract/gate/v2/fixture.json` carries two commits so a range exists; `cases.json`
  adds `ci` cases — a range whose gated commit has no design (`deny`), a clean range (`allow`), a
  new-branch range (the head only) — and the v1 cases unchanged. `agentsmith conformance --provider
  "agentsmith gate" --contract 2` runs them; AgentSmith's own provider must pass both versions.

### What it takes to use

A **release** that carries the setup action — **v2.1.0**, a MINOR: contract 2 is additive and v1 is
still served. A tenant cannot pin a ref that does not exist, so cutting it is the owner's step
between building C1 and proving it. CHANGELOG calls it out as a hook-interface change.

### The tenants that prove it

1. **Scratch tenants** (`.github/scratch-tenants/`): rebuilt by CI with the new template and
   declaration; their CI must go green through the provider.
2. **KYC Sentinel**, after its pending sync: its declaration moves to contract 2, its hand-written
   process-gates job is replaced by the shim, and the unpinned checkout of `main` is gone.
3. **OTS** (its own design, in OTS): declares `providers.json`, takes the shim, removes the gate job
   from `ci-python-fastapi.yml`, and deletes its vendored `process_gate.py`, `gate_*.py` and
   `requirements-gate.txt` — unless another vendored script still imports them, in which case those
   files leave with the slice that retires that script, and the OTS design names which.

**Deliberately not done:** `commit-msg`, `sweep`, `pre-push` and the knowledge graph (C2); the record
as a published wire contract (C3); AgentSmith's own `self-test.yml`, which runs the gate it ships and
is the provider, not a tenant; and `agentsmith-sync.yml`, which still checks AgentSmith out to run
`agentsmith sync` — it is the provider's update channel for the shims, and goes with C9.

## Pillars

- P1 applies — `.agent-rfc/designs/governance-providers.md` is the architecture this continues; the umbrella `governance-contracts.md` (PR #28) defines this slice, C1, and its tenant steps, and this design precedes the code.
- P2 applies — `contract/gate/v1/protocol.md` is copied into `v2/` and extended, not rewritten; `scripts/process_gate.py`'s `cmd_ci` already builds the report and the record, and `scripts/send_dev_record.py`'s sender is imported rather than duplicated. No new package: the setup action installs `scripts/requirements-gate.txt`, which exists.
- P3 applies — `scripts/process_gate.py` runs `ci` inside `_traced("ci", …)` already; `agentsmith gate ci` goes through the same call, so the span exists for the provider path too.
- P4 applies — `runtime/conformance.py` gains the contract-2 cases and is run against AgentSmith's own provider for v1 and v2; `scripts/test/test_gate_contract.py` adds the launcher's three answers for `ci` (allow, deny, no decision → failure, never a path fallback) and a contract-1 tenant left unchanged. Mutations on the no-fall-through rule and on the per-port contract read.
- P7 applies — `scripts/gate_models.py`: the range event and the report fields are Pydantic models, and the v2 schemas are generated from them as v1's are.
- P8 n/a — no new telemetry wire; the existing `ci` span covers the provider path.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — `contract/gate/v1/protocol.md`'s rule holds: the provider command comes from the tenant's committed declaration, `$GOVERNANCE_PROVIDER` is an operator's escape; the `setup` reference is read by `sync` to write the workflow, never executed from fetched content.
- P12 applies — `scripts/send_dev_record.py` reads the portal URL and token by name from the environment and refuses redirects; the provider path keeps that, and the token never enters the decision or the report.
- P13 applies — `.githooks/process-gate` fails `ci` closed when a contract-2 provider gives no decision; today it falls back to framework paths, and that fallback is exactly what contract 2 removes for this event. Contract-1 behaviour is unchanged, pinned by a test. And the declaration, which now switches CI's check on or off, is governed in every tenant whatever its config lists — `scripts/process_gate.py`'s `is_gated` — closing a hole contract 2 would otherwise have widened.
- P14 applies — `contract/gate/v1/fixture.json` and `cases.json` stay byte-for-byte; v2 gets its own fixture and cases, so a v1 provider's conformance result cannot move.
- P15 applies — `.githooks/process-gate` names the reason a `ci` check failed without a verdict (not installed, not executable, no decision) separately from a `deny`, which carries the provider's own text.
- P16 applies — `contract/gate/v1/providers.schema.json` already admits ports it does not read; its v2 successor keeps a per-port contract, so a tenant can return to contract 1 by editing one value; the shim and the old workflow both remain valid until C9.

## Deviations

none

## Dependencies

none

## Levers

- `gate-integrity` — no fall-through for `ci`; a CI check with no decision fails, never resolves to a path.
- `declared-vs-enforced` — the declaration's contract number is read and acted on, not recorded for a person only.
- `test-the-contract` — conformance cases for `ci`, run against AgentSmith's own provider, and the scratch tenants' real CI.
- `implemented-not-invoked` — the slice is done when three tenants' CI runs through the provider.
- `two-owners-two-cadences` — contract 2 is additive and v1 stays served; the provider is pinned through its setup ref.
- `failure-mode-visibility` — "provider could not answer" and "range denied" read differently.
- `docs-match-behaviour` — README's ports table, `docs/process-gates.md`, the manual and CHANGELOG move with it.
