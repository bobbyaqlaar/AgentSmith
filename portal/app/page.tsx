import Link from "next/link";
import { headers } from "next/headers";
import { listTenants } from "@/lib/tenants";
import { getAllTenantsCurrentSpend } from "@/lib/cost";
import { getUnresolvedCountByTenant } from "@/lib/issues";
import { getDLQStatus } from "@/lib/dlq";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, filterTenantIds, getAccessFromHeaderValues } from "@/lib/authz";
import { MetricCard } from "@/components/ui/Card";
import { Badge, toneForRunStatus } from "@/components/ui/Badge";

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

  const totalSpend = tenants.reduce((sum, t) => sum + (spend[t.tenantId] ?? 0), 0);
  const totalIssues = tenants.reduce((sum, t) => sum + (issues[t.tenantId] ?? 0), 0);
  const totalDlq = dlq.wired ? tenants.reduce((sum, t) => sum + (dlq.pendingByTenant[t.tenantId] ?? 0), 0) : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium">Tenants</h2>
        {!dlq.wired && (
          <span className="text-sm text-amber-700 dark:text-amber-400">
            DLQ not wired — no worker has constructed a DeadLetterQueue against this database yet
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Spend this month" value={`$${totalSpend.toFixed(2)}`} />
        <MetricCard
          label="Unresolved issues"
          value={totalIssues}
          tone={totalIssues > 0 ? "danger" : "success"}
        />
        <MetricCard label="DLQ pending" value={totalDlq ?? "—"} tone={totalDlq ? "warning" : "default"} />
        <MetricCard label="Tenants" value={tenants.length} />
      </div>

      {tenants.length === 0 ? (
        <p className="text-black/60 dark:text-white/60">
          No tenants registered yet. They&apos;ll appear automatically the first time a
          tenant&apos;s CD pipeline calls{" "}
          <code className="text-black/80 dark:text-white/80">POST /api/sync/history</code>.
        </p>
      ) : (
        <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
              <tr>
                <th className="py-2.5 px-4 font-medium">Tenant</th>
                <th className="py-2.5 px-4 font-medium">Isolation</th>
                <th className="py-2.5 px-4 font-medium">Spend (this month)</th>
                <th className="py-2.5 px-4 font-medium">Unresolved issues</th>
                <th className="py-2.5 px-4 font-medium">DLQ pending</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.tenantId} className="border-t border-black/10 dark:border-white/10">
                  <td className="py-2.5 px-4">
                    <Link className="text-blue-700 dark:text-blue-400 hover:underline" href={`/tenants/${t.tenantId}`}>
                      {t.name}
                    </Link>
                    <span className="ml-2 text-black/40 dark:text-white/40">({t.tenantId})</span>
                  </td>
                  <td className="py-2.5 px-4 text-black/70 dark:text-white/70">{t.isolation}</td>
                  <td className="py-2.5 px-4">${(spend[t.tenantId] ?? 0).toFixed(2)}</td>
                  <td className="py-2.5 px-4">
                    {issues[t.tenantId] ? (
                      <Badge tone="danger">{issues[t.tenantId]}</Badge>
                    ) : (
                      <Badge tone={toneForRunStatus("success")}>0</Badge>
                    )}
                  </td>
                  <td className="py-2.5 px-4 text-black/70 dark:text-white/70">
                    {dlq.wired ? dlq.pendingByTenant[t.tenantId] ?? 0 : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
