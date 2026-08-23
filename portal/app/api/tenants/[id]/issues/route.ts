import { NextResponse } from "next/server";
import { getUnresolvedIssues } from "@/lib/issues";
import { canAccessTenant } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const access = currentAccess();
  if (!canAccessTenant(access, params.id)) {
    return NextResponse.json({ error: `forbidden: no access to tenant ${params.id}` }, { status: 403 });
  }

  try {
    const issues = await getUnresolvedIssues(params.id);
    return NextResponse.json({ issues });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
