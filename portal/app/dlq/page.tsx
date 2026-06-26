import Link from "next/link";
import { headers } from "next/headers";
import { getDLQStatus } from "@/lib/dlq";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, filterTenantIds, getAccessFromHeaderValues } from "@/lib/authz";
import { MetricCard } from "@/components/ui/Card";

export const dynamic = "force-dynamic";

export default async function DLQPage() {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));

  const dlq = await getDLQStatus();
  const visibleTenantIds = filterTenantIds(access, Object.keys(dlq.pendingByTenant));
  const totalPending = visibleTenantIds.reduce((sum, id) => sum + (dlq.pendingByTenant[id] ?? 0), 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-medium">Dead-letter queue</h2>
        <p className="text-sm text-black/60 dark:text-white/60 mt-1">
          Failed activities — including recoverable ones a human can fix and replay in place
          (e.g. a tool call that hallucinated a field name) — see{" "}
          <code className="text-black/80 dark:text-white/80">runtime/dead_letter.py</code> and{" "}
          <code className="text-black/80 dark:text-white/80">run_with_recoverable_step</code>.
          Click a tenant to view, edit, and replay or discard individual entries.
        </p>
      </div>

      {!dlq.wired ? (
        <p className="text-amber-700 dark:text-amber-400">
          Not wired — no worker has constructed a <code>DeadLetterQueue</code> against this database yet.
          The table is created on first use, not by this portal's migration (see db/schema.sql).
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <MetricCard label="Pending entries" value={totalPending} tone={totalPending > 0 ? "warning" : "success"} />
            <MetricCard label="Tenants with entries" value={visibleTenantIds.filter((id) => dlq.pendingByTenant[id] > 0).length} />
          </div>

          {visibleTenantIds.length === 0 ? (
            <p className="text-black/60 dark:text-white/60">No DLQ entries for any tenant you have access to.</p>
          ) : (
            <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
                  <tr>
                    <th className="py-2.5 px-4 font-medium">Tenant</th>
                    <th className="py-2.5 px-4 font-medium">Pending</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleTenantIds.map((id) => (
                    <tr key={id} className="border-t border-black/10 dark:border-white/10">
                      <td className="py-2.5 px-4">
                        <Link className="text-blue-700 dark:text-blue-400 hover:underline" href={`/dlq/${id}`}>
                          {id}
                        </Link>
                      </td>
                      <td className="py-2.5 px-4">{dlq.pendingByTenant[id] ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
