// POST /api/compliance/:app/attest — a signed-in compliance officer signs one
// obligation. The actor is the session's, never the request's.

import { NextResponse } from "next/server";

import { can } from "@/lib/authz";
import { NotAttestable, signObligation } from "@/lib/compliance";
import { LIMITS } from "@/lib/complianceState";
import { currentAccess } from "@/lib/currentAccess";
import { getTenant } from "@/lib/tenants";

export async function POST(request: Request, props: { params: Promise<{ app: string }> }) {
  const params = await props.params;
  const access = await currentAccess();
  if (!can(access, "compliance.attest", params.app) || !access.actor) {
    return NextResponse.json({ error: "a compliance officer signs obligations" }, { status: 403 });
  }
  if (!(await getTenant(params.app))) return NextResponse.json({ error: "no such app" }, { status: 404 });
  const body = (await request.json().catch(() => null)) as { obligation?: unknown; evidence?: unknown; note?: unknown } | null;
  const evidence = typeof body?.evidence === "string" ? body.evidence.trim() : "";
  const note = typeof body?.note === "string" ? body.note.trim() : "";
  if (typeof body?.obligation !== "string" || !evidence || evidence.length > LIMITS.evidence || note.length > LIMITS.note) {
    return NextResponse.json({ error: "an obligation and where the evidence is are both required" }, { status: 400 });
  }
  try {
    const record = await signObligation({ tenantId: params.app, obligation: body.obligation, actor: access.actor, evidence, note });
    return NextResponse.json(record);
  } catch (err) {
    if (err instanceof NotAttestable) return NextResponse.json({ error: err.message }, { status: 400 });
    throw err;
  }
}
