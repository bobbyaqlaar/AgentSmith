// POST /api/dev/ingest — an app's CI sends what the process gate decided about
// each commit (`process_gate.py ci --json`; portal phase 1). Machine to
// machine: authenticated by the app's own ingest token, not the dashboard's
// login, so it is excluded from middleware.ts like /api/sync and
// /api/runs/ingest. The work is lib/devIngestHandler.ts; this adapts it.

import { NextResponse } from "next/server";

import { handleDevIngest } from "@/lib/devIngestHandler";

export async function POST(request: Request) {
  try {
    const result = await handleDevIngest(request.headers.get("authorization"), await request.text());
    return NextResponse.json(result.body, { status: result.status });
  } catch (err) {
    // A 5xx tells the CI step the portal is unwell, not that the record was
    // wrong — the step warns rather than failing the build (S7).
    return NextResponse.json({ error: `the portal could not store the record: ${String(err)}` }, { status: 500 });
  }
}
