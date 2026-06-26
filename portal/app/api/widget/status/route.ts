// GET /api/widget/status?token=... — public, read-only, token-scoped status
// endpoint for the In-App Widget (templates/in-app-widget/, SPECS.md §15, §26).
//
// SECURITY: tenant scoping comes ENTIRELY from the token. There is no
// tenant-id query/body parameter here on purpose — a forged tenant-id could
// otherwise be used to read another tenant's data. The embed snippet's
// `tenant-id` attribute (see widget.js) is a display label only.
//
// CORS is open (no cookies are used; the token itself is the credential) —
// tenant apps load this from their own origin, not the portal's.

import { NextResponse } from "next/server";
import { resolveWidgetToken } from "@/lib/widgetTokens";
import { getWidgetStatus } from "@/lib/runStatus";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS_HEADERS });
}

export async function GET(request: Request) {
  const token = new URL(request.url).searchParams.get("token") ?? "";

  const tenantId = await resolveWidgetToken(token);
  if (!tenantId) {
    return NextResponse.json({ error: "invalid or revoked token" }, { status: 401, headers: CORS_HEADERS });
  }

  const status = await getWidgetStatus(tenantId);
  return NextResponse.json(status, { headers: CORS_HEADERS });
}
