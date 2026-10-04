# The telemetry contract, version 1

A governed application **emits** telemetry; it runs nothing of a provider's. This contract is what
its spans and metrics carry, so an application can emit with plain OpenTelemetry instead of
importing AgentSmith's code, and anything that reads the telemetry — dashboards, the Ops Portal —
reads a published shape. AgentSmith's runtime library is one emitter; it is judged like any other.

## The wire

**OTLP** — traces and metrics, over HTTP (protobuf or JSON), configured by OpenTelemetry's own
variables: `OTEL_EXPORTER_OTLP_ENDPOINT`, or the per-signal `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and
`…_METRICS_ENDPOINT`; a collector's credential goes in `OTEL_EXPORTER_OTLP_HEADERS`. The contract
names no endpoint and no credential, and an emitter reads none from a provider's install.

Outgoing calls carry the W3C `traceparent`, so a trace follows a request across processes.

## The catalogue

`attributes.json` (shape: `catalogue.schema.json`) defines every name, one entry each:

| Field | Means |
|---|---|
| `where` | `resource`, `span`, `span_name`, `event`, `metric` (an instrument) or `metric_attribute` |
| `type` | `string`, `int`, `double`, `number` (either), `bool`, `string[]` |
| `requirement` | `required` (on spans: those whose name starts with `applies_to`), `required_in_run`, `conditional`, `optional` |
| `when` | for `conditional`: the attribute is present **exactly** when these attributes have these values |
| `family` | the name is a prefix; `open` when its members are the emitter's own to name |
| `payload` | the value can carry content a redaction profile must see |
| `instrument`, `unit` | for an instrument |
| `since` | the AgentSmith release that first emitted it, where that is recorded |

**What an emitter promises:**

- **The Resource** carries `service.name`, `project.name`, `environment` (`development`, `staging`,
  `production` — unset or unknown is production) and **`governance.telemetry.contract: 1`**, which
  says which contract it speaks. A Resource without it is a pre-contract emitter.
- **Every span inside a run** carries `tenant.id`, `agent.role` and `run.id`. A span is inside a run
  when it, or an ancestor, carries `run.id`. Identity is per span, never on the Resource of a
  process that serves many tenants or roles.
- **A span of a kind** carries what that kind requires: an LLM span (`llm.<role>`) its model, tier
  and `llm.usage.reported`; a tool span (`agent.tool.<name>`) its name and whether it was allowed.
- **Conditional attributes** appear exactly when their condition holds: token counts only when
  `llm.usage.reported` is true — an unreported count is absent, never `0`.
- **Every catalogued name** has its catalogued type and, for an instrument, its kind and unit.
- **Payload attributes** (`input.value`, `output.value`) pass through the emitter's redaction
  profile. Version 1 names them; the security contract verifies the redaction.

**What a reader promises:** a name it does not know is ignored; a missing optional attribute means
"not emitted", never a fault; and it keys on `governance.telemetry.contract`, not on which product
emitted the spans.

**Failure is open.** Telemetry never blocks a commit, a deploy or a request: an emitter that cannot
export says so and carries on.

## Conformance

```bash
agentsmith conformance --port telemetry --emitter "<command>"   # run it against a loopback receiver
agentsmith conformance --port telemetry --export spans.json     # judge an OTLP/JSON export
```

`--emitter` runs the command with its OTLP destination pointed at a receiver on 127.0.0.1 — its own
destinations removed, so nothing leaves the machine — and judges what arrives. **Nothing received is
a failure**, and so is a body that is not OTLP. `--export` reads one OTLP/JSON object, or one per
line (a collector's file exporter). Both report each promise above as a check, and list names the
catalogue does not know and payload attributes as notes.

`fixture.json` is one representative run exported by AgentSmith's library; `cases.json` changes one
thing in it per case, and says which check must fail — the judge's own test, for any platform that
writes one.

## What is not in version 1

The names are those AgentSmith emits today; moving the `llm.*` attributes to OpenTelemetry's GenAI
semantic conventions is a later version, with a period that emits both. Log records are not
judged. The run-status report a tenant posts to the portal is the Ops records contract.
