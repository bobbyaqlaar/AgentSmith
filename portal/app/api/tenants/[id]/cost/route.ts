import { NextResponse } from "next/server";
import { headers } from "next/headers";
import { getTenantCost } from "@/lib/cost";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canAccessTenant, getAccessFromHeaderValues } from "@/lib/authz";

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  if (!canAccessTenant(access, params.id)) {
    return NextResponse.json({ error: `forbidden: no access to tenant ${params.id}` }, { status: 403 });
  }

  try {
    const cost = await getTenantCost(params.id);
    return NextResponse.json(cost);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
