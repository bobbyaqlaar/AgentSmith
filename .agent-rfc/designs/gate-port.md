---
status: done
scope:
  - contract/gate/v1/protocol.md
  - contract/gate/v1/event.schema.json
  - contract/gate/v1/decision.schema.json
  - contract/gate/v1/fixture.json
  - contract/gate/v1/cases.json
  - runtime/conformance.py
  - runtime/cli.py
  - scripts/gate_ides.py
  - scripts/process_gate.py
  - runtime/test/test_conformance.py
  - scripts/test/test_gate_contract.py
  - .agenticframework/process-gates.json
  - scripts/gate_models.py
  - scripts/mutation_check.py
  - docs/UserManual.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# The gate port: a contract a provider satisfies, and a suite that proves it

First slice of `.agent-rfc/designs/governance-providers.md`: the gate port, published as a
contract with a conformance suite, and AgentSmith's own adapter certified against it.

## Problem

A tenant's hooks call AgentSmith by path — `.githooks/process-gate` looks for
`scripts/process_gate.py` in the repo, `$AGENTSMITH_DIR` and `~/.agent-framework`. Nothing else
can answer those questions, so "hook onto AgentSmith or another platform" is not possible today,
and nothing states what a platform would have to do.

The pieces of a neutral contract already exist and are not published: `gm.GateEvent` (kind, paths,
command, cwd, stop_active) is what the checks read once an IDE's dialect is off it, and the
decision — allow, deny, block, context, with its text — is what `gate_ides.render` turns back into
each IDE's shape. They are internal names in `scripts/`, not a contract anyone can build against.

## Approach

### Contract v1 is the neutral profile

A **gate provider** is a command. The contract covers the three hook events, because those are the
portable core: a provider decides about an edit, a turn ending, and a session starting.

    <provider-command> <event>        # event ∈ session-start | pre-edit | stop
    stdin   one GateEvent as JSON     (contract/gate/v1/event.schema.json)
    stdout  one Decision as JSON      (contract/gate/v1/decision.schema.json)
    exit    0 a decision was made · 3 this provider cannot run here

`{"decision": "deny", "text": "…"}` — `allow`, `deny`, `block` and `context` are the four answers,
and `text` is what a person reads. Exit 3 is the caller's signal to try the next provider, the
same meaning the launcher already gives it for an interpreter that cannot run.

**IDE dialects stay on the provider's side of the line.** Six IDEs send six payload shapes for the
same three questions, and translating them is the adapter's job, not the tenant's: a provider that
wants to serve Claude Code or Cursor ships that translation, as AgentSmith does in
`scripts/gate_ides.py`. The contract carries the neutral shape only, so a second platform
implements one protocol rather than six dialects.

**Out of contract v1, deliberately:** `commit-msg`, `sweep` and `ci` are git and CI events whose
contract is an exit code and a message, already stable, and whose arguments differ enough
(a message file, a commit range, a record file) that pinning them now would pin AgentSmith's CLI
rather than a protocol. They stay documented behaviour, and v2 can adopt them once a second
provider exists to disagree with.

### AgentSmith's adapter

`gate_ides` gains a `neutral` adapter — parse is identity over the event, render writes
`{"decision", "text"}` — and `process_gate.py` accepts `--ide neutral`. That makes the whole
existing decision path the adapter: no second implementation of what a rule means, which is the
`one-catalog` lever this repository already holds itself to.

`agentsmith gate <event>` is the command a tenant names as its provider. It resolves
`process_gate.py` the way the launcher does and runs it with `--ide neutral`.

### The conformance suite

`agentsmith conformance --provider "<command>"` builds the fixture repository the contract
describes (`fixture.json`: the files, and whether they are committed), then replays each case
(`cases.json`: an event and the decision expected) against the provider **in that repository**,
and prints one line per case. A gate decision depends on the repository it is asked about, so a
contract without a fixture repository would be untestable — which is why the fixture is data in
the contract rather than a fixture in this repository's tests.

Five cases, chosen because each pins a different rule rather than a different wording:

1. an edit to an ungated path — `allow`;
2. an edit to a gated path with no design — `deny`;
3. an edit to a gated path an active design covers — `allow`;
4. a turn ending with gated changes and no review — `block`;
5. a session starting — `context`, with text.

`text` is never matched: a provider is free to word its answer. The suite asserts the decision, and
that `deny` and `block` carry some text, because a refusal with no reason is not an answer.

### What is not in this slice

Provider resolution in the tenant — `providers.yaml` and a launcher that reads it — is the next
slice. This one publishes the contract and proves AgentSmith satisfies it; that is what a second
platform needs before any tenant can point at one.

## Pillars

- P1 applies — this design precedes the code and follows `.agent-rfc/designs/governance-providers.md`, which the owner asked for on 2026-09-23.
- P2 applies — no dependency added: the suite builds its fixture with `git` and the standard library, as `scripts/test/test_process_gate.py` does.
- P3 n/a — the gate's own spans are unchanged; the adapter adds no service path.
- P4 applies — tests first: `scripts/test/test_gate_contract.py` runs the suite against AgentSmith's own adapter, and `runtime/test/test_conformance.py` covers the runner's verdicts, including a provider that fails a case.
- P7 applies — the event and decision stay Pydantic models in `scripts/gate_models.py`; the schemas in `contract/gate/v1/` are generated from them rather than written twice.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 applies — a provider command comes from the caller, never from the repository under test; the fixture's files are written by the suite, and a case's event is data the suite composes, in `runtime/conformance.py`.
- P12 applies — nothing in the contract or the suite reads a credential; the fixture repository holds no secret, in `contract/gate/v1/fixture.json`.
- P13 applies — the neutral adapter renders the same decision the IDE adapters render, so a provider cannot answer one thing to a dialect and another to the contract (`scripts/gate_ides.py`).
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — exit 3 means "cannot run here" and is distinct from `deny`; the suite reports a provider that cannot run separately from one that answered wrongly (`runtime/conformance.py`).
- P16 applies — a failing case names the event, the expected decision and what came back, so a provider author can act on it without reading this repository (`runtime/conformance.py`).

## Deviations

none

## Dependencies

None added.

## Levers

- `one-catalog` — the neutral profile is an adapter over the existing decision path, not a second implementation of the rules.
- `declared-vs-enforced` — conformance is a suite a provider runs, not a claim in a document.
- `test-the-contract` — the fixture is a real repository and the cases are real events through the real gate.
- `denied-vs-missing` — exit 3 (cannot run) and `deny` (a decision) stay different answers.
- `use-existing-apis` — `GateEvent` and the decision already exist; this publishes them.
