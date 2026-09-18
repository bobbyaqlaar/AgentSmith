// POST   /api/admin/apps/:id/ingest-token — issue a new ingest token, revoking
//        any the app has (a rotation). The token is in this response and nowhere
//        else, ever: only its hash is stored.
// DELETE /api/admin/apps/:id/ingest-token — revoke every token; the app's CI is
//        refused until a new one is issued.
// Both need admin.apps on this app, and both are audited with the actor.

import { NextResponse } from "next/server";

import { AppMissingError, revokeAppIngestTokens, rotateIngestToken } from "@/lib/apps";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function POST(_request: Request, { params }: { params: { id: string } }) {
  const access = currentAccess();
  if (!can(access, "admin.apps")) {
    return NextResponse.json({ error: "Administrator role required to issue ingest tokens" }, { status: 403 });
  }
  if (!can(access, "admin.apps", params.id)) {
    return NextResponse.json({ error: `Unknown app ${params.id}` }, { status: 404 });
  }
  try {
    const token = await rotateIngestToken(params.id, access.actor ?? "unknown");
    return NextResponse.json(
      { token, note: "Store this now — it is not shown again. Any earlier token for this app has stopped working." },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (err) {
    if (err instanceof AppMissingError) return NextResponse.json({ error: err.message }, { status: 404 });
    throw err;
  }
}

export async function DELETE(_request: Request, { params }: { params: { id: string } }) {
  const access = currentAccess();
  if (!can(access, "admin.apps")) {
    return NextResponse.json({ error: "Administrator role required to revoke ingest tokens" }, { status: 403 });
  }
  if (!can(access, "admin.apps", params.id)) {
    return NextResponse.json({ error: `Unknown app ${params.id}` }, { status: 404 });
  }
  const revoked = await revokeAppIngestTokens(params.id, access.actor ?? "unknown");
  return NextResponse.json({ revoked });
}
