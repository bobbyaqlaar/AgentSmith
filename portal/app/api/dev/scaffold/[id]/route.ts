// GET /api/dev/scaffold/:id — the intake record, for `agentsmith tenant init
// --from <id>` (contract/intake/v1/). Machine to machine: authenticated inside
// the handler by the intake's own token, so it is excluded from proxy.ts
// like /api/dev/ingest. The work is lib/intakes.ts; this adapts it.

import { NextResponse } from "next/server";

import { handleScaffoldRead } from "@/lib/intakes";

export async function GET(request: Request, props: { params: Promise<{ id: string }> }) {
  const params = await props.params;
  const result = await handleScaffoldRead(request.headers.get("authorization"), params.id);
  return NextResponse.json(result.body, { status: result.status, headers: { "Cache-Control": "no-store" } });
}
