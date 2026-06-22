import Link from "next/link";
import { headers } from "next/headers";
import { listTenants } from "@/lib/tenants";
import { getAllTenantsCurrentSpend } from "@/lib/cost";
import { getUnresolvedCountByTenant } from "@/lib/issues";
import { getDLQStatus } from "@/lib/dlq";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, filterTenantIds, getAccessFromHeaderValues } from "@/lib/authz";

export const dynamic = "force-dynamic";

export default async function TenantOverviewPage() {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));

  const [allTenants, spend, issues, dlq] = await Promise.all([
    listTenants(),
    getAllTenantsCurrentSpend(),
    getUnresolvedCountByTenant(),
    getDLQStatus(),
  ]);
  const visibleIds = new Set(filterTenantIds(access, allTenants.map((t) => t.tenantId)));
  const tenants = allTenants.filter((t) => visibleIds.has(t.tenantId));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium">Tenants</h2>
        {!dlq.wired && (
          <span className="text-sm text-amber-400">
            DLQ not wired — runtime/dead_letter.py has no persistent store yet
          </span>
        )}
      </div>

      {tenants.length === 0 ? (
        <p className="text-white/60">
          No tenants registered yet. They&apos;ll appear automatically the first time a
          tenant&apos;s CD pipeline calls{" "}
          <code className="text-white/80">POST /api/sync/history</code>.
        </p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="text-white/60">
            <tr>
              <th className="py-2">Tenant</th>
              <th className="py-2">Isolation</th>
              <th className="py-2">Spend (this month)</th>
              <th className="py-2">Unresolved issues</th>
              <th className="py-2">DLQ pending</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.tenantId} className="border-t border-white/10">
                <td className="py-2">
                  <Link className="text-blue-400 hover:underline" href={`/tenants/${t.tenantId}`}>
                    {t.name}
                  </Link>
                  <span className="ml-2 text-white/40">({t.tenantId})</span>
                </td>
                <td className="py-2">{t.isolation}</td>
                <td className="py-2">${(spend[t.tenantId] ?? 0).toFixed(2)}</td>
                <td className="py-2">
                  {issues[t.tenantId] ? (
                    <span className="text-red-400">{issues[t.tenantId]}</span>
                  ) : (
                    <span className="text-white/40">0</span>
                  )}
                </td>
                <td className="py-2">
                  {dlq.wired ? dlq.pendingByTenant[t.tenantId] ?? 0 : <span className="text-white/40">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
