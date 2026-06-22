import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { getTenant } from "@/lib/tenants";
import { getTenantCost } from "@/lib/cost";
import { getUnresolvedIssues } from "@/lib/issues";
import { tenantTraceUrl, checkPhoenixHealth } from "@/lib/phoenix";
import { CostChart } from "@/components/CostChart";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canAccessTenant, getAccessFromHeaderValues } from "@/lib/authz";

export const dynamic = "force-dynamic";

export default async function TenantDetailPage({ params }: { params: { id: string } }) {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  // Treat out-of-scope tenants identically to nonexistent ones — a 403 page
  // would itself leak "this tenant id exists" to a viewer who shouldn't see it.
  if (!canAccessTenant(access, params.id)) notFound();

  const tenant = await getTenant(params.id);
  if (!tenant) notFound();

  const [cost, issues, phoenixUp] = await Promise.all([
    getTenantCost(tenant.tenantId),
    getUnresolvedIssues(tenant.tenantId),
    tenant.phoenixBaseUrl ? checkPhoenixHealth(tenant.phoenixBaseUrl) : Promise.resolve(null),
  ]);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-medium">
          {tenant.name} <span className="text-white/40">({tenant.tenantId})</span>
        </h2>
        <p className="text-white/60 text-sm">Isolation: {tenant.isolation}</p>
        {tenant.phoenixBaseUrl ? (
          <p className="text-sm">
            Phoenix:{" "}
            <a className="text-blue-400 hover:underline" href={tenantTraceUrl(tenant.phoenixBaseUrl, { environment: "production" })}>
              {tenant.phoenixBaseUrl}
            </a>{" "}
            {phoenixUp === false && <span className="text-red-400">(unreachable)</span>}
          </p>
        ) : (
          <p className="text-sm text-white/40">No Phoenix endpoint registered for this tenant.</p>
        )}
      </div>

      <section>
        <h3 className="text-lg font-medium mb-2">Cost — last {cost.history.length} month(s)</h3>
        <CostChart history={cost.history} />
      </section>

      <section>
        <h3 className="text-lg font-medium mb-2">Unresolved MAJOR / CRITICAL issues</h3>
        {issues.length === 0 ? (
          <p className="text-white/60">None — clean.</p>
        ) : (
          <ul className="space-y-2">
            {issues.map((i) => (
              <li key={i.entryId} className="border border-white/10 rounded p-3 text-sm">
                <span
                  className={`mr-2 font-mono text-xs px-1.5 py-0.5 rounded ${
                    i.level === "CRITICAL" ? "bg-red-900 text-red-200" : "bg-amber-900 text-amber-200"
                  }`}
                >
                  {i.level}
                </span>
                {i.event} <span className="text-white/40">— {new Date(i.timestamp).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
