"""
runtime/worker.py — Production worker entrypoint.

Starts a Temporal or Celery worker partitioned by tenant.id.
All LLM calls route through llm_gateway.py — cost_router.py is NOT used here.
All spans carry tenant.id, workflow.id, workflow.run_id.

See SPECS.md §25 for the full production runtime specification.

TODO (Phase 2):
  - Implement Temporal activity registration
  - Implement Celery app factory (fallback)
  - Wire OTel provider with trace_redactor processor
  - Read tenant partition from TENANT_ID env var or tenant.yaml
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    """
    Worker entrypoint. Reads WORKER_BACKEND from environment:
      - 'temporal' (default): start Temporal worker
      - 'celery':             start Celery worker

    TENANT_ID must be set for production workers.
    """
    backend = os.environ.get("WORKER_BACKEND", "temporal").lower()
    tenant_id = os.environ.get("TENANT_ID", "")

    if not tenant_id:
        print("[worker] ERROR: TENANT_ID environment variable is required.", file=sys.stderr)
        sys.exit(1)

    print(f"[worker] Starting {backend} worker for tenant={tenant_id}")

    if backend == "temporal":
        _start_temporal_worker(tenant_id)
    elif backend == "celery":
        _start_celery_worker(tenant_id)
    else:
        print(f"[worker] ERROR: Unknown WORKER_BACKEND={backend!r}", file=sys.stderr)
        sys.exit(1)


def _start_temporal_worker(tenant_id: str) -> None:
    """
    TODO Phase 2: Implement Temporal worker.

    Required:
      pip install temporalio

    Pattern:
      async with Client.connect(os.environ["TEMPORAL_ADDRESS"]) as client:
          worker = Worker(
              client,
              task_queue=f"agent-tasks-{tenant_id}",
              workflows=[AgentWorkflow],
              activities=[architect_activity, developer_activity, validator_activity],
          )
          await worker.run()
    """
    raise NotImplementedError(
        "Temporal worker not yet implemented. See SPECS.md §25 and runtime/workflows/."
    )


def _start_celery_worker(tenant_id: str) -> None:
    """
    TODO Phase 2: Implement Celery worker.

    Required:
      pip install celery redis

    Pattern:
      app = Celery("agent_worker", broker=os.environ["REDIS_URL"])
      app.conf.task_routes = {
          "runtime.tasks.*": {"queue": f"agent-{tenant_id}"}
      }
      app.worker_main(argv=["worker", "--loglevel=info"])
    """
    raise NotImplementedError(
        "Celery worker not yet implemented. See SPECS.md §25."
    )


if __name__ == "__main__":
    main()
