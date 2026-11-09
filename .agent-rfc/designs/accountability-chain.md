---
status: done
scope:
  - agentsmith/version.py
  - agentsmith/ops_contract.py
  - agentsmith/llm_gateway.py
  - agentsmith/tracing.py
  - agentsmith/compliance.py
  - contract/ops/**
  - contract/telemetry/**
  - portal/**
  - workflow-templates/cd-production.yml
  - workflow-templates/cd-staging.yml
  - scripts/test/test_ops_contract.py
  - scripts/test/test_app_commit.py
---
# A production run links to the commit behind it

Gap 2 of `docs/PRODUCT_BACKLOG.md`.

## Problem

The portal's commit page shows a commit's verdict, its design, each deviation and who approved it. Nothing connects a production run to that page, because a run carries no commit. So "why does this agent do that?" cannot be answered from a run.

## Approach

**The commit comes from the deployment.** A new `APP_COMMIT` environment variable, which the deploy templates set from the commit CI validated. `version.app_commit()` reads it and returns only a 7 to 40 character hash. Anything else is treated as unset: a value nobody can look up is not a link.

**It travels two additive ways.** `RunMessage` gains an optional `app_commit`, validated by the same pattern on both sides of the Ops contract. Traces gain an `app.commit` resource attribute when it is set.

**The portal joins, and decides nothing.** `agent_runs.app_commit` is stored beside `framework_version` and kept by `COALESCE` the same way. The app's Ops page gains a Recent runs list, each linking to `/dev/apps/<app>/commits/<sha>`, where the design and approvals already are. That commit page gains the reverse: how many runs came from it and when the last one was. A run without a commit says "not reported". That is different from a commit the gate never saw, which the commit page already explains.

Only the Ops contract carries it. The deprecated `/api/runs/ingest` route is unchanged.

## Pillars

- P1 applies — `docs/PRODUCT_BACKLOG.md` gap 2 is the requirement; `.agent-rfc/designs/accountability-chain.md` is the plan.
- P2 applies — `agentsmith/version.py` holds the reader beside `framework_version`; no new dependency or service.
- P3 applies — `agentsmith/tracing.py` puts `app.commit` on the Resource, with the reasoning `agentsmith.framework.version` already gives for per-process values.
- P4 applies — `scripts/test/test_app_commit.py`, `scripts/test/test_ops_contract.py` and `portal/test/opsIngestDb.test.ts` pin both sides; mutation-checked by hand.
- P7 applies — `agentsmith/ops_contract.py` is the Pydantic model the published schema is generated from.
- P8 applies — `contract/telemetry/v1/attributes.json` gains one optional resource attribute; a reader ignores what it does not know.
- P9 n/a — no orchestration change.
- P10 n/a — no routing change.
- P11 applies — `portal/lib/opsIngest.ts` refuses a value that is not a hash, so nothing but hex reaches a link or a query.
- P12 n/a — a commit hash is not a secret.
- P13 applies — `portal/lib/opsIngest.ts` keeps the token as the only thing deciding whose run it is; `app_commit` cannot name another app.
- P14 applies — `contract/ops/v1/message.schema.json` is regenerated from the model; `scripts/test/test_ops_contract.py` holds them equal.
- P15 applies — `portal/test/opsIngestDb.test.ts` holds that a missing commit is stored as NULL and shown as not reported, never as a commit.
- P16 applies — `portal/db/schema.sql` adds a nullable column with `ADD COLUMN IF NOT EXISTS`, and `CHANGELOG.md` names it.

## Deviations

none

## Dependencies

none

## Levers

- `implemented-not-invoked` — the deploy templates set the variable, and the pages read the column.
- `failure-is-not-a-result` — a run with no commit is reported as that.
- `test-that-cannot-fail` — hand mutants on both sides.
