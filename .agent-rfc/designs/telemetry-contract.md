---
status: done
scope:
  - contract/telemetry/v1/**
  - runtime/telemetry_contract.py
  - runtime/tracing.py
  - templates/agent-rules.yaml
  - templates/governance.json
  - runtime/conformance.py
  - runtime/cli.py
  - portal/lib/spanIdentity.ts
  - portal/test/**
  - portal/package.json
  - scripts/test/**
  - runtime/test/**
  - scripts/mutation_check.py
  - .agenticframework/process-gates.json
  - .github/actions/setup-agentsmith/action.yml
  - workflow-templates/agentsmith-sync.yml
---
# C5 — The telemetry contract: what a tenant's spans and metrics carry

Slice C5 of `.agent-rfc/designs/governance-contracts.md`, the first Ops port. A tenant **emits**
telemetry; it runs nothing of a provider's. So this is a wire contract, like C3's record: OTLP, with a
published catalogue of the attributes and instruments a governed application emits — so a tenant can
emit with plain OpenTelemetry instead of importing AgentSmith's code, and anything that reads the
telemetry (Phoenix dashboards, the portal) reads a published shape.

## Problem

Measured on 2026-10-04:

- **The shape exists only as code and prose.** `runtime/tracing.py`, `runtime/llm_gateway.py`,
  `runtime/metrics.py`, `runtime/prompt_identity.py`, `runtime/vector_store.py` and
  `runtime/embeddings.py` set about fifty span attributes and eleven metric instruments (counted when building: the
  first count, eight, missed the three retrieval instruments); the CHANGELOG's
  Wire Contract table lists thirteen rows of them, by hand, with no check that either matches the
  other. Nothing tells a tenant which attributes are required, which are optional, or which carry a
  payload the redactor must see.
- **The only way to emit it is to import AgentSmith.** `resource_attributes()`, the
  `AgentIdentityProcessor` that puts `tenant.id`, `agent.role` and `run.id` on every span, and the
  OTLP endpoint resolution live in the runtime library. OTS's span code (`services/templates/tracing.py`,
  in its uncommitted template work) imports `runtime.tracing`, `runtime.tenancy` and `runtime.otlp`
  **from its vendored copy** — the coupling this programme removes.
- **A reader cannot tell an old emitter from a broken one by contract.** `agentsmith.framework.version`
  on the Resource says which AgentSmith emitted a span — meaningful only to an emitter that *is*
  AgentSmith. A tenant on plain OpenTelemetry has no way to say which shape it emits.
- **Nobody checks an emitter.** No test holds the runtime's spans to the table, and nothing could
  score a tenant's.

**Correcting the umbrella's premise.** Its C5 row says OTS's `tracing.py` is tenant code importing the
vendored `runtime/`. OTS's **committed** code imports nothing from `runtime/` — verified; `runtime/tracing.py`
there is the vendored file itself. The one importer is `services/templates/tracing.py`, part of OTS's
uncommitted template-model work, which is frozen. KYC Sentinel emits through the runtime **library**,
pinned as a package dependency — which the umbrella already allows ("The runtime library is not a port").

## Approach

### `contract/telemetry/v1/` — a wire contract

- **`protocol.md`** — telemetry travels as **OTLP** (HTTP; the standard `OTEL_EXPORTER_OTLP_*`
  variables configure it, and the contract names no endpoint or credential). What an emitter
  promises: the Resource attributes, the identity on every span emitted inside a run, the catalogued
  meaning and type of any attribute it uses, W3C `traceparent` propagation on outgoing calls, and that
  **payload attributes** are subject to its redaction profile. What a reader promises: an attribute
  it does not know is ignored; a missing optional attribute is "not emitted", never a fault.
  **Failure is open**: telemetry never blocks a commit or a request (umbrella's table).
- **`attributes.json`** — the catalogue, one entry per name: `where` (`resource`, `span`, `metric`
  instrument, `metric` attribute), `type`, `requirement` (`required`, `required_in_run`, `optional`,
  `conditional` with the condition — e.g. the token counts only when `llm.usage.reported` is true),
  `payload` (a value the redactor must see), `since` (the framework release that first emitted it)
  and a one-line meaning. Instruments carry their unit and kind. Some names are **families**, not
  single names: `agent_span(**attributes)` writes a tenant's own keys under `agent.`, the gateway
  writes `llm.gateway.input_guardrail.<kind>`, retrieval `retrieval.<backend>`. A family is one
  entry with a prefix, and says whether its members are the tenant's to name (`agent.`) or fixed by
  the emitter. **`catalogue.schema.json`** is
  generated from the model that reads it (`runtime/telemetry_contract.py`).
- **One new Resource attribute, `governance.telemetry.contract`** (`1`): which contract this emitter
  speaks, whoever wrote it. `agentsmith.framework.version` stays, `optional` — meaningful when the
  emitter is AgentSmith's library. A Resource without the contract attribute is a pre-contract
  emitter, and conformance says so.
- **`fixture.json` and `cases.json`** — a golden OTLP/JSON export of one representative run
  (resource, a step span, an LLM span with usage, a tool span, a retrieval span, metrics), and cases
  that each change one thing a judge must notice: the contract attribute missing, `tenant.id` missing
  from a span inside a run, a token count without `llm.usage.reported`, a required attribute of the
  wrong type, an unknown attribute (allowed and noted), a payload attribute (named in the report;
  whether it was redacted is C7's to verify).

**Deliberately version 1 is what AgentSmith emits today.** Moving the `llm.*` names to OpenTelemetry's
GenAI semantic conventions (`gen_ai.*`) is a later version, done with a mapping period; renaming in
the same slice that publishes would break every dashboard that reads the current names.

### Held on both sides

- **Emitters → catalogue.** A test inventories every literal attribute name set in `runtime/`
  (`set_attribute`, the gateway's attribute dicts, `agent_span` keywords) and every metric instrument,
  and requires each in `attributes.json`; the gate's spans (`scripts/gate_tracing.py`) and the
  portal's (`portal/lib/spanIdentity.ts`, its Resource) are held the same way. A new attribute cannot
  ship uncatalogued.
- **Catalogue → readers.** What the portal reads from spans (`portal/lib/promotions.ts`:
  `input.value`, `output.value`) is pinned to the catalogue by a portal test, as C3 pinned its record.
- **The Wire Contract table** in CHANGELOG.md is pinned: each of its span, Resource and metric rows
  names catalogued attributes with the same `since`.
- **`runtime/tracing.py`** emits `governance.telemetry.contract` from `resource_attributes()`, and the
  portal's `resourceAttributes()` does too.

### Pillar 8's own words

`templates/agent-rules.yaml` asks every design "does it resolve the endpoint through
`runtime/otlp.py`?", and its rule describes that module falling back to the endpoint
`agentsmith dashboard start` records on a machine. Both name AgentSmith's code as the way to emit —
the coupling this contract removes, written into the rules every tenant is held to. The question
becomes whether the endpoint comes from the standard `OTEL_EXPORTER_OTLP_*` variables (the runtime
library's `runtime/otlp.py` is one way to read them), and the rule names the contract; the registry
is regenerated from it. OTS's design met exactly this when it stopped importing that module.

### Found while building: the provider ran a vendored tenant's CLI

Verifying OTS's spans through `--emitter` from OTS's own directory ran OTS's vendored
`runtime/cli.py`, not the provider's. `python -m` puts the working directory first on the module
path, ahead of `PYTHONPATH` — so the `agentsmith` shim that `.github/actions/setup-agentsmith`
writes in CI (C1), and the test suite's `scripts/test/provider_shim.py`, both answer with a vendored
tenant's own copy when run inside one. In OTS's CI, `agentsmith gate ci` would have reached a
two-month-old CLI that has no `gate` command. Both shims run Python with `-P` (3.11+: no unsafe path
first), and a test runs each shim from a directory holding a decoy `runtime/` and asserts the
provider's module answered. Its sibling, the weekly sync workflow (`workflow-templates/agentsmith-sync.yml`),
ran `python3 -m runtime.cli sync` from the tenant's workspace — a vendored tenant's own `sync` —
and takes `-P` too. The installed console script is unaffected — its path starts at its
own directory.

### Conformance — `agentsmith conformance --port telemetry`

- **`--export FILE`** judges an OTLP/JSON export (a collector's file exporter, a Phoenix export).
- **`--emitter "<command>"`** stands up a loopback OTLP/HTTP receiver (protobuf and JSON, size-
  capped, loopback only), runs the command with `OTEL_EXPORTER_OTLP_ENDPOINT` pointed at it, and
  judges what arrives — nothing received is a failure, not a pass.

Both report per check: the Resource; identity on spans inside a run (a span is inside a run when it
carries `run.id` or descends from one that does); types; conditionals; payload attributes named;
unknown attributes listed as notes. The runtime library is scored by both — its spans exported from
an in-memory provider as OTLP, and a stub emitter through `--emitter`; two stub emitters that break
it (no contract attribute, a span without `tenant.id`) are shown to fail.

### The tenant steps that prove it — after the release that carries it

- **OTS — done ahead of the build, at the owner's direction (2026-10-04)**: a governance-only change
  to `services/templates/tracing.py`, under OTS's own design and review
  (`telemetry-contract-tenant.md` there). Plain OpenTelemetry, the catalogue's names,
  `governance.telemetry.contract` on the Resource and a per-process `run.id`; its public surface
  unchanged, so no caller or test changed; its 6 tracing tests pass, and removing the `tenant.id`
  stamp fails 4 of them. Not committed — the file is part of the frozen, uncommitted template work.
  `agentsmith conformance --port telemetry --emitter "ots-templates …"` judges it once this ships.
  OTS's own code now imports nothing from its vendored `runtime/`, which leaves at C9.
- **KYC Sentinel**: stays on the library (allowed); its pin moves to the release carrying C5, and its
  smoke job's export passes `--export`. On v1.3.0 it emits no contract attribute and fails — which is
  the case the attribute exists to make visible.

**Deliberately not done:** redaction is *named* here (payload attributes) and *verified* by C7's
redaction check; the run-status POST and its `frameworkVersion` are Ops records (C8); no
`providers.json` entry — a tenant runs nothing of a telemetry provider's, and nothing would read it
(C3's reasoning); no CI step in the gates workflow — an emitter command is the tenant's own, so a
tenant adds `--emitter` to its CI by choice, documented.

## Pillars

- P1 applies — `.agent-rfc/designs/governance-contracts.md` defines C5 and is amended for the OTS premise; `CHANGELOG.md`'s Wire Contract table is what this publishes; this design precedes the code.
- P2 applies — `runtime/conformance.py` gains the port rather than a second runner; `runtime/otlp.py` keeps endpoint resolution as the library's; the OTLP decoder is `opentelemetry-proto`, already installed with the exporter. KG impact over the scope is recorded in the review.
- P3 applies — `runtime/tracing.py` `resource_attributes()` gains `governance.telemetry.contract`; no new span is emitted, and the catalogue is what P3's "every span carries tenant.id, agent.role, run.id" becomes in data.
- P4 applies — `runtime/conformance.py`'s telemetry suite runs against the runtime library and two stub emitters that must fail; the inventory test fails on an uncatalogued attribute. Mutations: an inventory that skips a module, a judge that ignores identity, a receiver that passes on nothing received, a conditional never checked, the Resource attribute dropped.
- P7 applies — `runtime/telemetry_contract.py`: the catalogue entries are Pydantic V2 models and the schema is generated from them; the portal stays TypeScript, checked against the published file.
- P8 applies — `templates/agent-rules.yaml`'s P8 question and rule stop naming `runtime/otlp.py` as the way to emit; `runtime/otlp.py` stays the library's one endpoint resolver; the contract names only the standard `OTEL_EXPORTER_OTLP_*` variables, and this is the slice that makes the wire itself the published interface.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call; the catalogue describes the gateway's attributes without changing them.
- P11 applies — `runtime/conformance.py`'s receiver parses OTLP bodies it did not write: bound to loopback, size-capped, a body that does not decode is a failed check and never a crash.
- P12 n/a — no credential read or written; the contract names `OTEL_EXPORTER_OTLP_HEADERS` as where an emitter's collector credential goes, never a value.
- P13 n/a — no gate check is added or weakened; telemetry is open by the umbrella's table.
- P14 applies — `contract/telemetry/v1/fixture.json` is a new golden; the Wire Contract table is pinned to the catalogue rather than kept beside it by hand.
- P15 applies — `runtime/conformance.py` reports "nothing received" as a failure and an unknown attribute as a note, so an emitter that exports nothing never reads as conformant.
- P16 n/a — no fallback added: telemetry already degrades to a no-op when OpenTelemetry is absent, and that is unchanged.

## Deviations

none

## Dependencies

none — `opentelemetry-proto` comes with `opentelemetry-exporter-otlp-proto-http`, already in `requirements.txt` and the lock.

## Levers

- `single-source-of-truth` — one catalogue; the schema, the table's pin, the emitter inventory and the reader pin all read it.
- `pin-unremovable-duplicates` — the portal's TypeScript and the CHANGELOG table cannot be generated away, so each is pinned to the catalogue.
- `declared-vs-enforced` — the Wire Contract table becomes data an inventory test and a conformance run enforce.
- `denied-vs-missing` — "not emitted by this contract", "pre-contract emitter" and "nothing received" are different results.
- `test-the-contract` — the runtime library is scored by the same suite a tenant would be.
- `guards-must-be-able-to-fail` — two stub emitters are shown failing.
- `validate-on-the-receiving-side` — the loopback receiver treats every body as untrusted.
