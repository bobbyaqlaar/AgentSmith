# The runtime contract, version 1

How an application not written in Python reaches the compliance guards. It runs `agentsmith runtime serve` beside itself and calls it over
localhost, so every stack gets one implementation of the guards.

Bound to `127.0.0.1`. Every `POST` carries `Authorization: Bearer $AGENTSMITH_RUNTIME_TOKEN`.

| Call | Body | Answer |
|---|---|---|
| `POST /v1/complete` | `prompt`, `data_class` (required), `model_hint`, `workflow_id`, `user_id`, `max_tokens`, `temperature` | The completion, with `ai_generated` and `provenance` |
| `POST /v1/running` | `workflow_id` | `{"running": true}` |
| `POST /v1/record` | `kind`, `payload` | `{"record_id": N}` |
| `POST /v1/gate/request` | `gate_id`, `workflow_id`, `action`, `input`, `requested_by` (required) | `{"status": "pending"}` |
| `POST /v1/gate/status` | `gate_id`, `workflow_id` | `{"status": "pending" \| "approved" \| "rejected", "decision": {...}}` |
| `POST /v1/gate/timeout` | `gate_id`, `workflow_id` | Takes the gate off the reviewers' queue |
| `GET /healthz` | none | `{"ok": true, "profile": bool}` |

**Anything but a 200 means do not act.** `403` is a refusal, naming the obligation: `{"refused": true, "obligation": "OB-RESIDENCY", "reason": "..."}`. `401` is a bad token, `400` a bad
request, `5xx` that the guards could not run.

An application cannot record `hitl_pending`, `hitl_decision`, `hitl_timeout`, `stop_control`, `model_call` or `model_result` through `/v1/record`.

**Human gates.** Call `/v1/gate/request`, poll `/v1/gate/status`, and act only on `approved`. Run `agentsmith/replay_webhook_server.py` with `HITL_DECISION_BACKEND=store`, so the portal's signed decision is stored where the sidecar reads it.

The moderation hook and the name guardrail are Python modules the sidecar loads, named in `tenant.yaml`.

Conformance: `agentsmith conformance --port runtime --receiver http://127.0.0.1:8765`.
