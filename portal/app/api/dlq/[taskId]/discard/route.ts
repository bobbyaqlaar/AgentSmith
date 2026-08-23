// POST /api/dlq/:taskId/discard — mark a DLQ entry resolved without
// replaying it. Safe to do directly from the portal (unlike replay) since
// it never needs to resume a live workflow.

import { NextResponse } from "next/server";
import { getDlqEntry, discardDlqEntry } from "@/lib/dlq";
import { canAccessTenant, canWrite } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function POST(_request: Request, { params }: { params: { taskId: string } }) {
  const access = currentAccess();
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
