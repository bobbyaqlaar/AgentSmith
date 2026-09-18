// PATCH /api/admin/apps/:id — edit an app's name and repository
// (Administration › Apps; portal phase 1). Needs admin.apps on this app.

import { NextResponse } from "next/server";

import { AppMissingError, parseAppInput, updateApp } from "@/lib/apps";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const access = currentAccess();
  if (!can(access, "admin.apps")) {
    return NextResponse.json({ error: "Administrator role required to edit apps" }, { status: 403 });
  }
  if (!can(access, "admin.apps", params.id)) {
    return NextResponse.json({ error: `Unknown app ${params.id}` }, { status: 404 });
  }
  const parsed = parseAppInput(await request.json().catch(() => null), "update");
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });
  try {
    await updateApp(params.id, parsed.value, access.actor ?? "unknown");
  } catch (err) {
    if (err instanceof AppMissingError) return NextResponse.json({ error: err.message }, { status: 404 });
    throw err;
  }
  return NextResponse.json({ app: params.id });
}
