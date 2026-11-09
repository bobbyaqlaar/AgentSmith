---
status: active
scope:
  - agentsmith/llm_gateway.py
  - agentsmith/tracing.py
  - agentsmith/telemetry_contract.py
  - contract/telemetry/**
  - scripts/test/test_gen_ai_telemetry.py
---
# OpenTelemetry's GenAI names beside AgentSmith's own

Gap 7 of `docs/PRODUCT_BACKLOG.md`.

## Problem

`contract/telemetry/v1` defines its own attribute names (`llm.model_name`, `llm.usage.*`). Every observability tool now reads OpenTelemetry's GenAI conventions, so AgentSmith's traces are opaque to them unless someone maps the names by hand.

## Approach

Emit both, as `contract/telemetry/v1/protocol.md` already promised. The `llm.*` names stay the contract's required names in version 1, and the GenAI names are optional additions. A reader that does not know them ignores them.

**Pinned.** The conventions moved in June 2026 to `open-telemetry/semantic-conventions-genai`, which has no tagged release. Every name used is marked `development` there. They are pinned to commit `e6658f14c9d9` (schema `gen-ai-dev/1.42.0-dev`), named once in `agentsmith/telemetry_contract.py` and in the protocol. A rename upstream is then a deliberate change here, not drift.

**What is emitted:**

| On | GenAI name | From |
|---|---|---|
| a gateway call | `gen_ai.operation.name` = `chat` | always |
| | `gen_ai.request.model` | the model id, as `llm.model_name` |
| | `gen_ai.provider.name` | the model id's provider prefix, mapped to the conventions' values (`gemini` → `gcp.gemini`, `bedrock` → `aws.bedrock`); a provider they do not list keeps its own lowercase name, as they allow; no prefix, no attribute |
| | `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | only when the provider reported usage, like `llm.usage.*`; optional in the catalogue rather than conditional, so no other emitter is held to them |
| a tool call | `gen_ai.operation.name` = `execute_tool`, `gen_ai.tool.name` | as `agent.tool.name` |

## Pillars

- P1 applies — `docs/PRODUCT_BACKLOG.md` gap 7 is the requirement; `.agent-rfc/designs/gen-ai-telemetry.md` is the plan.
- P2 applies — `agentsmith/telemetry_contract.py` holds the pin and the provider map; no new dependency.
- P3 applies — `agentsmith/llm_gateway.py` and `agentsmith/tracing.py` write the names on the spans they already open.
- P4 applies — `scripts/test/test_gen_ai_telemetry.py` reads real spans from an in-memory exporter; mutation-checked by hand.
- P7 applies — `contract/telemetry/v1/attributes.json` is validated by its schema, and `scripts/test/test_telemetry_contract.py` holds every emitted name to it.
- P8 applies — `contract/telemetry/v1/attributes.json` gains optional entries; no required name moves.
- P9 n/a — no orchestration change.
- P10 n/a — no routing change; the provider is read from the id, not chosen.
- P11 n/a — no untrusted content is read.
- P12 n/a — no secrets involved.
- P13 n/a — no gate changes.
- P14 applies — `scripts/test/test_telemetry_contract.py` fails on an emitted name the catalogue does not have.
- P15 applies — `scripts/test/test_gen_ai_telemetry.py` holds that unreported usage writes no GenAI token count, never a zero.
- P16 applies — `CHANGELOG.md` names the names; additive, so reverting is one commit.

## Deviations

none

## Dependencies

none

## Levers

- `single-source-of-truth` — one pin, one provider map.
- `failure-is-not-a-result` — no usage is no count, never zero.
- `test-that-cannot-fail` — hand mutants.
