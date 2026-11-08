// POST /api/hitl/decide — a signed-in reviewer decides one gate. Who decided comes
// from the session, never from the request.

import { NextResponse } from "next/server";

import { can, roleFor } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { decideGate, HitlError } from "@/lib/hitl";

export async function POST(request: Request) {
  const access = await currentAccess();
  const body = (await request.json().catch(() => null)) as { tenantId?: unknown; recordId?: unknown; approved?: unknown; rationale?: unknown } | null;
  const tenantId = typeof body?.tenantId === "string" ? body.tenantId : "";
  const rationale = typeof body?.rationale === "string" ? body.rationale.trim() : "";
  if (!can(access, "ops.hitl", tenantId) || !access.actor) return NextResponse.json({ error: "a HITL reviewer decides gates" }, { status: 403 });
  if (!Number.isSafeInteger(body?.recordId) || typeof body?.approved !== "boolean" || !rationale || rationale.length > 4000) {
    return NextResponse.json({ error: "a gate, a decision and a reason are all required" }, { status: 400 });
  }
  try {
    await decideGate({ tenantId, recordId: body.recordId as number, approved: body.approved, actor: access.actor,
                       role: roleFor(access, "ops.hitl", tenantId) ?? "hitl_reviewer", rationale });
  } catch (err) {
    if (err instanceof HitlError) return NextResponse.json({ error: err.message }, { status: err.status });
    throw err;
  }
  return NextResponse.json({ ok: true });
}
