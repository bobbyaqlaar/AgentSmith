// POST /api/incidents — open or close an incident (DESC ISR domain 4).

import { NextResponse } from "next/server";

import { appendAuditEvent } from "@/lib/auditLog";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { withTransaction } from "@/lib/db";

const SEVERITIES = ["low", "medium", "high", "critical"];

export async function POST(request: Request) {
  const access = await currentAccess();
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  const tenantId = typeof body?.tenantId === "string" ? body.tenantId : "";
  if (!can(access, "ops.incident", tenantId) || !access.actor) return NextResponse.json({ error: "an operator or compliance officer manages incidents" }, { status: 403 });
  const actor = access.actor;
  if (Number.isSafeInteger(body?.closeId)) {
    await withTransaction("incident_close", async (client) => {
      await client.query(`UPDATE incidents SET status = 'closed', closed_by = $1, closed_at = now() WHERE incident_id = $2 AND tenant_id = $3 AND status = 'open'`, [actor, body?.closeId, tenantId]);
      await appendAuditEvent({ eventType: "incident", actorId: actor, tenantId, details: { action: "close", incident: body?.closeId } }, client);
    });
    return NextResponse.json({ ok: true });
  }
  const title = typeof body?.title === "string" ? body.title.trim() : "";
  const details = typeof body?.details === "string" ? body.details.trim() : "";
  if (!title || title.length > 300 || details.length > 8000 || !SEVERITIES.includes(String(body?.severity))) {
    return NextResponse.json({ error: "a title and a severity are required" }, { status: 400 });
  }
  await withTransaction("incident_open", async (client) => {
    const { rows } = await client.query(`INSERT INTO incidents (tenant_id, title, severity, details, opened_by) VALUES ($1,$2,$3,$4,$5) RETURNING incident_id`, [tenantId, title, body?.severity, details, actor]);
    await appendAuditEvent({ eventType: "incident", actorId: actor, tenantId, details: { action: "open", incident: rows[0].incident_id, severity: body?.severity } }, client);
  });
  return NextResponse.json({ ok: true });
}
