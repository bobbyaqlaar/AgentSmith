// POST /api/ops/stop — stop or resume a run or a whole app.

import { NextResponse } from "next/server";

import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { HitlError, stopControl } from "@/lib/hitl";

export async function POST(request: Request) {
  const access = await currentAccess();
  const body = (await request.json().catch(() => null)) as { tenantId?: unknown; action?: unknown; scope?: unknown; reason?: unknown } | null;
  const tenantId = typeof body?.tenantId === "string" ? body.tenantId : "";
  const reason = typeof body?.reason === "string" ? body.reason.trim() : "";
  if (!can(access, "ops.stop", tenantId) || !access.actor) return NextResponse.json({ error: "an operator stops apps" }, { status: 403 });
  if ((body?.action !== "stop" && body?.action !== "resume") || !reason || reason.length > 2000) {
    return NextResponse.json({ error: "stop or resume, and a reason, are required" }, { status: 400 });
  }
  const scope = typeof body.scope === "string" && body.scope ? body.scope : "*";
  try {
    await stopControl({ tenantId, action: body.action, scope, reason, actor: access.actor });
  } catch (err) {
    if (err instanceof HitlError) return NextResponse.json({ error: err.message }, { status: err.status });
    throw err;
  }
  return NextResponse.json({ ok: true });
}
