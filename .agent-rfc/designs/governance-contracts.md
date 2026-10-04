---
status: active
scope:
  - .agent-rfc/designs/governance-contracts.md
---
# Governance contracts: every port a tenant needs, Dev and Ops

The umbrella for finishing what `.agent-rfc/designs/governance-providers.md` began. That arc made
AgentSmith the reference implementation of **one** contract — the gate, for three editing events —
and left the other ports "contracts in place that still resolve to AgentSmith". This design defines
the rest, orders them into slices, and pairs each with the tenant step that proves it. It writes no
code: every slice gets its own design, review and pull request.

## Problem

**The owner's principle (2026-10-02), non-negotiable:** AgentSmith and its tenants are decoupled,
and the decoupling is by contract — "the key change in this version". A tenant depends on a
published, versioned interface, never on AgentSmith's files or paths.

The code does not meet it yet. Measured, not estimated:

- **The framework ships the coupling.** Its own workflow templates call **11 framework scripts by
  path** in every tenant that installs them — `process_gate.py`, `send_dev_record.py`,
  `generate-ide-config.py`, `verify_system.py`, `run-evals.py`, `run-security-checks.py`,
  `sync-portal-history.py`, `sync-ui-feedback.py`, `shadow-eval.py`, `verify_ttft.py` — and its hooks
  call five more. Any rename or flag change in AgentSmith breaks every tenant's CI.
- **Only three gate events are in a contract.** `contract/gate/v1` covers `session-start`, `pre-edit`
  and `stop`. The commit, push and CI gates "still run AgentSmith's own `process_gate.py`"
  (`README.md`), so a tenant's commit and CI are governed by a path, not a contract.
- **Vendoring is still a supported transport** — decision 1 of `governance-providers.md`, made
  because the owner kept vendoring on 2026-09-13. The principle overrides that decision. Its cost is
  visible in OTS: 46 `scripts/`, 51 `runtime/` and 9 `fixtures/security/` files committed, and an
  uncommitted gate 1,318 lines behind today's.
- **A pin is missing where there is one at all.** KYC Sentinel's CI checks AgentSmith out at no ref —
  whatever `main` is that minute — and runs `scripts/process_gate.py` from it.

**What a tenant uses, by port** (from OTS's and KYC's workflows and the templates):

| Need | Today | Port |
|---|---|---|
| commit-msg, sweep, pre-push, CI range check | `.githooks/*` → `scripts/process_gate.py`; CI → `scripts/process_gate.py ci` by path | **Gate** |
| the review's `KG query:` hash | `scripts/map_codebase.py`, `local_knowledge_graph.py` | **Gate** (evidence) |
| what CI decided, sent to the portal | `scripts/send_dev_record.py` | **Records** |
| rule files, IDE configs, drift check | `templates/governance.json`, `scripts/generate-ide-config.py` | **Rules** |
| spans and resource attributes | vendored `runtime/` imported by tenant code (OTS `tracing.py`) | **Telemetry** |
| golden, fairness, hallucination, TTFT, shadow evals | `scripts/run-evals.py`, `verify_ttft.py`, `shadow-eval.py` | **Evals** |
| security harness, redaction check | `scripts/run-security-checks.py`, `verify_system.py --check-redaction`, `fixtures/security/` | **Security** |
| run history and UI feedback to and from the portal | `scripts/sync-portal-history.py`, `sync-ui-feedback.py` | **Ops records** |

## Approach

### What a tenant may hold

1. **Declarations** — `.agenticframework/providers.json` naming a provider per port, with the
   contract version it speaks and a provider range; `process-gates.json` and `tenant.yaml`.
2. **Its own data** — designs, reviews, golden datasets, its knowledge graph, its security
   posture, its tenant-specific rules.
3. **Generated, hash-recorded shims** — the hook stubs, the IDE hook configs, the rules block, the
   workflows — each of which calls a *declared command*, never a path, and is refreshed by `sync`.

And nothing else: **no framework code, no framework path.** A workflow step reads
`<declared command> <verb>`, never `python3 scripts/<x>.py`.

### Two kinds of interface, one shape of contract

- **Command ports** (Gate, Rules, Evals, Security): the protocol of `contract/gate/v1` — a verb,
  JSON on stdin, one JSON result on stdout, exit 3 for "cannot run here". The tenant names the
  command; CI installs the provider by the provider's own pinned setup step.
- **Wire ports** (Records, Telemetry, Ops records): HTTP or OTLP with a published payload schema.
  The tenant sends data; it runs nothing of the provider's.

Every contract lives at `contract/<port>/v<N>/` with `protocol.md`, JSON schemas, golden cases and
a conformance runner (`agentsmith conformance --port <port> --provider "<command>"`), exactly as the
gate's does — so "another platform can provide this" is checkable, and AgentSmith's own
implementation is scored by the same cases.

### Failure semantics, per port — stated, not inherited

| Port | When the provider cannot answer |
|---|---|
| Gate | **closed** — the edit, commit, push or CI step is refused |
| Rules | **closed in CI** (drift is a failure), open in a session (the rules already rendered stand) |
| Evals, Security | **closed in CI** — a verdict that did not run is not a pass |
| Records, Ops records | **open, and said** — the run continues and the step reports that nothing was sent |
| Telemetry | **open** — never blocks a commit or a request |

### The slices, each paired with the tenant that proves it

OTS is the proving ground: its core function is frozen until its governance is aligned, so each
slice ends with OTS deleting the coupling that slice replaced. A slice is not done until a real
tenant runs on it — the scratch tenants for breadth, OTS for depth, KYC where it applies.

| # | AgentSmith | The tenant step that proves it |
|---|---|---|
| **C1** | **Gate v2 — the CI event.** `<gate> ci --base --head` in the contract, with the dev record as its output; a provider setup step for CI; `agentsmith-gates.yml` calls the declared command | OTS declares `providers.json`, its CI calls the provider, its vendored `process_gate.py`, `gate_*.py` and `requirements-gate.txt` go. KYC pins a release and calls the command |
| **C2** | **Gate v2 — commit-msg, sweep, pre-push**, and the knowledge graph as gate evidence (graph schema published; the provider computes the `KG query:` hash) | the hooks in OTS and KYC become stubs that call the declared command; `map_codebase.py` leaves OTS |
| **C3** | **Records** — `contract/record/v1`: the dev record schema (already `schema: 1`), the endpoint, auth, no-redirect, retry | the CI step sends by contract; `send_dev_record.py` is never a tenant's file |
| **C4** | **Rules** — `contract/rules/v1`: the tenant's own rules (`extends`), the managed-block markers; `<rules> render` and `<rules> check`. The registry stays the gate provider's policy, not a published document a tenant may hold (`rules-contract.md`) | OTS's tenant rules move into its declaration and its CI calls the declared check; its vendored `templates/` and `generate-ide-config.py` are then read by nothing, and leave with vendoring at C9 |
| **C5** | **Telemetry** — `contract/telemetry/v1`: resource and span attributes as a schema (from the Wire Contract table), OTLP, a conformance check over exported spans | OTS's `tracing.py` uses plain OpenTelemetry against the schema; vendored `runtime/` goes |
| **C6** | **Evals** — `contract/evals/v1`: dataset format the tenant owns, suites, the verdict and scorecard schema, threshold semantics; `<evals> run` | OTS's eval workflows call the declared command against its own datasets |
| **C7** | **Security** — `contract/security/v1`: the `SEC-*` control registry, evidence packs, the harness verdict, the redaction check; `<security> check` | OTS's security and redaction steps call the command; vendored `fixtures/security/` goes |
| **C8** | **Ops records** — `contract/ops/v1`: run history out, HITL and UI feedback in, over HTTP — the base the portal's Ops and HITL work builds on | OTS's CD workflows send and receive by contract; the two sync scripts go |
| **C9** | **Vendoring retired.** `sync` and `upgrade` stop vendoring; `upgrade` is removed; `install-ai-stack.sh` installs the provider, not a tenant's copy | no tenant holds a framework file: a check in `verify_system --governed` fails if one does |

C1 goes first because every tenant's CI depends on it and it removes the largest copy. C2–C3 finish
Dev; C4 is shared; C5–C8 are Ops; C9 closes the transport once nothing needs it.

### The runtime library is not a port

The gateway, HITL gate and dead-letter queue are an **optional, versioned library**
(`agentsmith-runtime`), chosen by the tenant's own code like any dependency. A tenant must be fully
governable without it. KYC's pinned package dependency is fine under this principle; its unpinned
CI checkout is not.

### Decisions I am taking, each reversible

1. **New gate events are contract 2, not contract 1.** v1 says an unknown event gets no decision and
   the caller "may try the next one"; for a commit or CI check that would mean falling back to
   AgentSmith's own paths — the coupling this removes. A v1 provider stays valid for the three
   editing events; `providers.json` states the contract per port.
2. **The knowledge graph belongs to the gate.** It exists to scope a review, and the review is the
   gate's; the graph's schema is published so a tenant's committed graph is data, not a
   framework artefact.
3. **CI installs the provider by the provider's own pinned setup step** (for AgentSmith, a setup
   action at a release tag), never by a raw checkout of its repository at `main`.
4. **Vendoring is deprecated now and removed at C9.** No new tenant is vendored; `adopt` is already
   the default.

**Deliberately not done here:** the portal's own administration and HITL screens (they consume C8,
and are their own designs); a public contract repository (it moves out the day a second platform
adopts one, as `governance-providers.md` decided); anything in OTS's core function.

## Pillars

- P1 applies — `.agent-rfc/designs/governance-providers.md` is the architecture this finishes; the owner's principle and the measured coupling are in Problem, and every slice will have its own design before code.
- P2 applies — `contract/gate/v1/protocol.md` is the shape every new contract copies — verb, JSON in, one result out, exit 3 — and the conformance runner `agentsmith conformance` is extended, not duplicated. No dependency is added by this document.
- P3 applies — `CHANGELOG.md`'s Wire Contract table is what C5 publishes as a schema; each command port's slice states the span its provider emits per invocation.
- P4 applies — `contract/gate/v1/cases.json` is the model: every contract ships golden cases and a conformance run, AgentSmith's own implementation is scored by them, and each slice ends with a real tenant (scratch tenants, OTS, KYC) running on it.
- P7 n/a — no code in this design; each slice answers it for its stack.
- P8 applies — `CHANGELOG.md`'s Wire Contract table: telemetry stays OTLP with documented attributes; C5 turns the table into a schema rather than inventing a wire.
- P9 n/a — no orchestration.
- P10 n/a — no model call; the evals contract (C6) names the judge as provider configuration, never a tenant-side import.
- P11 applies — `contract/gate/v1/protocol.md`'s rule carries over: a provider command comes from the tenant's committed declaration, and an operator escape is an operator's variable, never fetched content.
- P12 applies — `scripts/send_dev_record.py` is the pattern for wire ports: endpoints and tokens are environment variables read by name, redirects refused; a contract names a credential's variable, never its value.
- P13 applies — `.githooks/process-gate` fails closed today when no provider answers; the per-port failure table above makes every port's mode explicit, and contract 2 exists precisely so a commit or CI check never falls back to an unpinned path.
- P14 applies — `contract/gate/v1/fixture.json` shows the rule: each contract's fixture carries everything its decisions depend on, so a run needs nothing from any provider's installation and no baseline drifts with AgentSmith.
- P15 applies — `contract/gate/v1/protocol.md` distinguishes "declared none" from "could not run"; every port keeps that distinction, and the wire ports report "nothing sent" rather than succeeding silently.
- P16 applies — `contract/gate/v1/providers.schema.json` lets a tenant pin each port separately, so a tenant can move port by port and stop at any slice; vendored tenants keep working until C9, which ships only when no port needs vendoring.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the README's "contracts in place" become published schemas with conformance runs; a contract nobody can check is a description.
- `implemented-not-invoked` — each slice is done only when a real tenant runs on it and deletes the coupling it replaced.
- `single-source-of-truth` — each interface is defined once, under `contract/`, and AgentSmith's implementation is scored against it like anyone else's.
- `gate-integrity` — contract 2 for the new gate events, because v1's fall-through would route a commit or CI check back to AgentSmith's paths.
- `small-verified-slices` — nine slices, each with its own design, review and pull request, each proven on a tenant.
- `two-owners-two-cadences` — the contract and the provider version separately; the tenant pins the contract.
- `failure-is-not-a-result` — the per-port failure table; a verdict that did not run is never a pass.
