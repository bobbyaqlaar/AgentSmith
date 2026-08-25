import Link from "next/link";
import { listTenants } from "@/lib/tenants";
import { getAllTenantsCurrentSpend } from "@/lib/cost";
import { getUnresolvedCountByTenant } from "@/lib/issues";
import { getDLQStatus } from "@/lib/dlq";
import { getFrameworkVersionByTenant } from "@/lib/runStatus";
import { FIRST_VERSIONED_RELEASE, versionBreakdown } from "@/lib/wireContract";
import { filterTenantIds } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { MetricCard } from "@/components/ui/Card";
import { Badge, toneForRunStatus } from "@/components/ui/Badge";

export const dynamic = "force-dynamic";

export default async function TenantOverviewPage() {
  const access = currentAccess();

  const [allTenants, spend, issues, dlq, frameworkVersions] = await Promise.all([
    listTenants(),
    getAllTenantsCurrentSpend(),
    getUnresolvedCountByTenant(),
    getDLQStatus(),
    getFrameworkVersionByTenant(),
  ]);
  const visibleIds = new Set(filterTenantIds(access, allTenants.map((t) => t.tenantId)));
  const tenants = allTenants.filter((t) => visibleIds.has(t.tenantId));

  const totalSpend = spend.wired
    ? tenants.reduce((sum, t) => sum + (spend.byTenant[t.tenantId] ?? 0), 0)
    : null;
  const totalIssues = tenants.reduce((sum, t) => sum + (issues[t.tenantId] ?? 0), 0);
  const totalDlq = dlq.wired ? tenants.reduce((sum, t) => sum + (dlq.pendingByTenant[t.tenantId] ?? 0), 0) : null;

  // The fleet view. This portal is operated by IT and the tenants by the
  // business, on independent release cadences — so "which AgentSmith is my
  // fleet on" is a question only this page can answer, and until the version
  // was on the wire nothing could. Tenants that have never reported a run are
  // excluded rather than bucketed: nothing has run, which is not a version.
  const reportedVersions = tenants
    .filter((t) => frameworkVersions.has(t.tenantId))
    .map((t) => frameworkVersions.get(t.tenantId) ?? null);
  const versions = versionBreakdown(reportedVersions);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium">Tenants</h2>
        <div className="flex flex-col items-end gap-0.5 text-sm text-amber-700 dark:text-amber-400">
          {!dlq.wired && (
            <span>DLQ not wired — no worker has constructed a DeadLetterQueue against this database yet</span>
          )}
          {/* The same sentence the DLQ has always had, for the column that used
              to render "$0.00" instead: the gateway creates its budget table on
              first use, so an absent one means nothing has run — not that
              nothing was spent. */}
          {!spend.wired && (
            <span>Spend not wired — no gateway has recorded a call against this database yet</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Spend this month" value={totalSpend === null ? "—" : `$${totalSpend.toFixed(2)}`} />
        <MetricCard
          label="Unresolved issues"
          value={totalIssues}
          tone={totalIssues > 0 ? "danger" : "success"}
        />
        <MetricCard label="DLQ pending" value={totalDlq ?? "—"} tone={totalDlq ? "warning" : "default"} />
        <MetricCard label="Tenants" value={tenants.length} />
        <MetricCard
          label="AgentSmith versions in the fleet"
          value={versions.length === 0 ? "—" : versions.length}
          tone={versions.length > 1 ? "warning" : "default"}
        />
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
                <th className="py-2.5 px-4 font-medium">AgentSmith</th>
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
                  {/* Three states, and the em dash is not one of the other two.
                      A tenant with no runs has reported nothing; a tenant whose
                      runs carry no version is on a framework older than the one
                      that began reporting it — a fact about that tenant, not a
                      gap in this table. */}
                  <td className="py-2.5 px-4 text-black/70 dark:text-white/70">
                    {!frameworkVersions.has(t.tenantId) ? (
                      <span className="text-black/40 dark:text-white/40" title="no runs reported yet">—</span>
                    ) : frameworkVersions.get(t.tenantId) === null ? (
                      <span title={`reported no version, so older than ${FIRST_VERSIONED_RELEASE}`}>
                        {`< ${FIRST_VERSIONED_RELEASE}`}
                      </span>
                    ) : (
                      frameworkVersions.get(t.tenantId)
                    )}
                  </td>
                  <td className="py-2.5 px-4">
                    {spend.wired ? `$${(spend.byTenant[t.tenantId] ?? 0).toFixed(2)}` : "—"}
                  </td>
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
