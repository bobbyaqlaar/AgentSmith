// POST /api/admin/apps — register an app (Administration › Apps; portal phase 1).
// Needs admin.apps. Registration never overwrites: an id that exists is a 409.

import { NextResponse } from "next/server";

import { AppExistsError, createApp, parseAppInput } from "@/lib/apps";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function POST(request: Request) {
  const access = currentAccess();
  if (!can(access, "admin.apps")) {
    return NextResponse.json({ error: "Administrator role required to register apps" }, { status: 403 });
  }
  const parsed = parseAppInput(await request.json().catch(() => null), "create");
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });
  const id = parsed.value.id!;
  if (!can(access, "admin.apps", id)) {
    return NextResponse.json({ error: `forbidden: no access to app ${id}` }, { status: 403 });
  }
  try {
    await createApp({ ...parsed.value, id }, access.actor ?? "unknown");
  } catch (err) {
    if (err instanceof AppExistsError) return NextResponse.json({ error: err.message }, { status: 409 });
    throw err;
  }
  return NextResponse.json({ app: id }, { status: 201 });
}
