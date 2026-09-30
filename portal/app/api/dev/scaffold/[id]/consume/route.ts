// POST /api/dev/scaffold/:id/consume — marks the intake used, once, after the
// CLI has written the scaffold. Token-authenticated inside the handler, like
// the GET beside it; the work is lib/intakes.ts.

import { NextResponse } from "next/server";

import { handleScaffoldConsume } from "@/lib/intakes";

export async function POST(request: Request, { params }: { params: { id: string } }) {
  const result = await handleScaffoldConsume(request.headers.get("authorization"), params.id);
  return NextResponse.json(result.body, { status: result.status, headers: { "Cache-Control": "no-store" } });
}
