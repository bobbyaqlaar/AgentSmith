---
status: active
scope:
  - .githooks/process-gate
  - runtime/adopt.py
  - runtime/cli.py
  - scripts/gate_ides.py
  - contract/gate/v1/protocol.md
  - contract/gate/v1/providers.schema.json
  - scripts/test/test_provider_resolution.py
  - scripts/test/test_tenant_adopt.py
  - scripts/mutation_check.py
  - docs/process-gates.md
  - docs/UserManual.md
  - .agenticframework/process-gates.json
  - .agent-rfc/fixtures/knowledge_graph.json
---
# A tenant names its provider

Second slice of `.agent-rfc/designs/governance-providers.md`, after the contract
(`.agent-rfc/designs/gate-port.md`). The contract exists and AgentSmith satisfies it; no tenant can
yet point at it.

## Problem

`.githooks/process-gate` looks for `scripts/process_gate.py` in the repository, `$AGENTSMITH_DIR`
and `~/.agent-framework`. Those are AgentSmith's paths, so a tenant is governed by AgentSmith or by
nothing: there is nowhere to say "this repository is governed by that provider", and no way to try
another platform without editing a hook the tenant does not own.

## Approach

### The declaration

`.agenticframework/providers.json` — **JSON, not YAML**: the launcher is a shell script that must
read it before any interpreter is known to exist, and this repository already keeps its gate
configuration as JSON beside it.

```json
{
  "contract": 1,
  "providers": {
    "gate": { "command": "agentsmith gate", "version": "^2" }
  }
}
```

`"gate": "none"` is a declaration too: this repository has no gate provider, and the hooks do
nothing rather than fall back to whatever is installed. A port this slice does not read —
telemetry, records, security — is ignored, so declaring one now costs nothing.

### Resolution, in the launcher

For the three contract events (`session-start`, `pre-edit`, `stop`), in order:

1. `$GOVERNANCE_PROVIDER` — an operator escape, for trying a provider without editing the
   repository;
2. the `gate` command in `.agenticframework/providers.json`;
3. today's behaviour — `process_gate.py` from the repository, `$AGENTSMITH_DIR` or
   `~/.agent-framework`.

**An answer is a decision on stdout**, and a provider that prints none has not answered, whatever
its exit code — it falls through to the next step. That covers exit 3 ("cannot run here"), a
command that is missing (127) or not executable (126), and the case found while building this:
a provider *installed but too old to know the event*, which exits with a usage error. Enumerating
exit codes would have left that tenant ungated the day its provider lagged the contract. When every
step is exhausted the launcher fails exactly as it does today — the edit denied, the commit and
push blocked, the advisory events warning.

Everything else — `commit-msg`, `sweep`, `ci`, `artifacts`, `pillars` — keeps today's resolution:
contract v1 does not cover them, and inventing a provider protocol for them here would pin
AgentSmith's own CLI, which the contract exists to avoid.

**Arguments pass through unchanged**, `--ide` included. A provider that serves IDE hooks accepts
the dialect flag and translates it, as AgentSmith's adapter now does; the neutral profile is what
conformance pins, and a provider that implements only that is still a valid provider for a
repository whose IDEs are configured to speak it.

### Who writes it

`tenant adopt` and `tenant init` write `providers.json` naming this framework
(`"command": "agentsmith gate"`), so an adopted repository states its provider from the first
commit instead of implying it. The file is listed in the plan and the manifest like everything
else they write.

### Why the fallback stays

Removing it would make this slice a migration: every existing tenant's hooks would stop working
until someone installed a provider on PATH. With it, the declaration is additive — it says out
loud what was implied, and it is the seam another platform can take over.

## Pillars

- P1 applies — this design precedes the code and follows `.agent-rfc/designs/governance-providers.md`.
- P2 applies — no dependency added: the launcher parses the declaration with `sed`, and `runtime/adopt.py` writes it with the standard library.
- P3 n/a — no traced service path; the gate's spans are unchanged.
- P4 applies — tests first in `scripts/test/test_provider_resolution.py`: a declared provider is used, `none` governs nothing, three kinds of unanswering provider fall through, no declaration behaves as today, and `$GOVERNANCE_PROVIDER` wins.
- P7 applies — the declaration has a published schema, `contract/gate/v1/providers.schema.json`, and `runtime/adopt.py` writes what it describes.
- P8 n/a — no telemetry wiring.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 applies — the provider command is read from the repository's own committed declaration, which is a gated file, so changing it is a governed change; `$GOVERNANCE_PROVIDER` is an operator's escape, never something fetched content can set, stated in `contract/gate/v1/protocol.md`.
- P12 applies — the declaration names a command and a version range, never a credential, in `contract/gate/v1/providers.schema.json`.
- P13 applies — this is the gate's own resolution: a provider that cannot run falls through rather than passing, and an exhausted chain fails closed exactly as `.githooks/process-gate` does today.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — `"none"` (declared ungoverned) and "no provider could run" are different answers and stay so in `.githooks/process-gate`.
- P16 applies — the fallback means a wrong or missing declaration degrades to today's behaviour rather than to no gates, and `test_a_provider_that_cannot_run_falls_through_to_the_framework` pins it, including a provider too old to know the event.

## Deviations

none

## Dependencies

None added.

## Levers

- `denied-vs-missing` — "no provider" and "no gate provider declared" stay distinct.
- `guards-must-be-able-to-fail` — an exhausted chain fails closed, as today.
- `provenance-and-precedence` — one order, written down: the escape, the declaration, then the framework's own paths.
- `test-the-contract` — the tests drive the real launcher with real stub providers.
- `single-source-of-truth` — the tenant says once, in a gated file, who governs it.
