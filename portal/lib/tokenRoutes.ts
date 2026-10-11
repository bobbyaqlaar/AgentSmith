// portal/lib/tokenRoutes.ts — the admin routes that issue, rotate and revoke an
// app's machine token, for either scope: its CI's ingest token
// (/api/admin/apps/:id/ingest-token) and its workers' Ops token
// (/api/admin/apps/:id/ops-token, contract/ops/v1). One implementation, so the
// two cannot drift on who may call them or what a response may carry.
//
// POST   — issue a new token, revoking any of that scope (a rotation). The token
//          is in the response and nowhere else, ever: only its hash is stored.
// DELETE — revoke every token of that scope; the app is refused until a new one
//          is issued.
// Both need admin.apps on this app, and both are audited with the actor.

import { NextResponse } from "next/server";

import { AppMissingError, revokeAppIngestTokens, rotateIngestToken } from "./apps";
import { can } from "./authz";
import { currentAccess } from "./currentAccess";
import type { TokenScope } from "./ingestTokens";

const NOUN: Record<TokenScope, string> = { dev: "ingest tokens", ops: "Ops tokens" };
const HOLDER: Record<TokenScope, string> = { dev: "this app's CI", ops: "this app's workers" };

export function tokenRoutes(scope: TokenScope) {
  async function POST(_request: Request, { params }: { params: { id: string } }) {
    const access = currentAccess();
    if (!can(access, "admin.apps")) {
      return NextResponse.json({ error: `Administrator role required to issue ${NOUN[scope]}` }, { status: 403 });
    }
    if (!can(access, "admin.apps", params.id)) {
      return NextResponse.json({ error: `Unknown app ${params.id}` }, { status: 404 });
    }
    try {
      const token = await rotateIngestToken(params.id, access.actor ?? "unknown", scope);
      return NextResponse.json(
        { token, note: `Store this now — it is not shown again. Any earlier token ${HOLDER[scope]} held has stopped working.` },
        { headers: { "Cache-Control": "no-store" } },
      );
    } catch (err) {
      if (err instanceof AppMissingError) return NextResponse.json({ error: err.message }, { status: 404 });
      throw err;
    }
  }

  async function DELETE(_request: Request, { params }: { params: { id: string } }) {
    const access = currentAccess();
    if (!can(access, "admin.apps")) {
      return NextResponse.json({ error: `Administrator role required to revoke ${NOUN[scope]}` }, { status: 403 });
    }
    if (!can(access, "admin.apps", params.id)) {
      return NextResponse.json({ error: `Unknown app ${params.id}` }, { status: 404 });
    }
    const revoked = await revokeAppIngestTokens(params.id, access.actor ?? "unknown", scope);
    return NextResponse.json({ revoked });
  }

  return { POST, DELETE };
}
