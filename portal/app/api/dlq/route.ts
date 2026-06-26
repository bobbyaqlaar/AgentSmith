import { NextResponse } from "next/server";
import { headers } from "next/headers";
import { getDLQStatus } from "@/lib/dlq";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, filterTenantIds, getAccessFromHeaderValues } from "@/lib/authz";

export async function GET() {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));

  try {
    const status = await getDLQStatus();
    const visibleIds = new Set(filterTenantIds(access, Object.keys(status.pendingByTenant)));
    const pendingByTenant = Object.fromEntries(
      Object.entries(status.pendingByTenant).filter(([tenantId]) => visibleIds.has(tenantId))
    );
    return NextResponse.json({ ...status, pendingByTenant });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
