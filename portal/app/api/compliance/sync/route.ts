// POST /api/compliance/sync — an app's CD sends the signatures in its repository
// and gets back the ones given in the portal (contract/compliance/v1). Machine to
// machine: the app's own Ops token decides the app, so it is excluded from
// proxy.ts.

import { NextResponse } from "next/server";

import { KNOWN_OBLIGATIONS, listAttestations, storeRepoAttestations } from "@/lib/compliance";
import { parseAttestations } from "@/lib/complianceState";
import { bearerToken, resolveIngestToken } from "@/lib/ingestTokens";

const MAX_BODY = 2_000_000;

export async function POST(request: Request) {
  const token = bearerToken(request.headers.get("authorization"));
  const tenantId = token ? await resolveIngestToken(token, "ops") : null;
  if (!tenantId) return NextResponse.json({ error: "unknown or revoked Ops token" }, { status: 401 });
  const text = await request.text();
  if (Buffer.byteLength(text, "utf8") > MAX_BODY) return NextResponse.json({ error: "the body is too large" }, { status: 413 });
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return NextResponse.json({ error: "the body is not JSON" }, { status: 400 });
  }
  const parsed = parseAttestations(raw, KNOWN_OBLIGATIONS);
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });
  await storeRepoAttestations(tenantId, parsed.value);
  return NextResponse.json({ attestations: await listAttestations(tenantId, "portal") });
}
