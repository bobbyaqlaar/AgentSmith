// POST /api/ops/ingest — an app's running workers report by the Ops contract
// (contract/ops/v1): a run's status, a dead letter for the HITL queue, the
// settings they declare. Machine to machine: authenticated by the app's own Ops
// token, not the dashboard's login, so it is excluded from middleware.ts. The
// work is lib/opsIngest.ts; this adapts it.

import { NextResponse } from "next/server";

import { handleOpsIngest } from "@/lib/opsIngest";

export async function POST(request: Request) {
  try {
    const result = await handleOpsIngest(request.headers.get("authorization"), await request.text());
    return NextResponse.json(result.body, { status: result.status });
  } catch (err) {
    // A 5xx tells the sender the portal is unwell, not that the message was
    // wrong: a worker warns and carries on, and its next report is sent again.
    return NextResponse.json({ error: `the portal could not store the message: ${String(err)}` }, { status: 500 });
  }
}
