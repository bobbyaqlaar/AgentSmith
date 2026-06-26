// POST /api/dlq/:taskId/discard — mark a DLQ entry resolved without
// replaying it. Safe to do directly from the portal (unlike replay) since
// it never needs to resume a live workflow.

import { NextResponse } from "next/server";
import { headers } from "next/headers";
import { getDlqEntry, discardDlqEntry } from "@/lib/dlq";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canAccessTenant, canWrite, getAccessFromHeaderValues } from "@/lib/authz";

export async function POST(_request: Request, { params }: { params: { taskId: string } }) {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  if (!canWrite(access)) {
    return NextResponse.json({ error: "operator or admin role required to discard DLQ entries" }, { status: 403 });
  }

  const entry = await getDlqEntry(params.taskId);
  if (!entry || !canAccessTenant(access, entry.tenantId)) {
    return NextResponse.json({ error: `Unknown DLQ entry ${params.taskId}` }, { status: 404 });
  }

  const discarded = await discardDlqEntry(params.taskId);
  if (!discarded) {
    return NextResponse.json({ error: `Entry ${params.taskId} is already ${entry.status}` }, { status: 409 });
  }
  return NextResponse.json({ ok: true });
}
