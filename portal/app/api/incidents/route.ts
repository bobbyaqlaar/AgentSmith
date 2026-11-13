// POST /api/incidents — open or close an incident (DESC ISR domain 4).

import { NextResponse } from "next/server";

import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { closeIncident, openIncident, SEVERITIES, type Severity } from "@/lib/incidents";

export async function POST(request: Request) {
  const access = await currentAccess();
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  const tenantId = typeof body?.tenantId === "string" ? body.tenantId : "";
  if (!can(access, "ops.incident", tenantId) || !access.actor) return NextResponse.json({ error: "an operator or compliance officer manages incidents" }, { status: 403 });
  const actor = access.actor;
  if (Number.isSafeInteger(body?.closeId)) {
    const closed = await closeIncident(tenantId, Number(body?.closeId), actor);
    return closed
      ? NextResponse.json({ ok: true })
      : NextResponse.json({ error: "this incident is already closed, or is not this app's" }, { status: 409 });
  }
  const title = typeof body?.title === "string" ? body.title.trim() : "";
  const details = typeof body?.details === "string" ? body.details.trim() : "";
  const severity = String(body?.severity);
  if (!title || title.length > 300 || details.length > 8000 || !(SEVERITIES as readonly string[]).includes(severity)) {
    return NextResponse.json({ error: "a title and a severity are required" }, { status: 400 });
  }
  await openIncident({ tenantId, title, severity: severity as Severity, details, actor });
  return NextResponse.json({ ok: true });
}
