// GET /api/admin/access-export — who holds which role, for the periodic access
// review (DESC ISR 5.2.1.12). Never includes a password. The export is itself
// on the record.

import { NextResponse } from "next/server";

import { appendAuditEvent } from "@/lib/auditLog";
import { can, configuredGrants } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function GET() {
  const access = await currentAccess();
  if (!can(access, "admin.org")) return NextResponse.json({ error: "Super user role required: this lists every grant in the organisation" }, { status: 403 });
  const grants = configuredGrants();
  await appendAuditEvent({ eventType: "access_export", actorId: access.actor ?? "unknown", tenantId: null, details: { entries: grants.length } });
  return NextResponse.json({ exportedAt: new Date().toISOString(), grants });
}
