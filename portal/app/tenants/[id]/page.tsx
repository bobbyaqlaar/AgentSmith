import Link from "next/link";
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { getTenant } from "@/lib/tenants";
import { getTenantCost } from "@/lib/cost";
import { getUnresolvedIssues } from "@/lib/issues";
import { tenantTraceUrl, checkPhoenixHealth, getRecentTraceStats } from "@/lib/phoenix";
import { getSuggestedPromotions } from "@/lib/promotions";
import { CostChart } from "@/components/CostChart";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canAccessTenant, getAccessFromHeaderValues } from "@/lib/authz";
import { Badge, toneForLevel } from "@/components/ui/Badge";
import { MetricCard } from "@/components/ui/Card";

export const dynamic = "force-dynamic";

export default async function TenantDetailPage({ params }: { params: { id: string } }) {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  // Treat out-of-scope tenants identically to nonexistent ones — a 403 page
  // would itself leak "this tenant id exists" to a viewer who shouldn't see it.
  if (!canAccessTenant(access, params.id)) notFound();

  const tenant = await getTenant(params.id);
  if (!tenant) notFound();

  const [cost, issues, phoenixUp, traceStats, suggestedPromotions] = await Promise.all([
    getTenantCost(tenant.tenantId),
    getUnresolvedIssues(tenant.tenantId),
    tenant.phoenixBaseUrl ? checkPhoenixHealth(tenant.phoenixBaseUrl) : Promise.resolve(null),
    tenant.phoenixBaseUrl ? getRecentTraceStats(tenant.phoenixBaseUrl, { sinceHours: 24 }) : Promise.resolve(null),
    tenant.phoenixBaseUrl ? getSuggestedPromotions(tenant.phoenixBaseUrl, { sinceHours: 24 }) : Promise.resolve([]),
  ]);

  return (
    <div className="space-y-8">
      <nav className="text-sm text-black/50 dark:text-white/50">
        <Link href="/" className="hover:text-black dark:hover:text-white">Tenants</Link>
        <span className="mx-1.5">/</span>
        <span className="text-black/80 dark:text-white/80">{tenant.name}</span>
      </nav>

      <div>
        <h2 className="text-xl font-medium">
          {tenant.name} <span className="text-black/40 dark:text-white/40">({tenant.tenantId})</span>
        </h2>
        <p className="text-black/60 dark:text-white/60 text-sm mt-1">Isolation: {tenant.isolation}</p>
        {tenant.phoenixBaseUrl ? (
          <p className="text-sm mt-1">
            Phoenix:{" "}
            <a className="text-blue-700 dark:text-blue-400 hover:underline" href={tenantTraceUrl(tenant.phoenixBaseUrl, { environment: "production" })}>
              {tenant.phoenixBaseUrl}
            </a>{" "}
            {phoenixUp === false && <Badge tone="danger">unreachable</Badge>}
            {phoenixUp === true && <Badge tone="success">reachable</Badge>}
          </p>
        ) : (
          <p className="text-sm text-black/40 dark:text-white/40 mt-1">No Phoenix endpoint registered for this tenant.</p>
        )}
        {traceStats !== null && (
          <p className="text-sm mt-1 text-black/60 dark:text-white/60">
            Last 24h: {traceStats.traceCount} trace(s)
            {traceStats.errorRate !== null && (
              <>
                {" "}— error rate{" "}
                <Badge tone={traceStats.errorRate > 0.05 ? "danger" : "success"}>
                  {(traceStats.errorRate * 100).toFixed(1)}%
                </Badge>
              </>
            )}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard label="Spend this month" value={`$${cost.spentUsd.toFixed(2)}`} />
        <MetricCard
          label="Budget cap"
          value={cost.cap !== null ? `$${cost.cap.toFixed(2)}` : "—"}
        />
        <MetricCard
          label="Unresolved issues"
          value={issues.length}
          tone={issues.length > 0 ? "danger" : "success"}
        />
      </div>

      <section>
        <h3 className="text-lg font-medium mb-3">Cost — last {cost.history.length} month(s)</h3>
        <CostChart history={cost.history} />
      </section>

      <section>
        <h3 className="text-lg font-medium mb-3">Unresolved MAJOR / CRITICAL issues</h3>
        {issues.length === 0 ? (
          <p className="text-black/60 dark:text-white/60">None — clean.</p>
        ) : (
          <ul className="space-y-2">
            {issues.map((i) => (
              <li key={i.entryId} className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm">
                <Badge tone={toneForLevel(i.level)}>{i.level}</Badge>
                <span className="ml-2">{i.event}</span>{" "}
                <span className="text-black/40 dark:text-white/40">— {new Date(i.timestamp).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="text-lg font-medium mb-3">Suggested promotions (shadow eval)</h3>
        {suggestedPromotions.length === 0 ? (
          <p className="text-black/60 dark:text-white/60">
            No shadow-eval failures in the last 24h — nothing suggested.
          </p>
        ) : (
          <ul className="space-y-2">
            {suggestedPromotions.map((p) => (
              <li key={p.spanId} className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm space-y-1">
                <div>
                  <Badge tone="danger">score {p.score.toFixed(2)}</Badge>
                  <span className="ml-2 text-black/40 dark:text-white/40 font-mono text-xs">{p.spanId}</span>
                </div>
                {p.inputValue && <p className="text-black/70 dark:text-white/70">Input: {p.inputValue}</p>}
                {p.outputValue && <p className="text-black/70 dark:text-white/70">Output: {p.outputValue}</p>}
                {p.explanation && <p className="text-black/50 dark:text-white/50 italic">{p.explanation}</p>}
                <p className="text-black/40 dark:text-white/40 text-xs">
                  Review in Phoenix, then run <code>ai-stack-promote</code> to add to the golden dataset — never auto-promoted.
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
