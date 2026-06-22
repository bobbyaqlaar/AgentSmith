# Oil Price Agent — Domain Agents

## Architecture

```
IngestionAgent  →  PredictionAgent  →  DecisionAgent
      │                  │                  │
   Fetches            Runs ML            Places
   price data         model              order /
   from APIs          forecast           alerts
```

## HITL Triggers

- Price anomaly > 3 standard deviations: pause workflow, alert ops team
- Model confidence < 0.6: pause for human review before order

## Temporal Workflow

See `../workflows/oil_price_workflow.py` and `../workflows/activities.py`,
built on the generic pattern in `runtime/workflows/base_workflow.py` (§25).
Worker bootstrap: `../worker.py`. Cron schedule: `../.agenticframework/schedules.yaml`.

## Status

Phase 2 — reference Temporal workflow implemented (ingestion/prediction/decision
activities, HITL signal + DLQ timeout). Domain logic (real price feed, real
forecasting model, real order placement) is left as TODOs for the tenant fork —
see inline `# TODO (tenant implementation)` markers in `../workflows/activities.py`.
