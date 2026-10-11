// POST /api/admin/apps/:id/replay-key — issue the key the portal signs this
// app's replay requests with (contract/ops/v1), replacing any it had. The key is
// in this response once, for the app's worker to hold as REPLAY_WEBHOOK_SECRET;
// the audit records that it was issued, never it. Needs admin.apps on this app.

import { NextResponse } from "next/server";

import { AppMissingError, issueReplayKey } from "@/lib/apps";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function POST(_request: Request, { params }: { params: { id: string } }) {
  const access = currentAccess();
  if (!can(access, "admin.apps")) {
    return NextResponse.json({ error: "Administrator role required to issue replay keys" }, { status: 403 });
  }
  if (!can(access, "admin.apps", params.id)) {
    return NextResponse.json({ error: `Unknown app ${params.id}` }, { status: 404 });
  }
  try {
    const key = await issueReplayKey(params.id, access.actor ?? "unknown");
    return NextResponse.json(
      {
        token: key,
        note: "Set this as REPLAY_WEBHOOK_SECRET on the app's worker now — it is not shown again. Replays signed " +
          "with any earlier key are refused from this moment.",
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (err) {
    if (err instanceof AppMissingError) return NextResponse.json({ error: err.message }, { status: 404 });
    throw err;
  }
}
