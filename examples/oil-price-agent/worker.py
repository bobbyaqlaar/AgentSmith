"""
examples/oil-price-agent/worker.py — Temporal worker entrypoint for this tenant.

Tenant repos register their OWN workflows/activities here — this is what
that registration looks like, copied out of runtime/worker.py's generic
NotImplementedError stub and made concrete for one domain (§25).

Usage:
    export TENANT_ID=oil-price-demo
    export TEMPORAL_ADDRESS=localhost:7233
    python3 worker.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "workflows"))

# Locate the AgentSmith runtime — prefer AGENTSMITH_DIR env var (set in ~/.zshrc)
# so this worker can run from any directory, not just from inside the framework tree.
_agentsmith_dir = os.environ.get("AGENTSMITH_DIR")
if _agentsmith_dir:
    _runtime_root = Path(_agentsmith_dir) / "runtime"
else:
    # Fallback: assume worker.py is still inside examples/oil-price-agent/ (3 levels deep)
    _runtime_root = Path(__file__).resolve().parent.parent.parent / "runtime"

# oil_price_workflow.py subclasses BaseAgentWorkflow (runtime/workflows/) —
# added here, not inside oil_price_workflow.py itself, because that file
# defines the workflow class and gets re-imported by Temporal's sandbox
# for determinism validation; a sys.path.insert(..., Path(...).resolve()...)
# at THAT module's top level trips the sandbox's restriction on
# pathlib.Path.resolve() (confirmed by running it — not a guess).
sys.path.insert(0, str(_runtime_root))
sys.path.insert(0, str(_runtime_root / "workflows"))

from oil_price_workflow import OilPricePredictionWorkflow  # type: ignore
from activities import (  # type: ignore
    fetch_oil_price_activity,
    run_prediction_activity,
    decide_action_activity,
    dead_letter_activity,
)


async def main() -> None:
    tenant_id = os.environ.get("TENANT_ID", "")
    if not tenant_id:
        print("ERROR: TENANT_ID environment variable is required.", file=sys.stderr)
        sys.exit(1)

    try:
        from temporalio.client import Client
        from temporalio.worker import Worker
    except ImportError:
        print("ERROR: temporalio is not installed. Run: pip install temporalio", file=sys.stderr)
        sys.exit(1)

    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(address)

    worker = Worker(
        client,
        task_queue=f"agent-tasks-{tenant_id}",
        workflows=[OilPricePredictionWorkflow],
        activities=[
            fetch_oil_price_activity,
            run_prediction_activity,
            decide_action_activity,
            dead_letter_activity,
        ],
    )
    print(f"[worker] Listening on task queue agent-tasks-{tenant_id} @ {address}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
