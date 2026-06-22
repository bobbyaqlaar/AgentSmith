"""
runtime/dead_letter.py — Dead-letter queue and replay API.

Failed activities that exhaust retries are moved here.
DLQ entries surface in the Ops Portal unresolved queue.

Operations:
  enqueue(task_id, payload, error, tenant_id)  — add failed task to DLQ
  list(tenant_id, limit)                        — list DLQ entries
  replay(task_id)                               — re-submit to workflow engine
  discard(task_id)                              — mark resolved, remove from DLQ

See SPECS.md §25 for the full specification.

TODO (Phase 2):
  - Implement Postgres-backed store (recommended for auditability)
  - Implement Ops Portal API endpoint for DLQ surfacing
  - Implement replay to Temporal or Celery
  - Add TTL and auto-archive for old resolved entries
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional
import uuid


@dataclass
class DLQEntry:
    task_id: str
    tenant_id: str
    payload: Any
    error: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    replayed_at: Optional[str] = None
    discarded_at: Optional[str] = None
    status: str = "pending"   # pending | replayed | discarded


class DeadLetterQueue:
    """
    Dead-letter queue for failed production activities.

    Instantiate once per worker process.
    """

    def __init__(self) -> None:
        # TODO Phase 2: connect to Postgres or Redis store
        pass

    def enqueue(
        self,
        payload: Any,
        error: str,
        tenant_id: str,
        task_id: Optional[str] = None,
    ) -> DLQEntry:
        """Add a failed task to the DLQ."""
        entry = DLQEntry(
            task_id=task_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            payload=payload,
            error=error,
        )
        # TODO Phase 2: persist to store
        raise NotImplementedError("DLQ store not yet implemented. See SPECS.md §25.")

    def list(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 100,
        status: str = "pending",
    ) -> List[DLQEntry]:
        """List DLQ entries, optionally filtered by tenant."""
        # TODO Phase 2: query store
        raise NotImplementedError("DLQ store not yet implemented.")

    def replay(self, task_id: str) -> None:
        """Re-submit a failed task to the workflow engine."""
        # TODO Phase 2: fetch entry, re-enqueue to Temporal/Celery
        raise NotImplementedError("DLQ replay not yet implemented.")

    def discard(self, task_id: str) -> None:
        """Mark a DLQ entry as resolved and remove it from the active queue."""
        # TODO Phase 2: update status in store
        raise NotImplementedError("DLQ discard not yet implemented.")
