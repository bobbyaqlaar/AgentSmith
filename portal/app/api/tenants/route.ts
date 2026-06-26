import { NextResponse } from "next/server";
import { headers } from "next/headers";
import { listTenants, upsertTenant } from "@/lib/tenants";
import { getAllTenantsCurrentSpend } from "@/lib/cost";
import { getUnresolvedCountByTenant } from "@/lib/issues";
import { getDLQStatus } from "@/lib/dlq";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canWrite, filterTenantIds, getAccessFromHeaderValues } from "@/lib/authz";
import { ISOLATION_VALUES, isValidIsolation } from "@/lib/isolation";

export async function GET() {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));

  try {
    const [tenants, spend, issues, dlq] = await Promise.all([
      listTenants(),
      getAllTenantsCurrentSpend(),
      getUnresolvedCountByTenant(),
      getDLQStatus(),
    ]);

    const visibleIds = new Set(filterTenantIds(access, tenants.map((t) => t.tenantId)));

    const data = tenants
      .filter((t) => visibleIds.has(t.tenantId))
      .map((t) => ({
        ...t,
        currentSpendUsd: spend[t.tenantId] ?? 0,
        unresolvedIssues: issues[t.tenantId] ?? 0,
        dlqPending: dlq.wired ? dlq.pendingByTenant[t.tenantId] ?? 0 : null,
      }));

    return NextResponse.json({ tenants: data, dlqWired: dlq.wired });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function POST(request: Request) {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  if (!canWrite(access)) {
    return NextResponse.json({ error: "operator or admin role required" }, { status: 403 });
  }

  const body = await request.json();
  if (!body?.tenantId || !body?.name) {
    return NextResponse.json({ error: "tenantId and name are required" }, { status: 400 });
  }
  if (body.isolation !== undefined && !isValidIsolation(body.isolation)) {
    return NextResponse.json({ error: `isolation must be one of: ${ISOLATION_VALUES.join(", ")}` }, { status: 400 });
  }
  await upsertTenant(body);
  return NextResponse.json({ ok: true });
}
