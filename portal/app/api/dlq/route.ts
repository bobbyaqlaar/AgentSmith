import { NextResponse } from "next/server";
import { getDLQStatus } from "@/lib/dlq";
import { filterTenantIds } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function GET() {
  const access = currentAccess();

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
