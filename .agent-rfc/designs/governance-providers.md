---
status: active
scope:
  - .agent-rfc/designs/governance-providers.md
---
# A tenant hooks onto a governance provider, not onto AgentSmith

**Nothing is built from this design until the owner says go.** It is the architecture asked for on
2026-09-23: tenants should be able to hook onto AgentSmith *or any other platform* that provides
the pillars — observability, security, design and review governance — with the least friction,
including across AgentSmith's own major releases.

## Problem

A tenant today holds AgentSmith's files and calls them by path: five hook copies, seven workflow
copies, generated rule files, IDE hook configs, and (vendored tenants) the whole of `scripts/`,
`runtime/`, `templates/` and `fixtures/`. Only the vendored code and the version pin are
refreshed by `agentsmith upgrade`; everything else drifts. The gate hooks changed six times in
90 days and the workflow templates 33 times, and no tenant saw any of it.

What that costs per major release, per tenant: re-install on each machine; `agentsmith upgrade`,
whose own commit the tenant's gates then refuse because it touches gated `scripts/**` with no
`Design:`/`Review:` trailers; a hand copy of the gate hooks; a hand edit of `ref: v2.0.0` in the
gates workflow, itself a gated file; regenerated rule files; and `core.hooksPath` plus
`agentsmith.chainHooksPath` in every clone. Six steps and two design/review cycles.

Worse for the stated goal: every one of those is AgentSmith-shaped. A tenant cannot point any of
it at another platform, because the coupling is to a file layout rather than to a contract. And
`agentsmith upgrade` in an *adopted* repository would vendor `scripts/` and `runtime/` into it —
it checks only for a package pin, not for the adopted manifest — which is the opposite of what
adoption promised.

## Approach

### The inversion

The tenant declares **what governance it wants**; a **provider** is resolved at run time. AgentSmith
becomes the reference implementation of a contract, not the thing tenants copy from. Five ports,
each of which already has a de-facto contract in this repository:

| Port | What the tenant needs | What exists today | What is missing |
|---|---|---|---|
| **Gate** | a decision at edit, turn end, commit, push and CI | `.githooks/process-gate` (JSON event in, decision out, exit codes); `scripts/gate_ides.py` adapters per IDE | the event and decision are not published as a schema, and the launcher hard-codes AgentSmith's paths |
| **Rules** | what the agent is told | `templates/governance.json`, the `agentsmith:rules` markers, `extends.session_start` | the registry schema is not published |
| **Telemetry** | spans, metrics, resource attributes | OTLP plus the attribute names in the Wire Contract | nothing — already vendor-neutral, and the model the others should copy |
| **Records** | what CI decided, per commit | the dev record, already versioned (`schema: 1`) | naming it a contract and documenting the endpoint |
| **Security and evals** | artifact schemas and a harness verdict | risk register, agency manifest, tool allowlist, NIST profile, `fixtures/security/control_registry.json` | the verdict format is not published |

The runtime helpers — the gateway, the HITL gate, the dead-letter queue — are a **library**, not a
port. They stay an optional versioned package, chosen independently of the governance provider.

### What a tenant holds

One declaration, and nothing else that names a vendor:

```yaml
# .agenticframework/providers.yaml
contract: 1
providers:
  gate:      { command: "agentsmith gate", version: "^2" }
  rules:     { command: "agentsmith rules" }
  records:   { url: "${GOVERNANCE_PORTAL_URL}", schema: "dev-record@1" }
  telemetry: { otlp: "${OTEL_EXPORTER_OTLP_ENDPOINT}" }
  security:  { command: "agentsmith security" }
```

Any port may be `none`: a repository may want the gates and not the telemetry. The git hooks become
one generic stub that runs the resolved gate command; the CI workflow runs the same command. Neither
names AgentSmith, so neither drifts when AgentSmith changes.

**Resolution order** for a command provider, first that answers: `$GOVERNANCE_PROVIDER` (an escape
for CI and for trying a provider out), the command on `PATH`, the machine install, a checkout named
by `$AGENTSMITH_DIR`. A provider that cannot be resolved **fails closed for the gate** exactly as
the launcher does today — an edit denied, a commit and push blocked — and open for telemetry, which
must never block a commit.

### Why this answers the major-release question

Two version lines, deliberately independent:

- **the contract** — a small integer, changes rarely, and is what the tenant pins;
- **the provider** — semver, changes often, pinned as a range (`^2`).

AgentSmith 2.x and 3.x both speak contract 1. **A major AgentSmith release then touches no tenant
file at all**, and friction appears only when the *contract* changes — the one case that deserves a
deliberate migration. That is a stronger guarantee than any sync command, because there is nothing
left to sync.

### What makes "or another platform" real rather than claimed

A conformance suite shipped with the contract: golden events in, expected decisions and exit codes
out, so a third party can self-certify with `agentsmith conformance --provider "<command>"`.
AgentSmith's own adapter runs the same suite, which is what keeps the contract honest as the
implementation moves.

### Decisions taken here

The owner declined a questionnaire, so these are my calls, each reversible:

1. **Vendoring stays, as one transport of the gate provider** — not as the model. Existing vendored
   tenants keep working; new ones resolve a provider. No forced migration, and the drift remains
   only where someone opts into it. (The owner kept vendoring deliberately on 2026-09-13.)
2. **The contract lives in this repository**, under `contract/`, with its own version integer and
   shipped as a release asset. It can move to its own public repository the day a second platform
   adopts it; until then a second repository is overhead.
3. **The gate port goes first**, end to end, proven by adopting a scratch tenant whose files name a
   provider rather than AgentSmith's paths. The other four ports keep working as they do now and
   are documented as contracts in place.
4. **Both visibilities are supported** (the owner's answer): the gate workflow uses the token when
   it is set and a plain checkout when the provider repository is public, so going public later
   removes a step without changing a tenant.

### What this does not fix by itself

`agentsmith upgrade` refusing its own commit in a gated tenant is a real problem for vendored
tenants, and the provider model removes it only for the files that stop being copies. A
hash-verified `Review: n/a: framework sync <version>` — the same escape as the generated scaffold,
checkable against what the provider ships — remains the answer for whatever stays copied, and is
worth its own slice.

## Pillars

- P1 applies — this design is the architecture, written before any of it is built; the friction it answers is measured in `.agent-rfc/designs/governance-providers.md` › Problem.
- P2 n/a — no dependency is added by a design document; the slice that builds the gate port answers this.
- P3 n/a — no traced code changes here.
- P4 applies — the contract's conformance fixtures are the test that a provider, AgentSmith's own included, still satisfies it; the existing per-IDE golden payloads in `scripts/test/test_gate_ides.py` are the shape to follow.
- P7 n/a — no code in this change.
- P8 applies — the telemetry port is OTLP and the attribute names already documented in the Wire Contract table in `CHANGELOG.md`; no new wire is invented.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 applies — a provider command comes from the tenant's own committed `providers.yaml`, never from an environment a remote can set, and `$GOVERNANCE_PROVIDER` is an operator escape recorded in `.agent-rfc/designs/governance-providers.md`, not a value any fetched content supplies.
- P12 applies — a provider is named by command and version, never by credential; endpoints and tokens stay environment variables read by name, as `scripts/send_dev_record.py` does.
- P13 applies — an unresolvable gate provider fails closed, exactly as `.githooks/process-gate` does today when no interpreter can run the gate.
- P14 n/a — no fixture or baseline changes here.
- P15 applies — a port set to `none` is a declared answer, distinct from a provider that could not be resolved, which is an error; both are named in the plan this design proposes.
- P16 applies — every decision above is reversible, and the contract's own version is what a migration would move; the escape for whatever stays copied is stated in "What this does not fix by itself".

## Deviations

none

## Dependencies

None added.

## Levers

- `single-source-of-truth` — a tenant pins a contract, not a file layout, so there is one place a change to the relationship happens.
- `use-existing-apis` — four of the five ports already have a contract in this repository; this names them rather than inventing new ones.
- `declared-vs-enforced` — a conformance suite makes "any platform can provide this" checkable instead of asserted.
- `two-owners-two-cadences` — the contract and the provider version move on separate clocks, which is what keeps a major release off the tenant's desk.
- `failure-is-not-a-result` — an unresolvable gate provider blocks; it never passes quietly.
