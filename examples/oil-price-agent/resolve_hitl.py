"""
examples/oil-price-agent/resolve_hitl.py — Send the hitl_approved signal to a
waiting workflow. Run from a second terminal while trigger_workflow.py is
still waiting.

Usage:
    python3 resolve_hitl.py [--approve | --reject]

Default: --approve
"""

from __future__ import annotations

import asyncio
import os
import sys

try:
    from runtime.temporal_client import connect as connect_temporal, tls_enabled
except ImportError:
    print(
        "ERROR: temporalio not installed. Run: pip install temporalio", file=sys.stderr
    )
    sys.exit(1)

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
WORKFLOW_ID = "oil-price-demo-run-1"


async def main() -> None:
    approve = "--reject" not in sys.argv
    print(f"Connecting to Temporal at {TEMPORAL_ADDRESS} (tls={tls_enabled()}) …")
    client = await connect_temporal()   # address + TEMPORAL_TLS + timeout, one place

    handle = client.get_workflow_handle(WORKFLOW_ID)
    # The UNADDRESSED signal, which any gate currently waiting will consume.
    # Correct for this demo, which has exactly one gate. A workflow with two
    # would use `hitl_approved_for(gate_id, approved)` instead — an approval
    # that does not name its gate cannot say which of two it means.
    await handle.signal("hitl_approved", approve)

    decision = "APPROVED" if approve else "REJECTED"
    print(f"Signal sent: hitl_approved={approve} ({decision})")
    print("trigger_workflow.py should now complete.")


if __name__ == "__main__":
    asyncio.run(main())
