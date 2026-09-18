// /dev — every app the user may see in the Dev workspace, with what its CI
// gate last decided (portal phase 1). Read from the Dev ingest, a cache of git.

import Link from "next/link";

import { Freshness, ShortSha, VerdictBadge } from "@/components/DevBits";
import { Badge } from "@/components/ui/Badge";
import { appsWith, can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { listDevApps } from "@/lib/devRead";
import { commitUrl } from "@/lib/devView";
import { listTenants } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function DevAppsPage() {
  const access = currentAccess();
  const allIds = (await listTenants()).map((t) => t.tenantId);
  const apps = await listDevApps(appsWith(access, "dev.read", allIds));

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-medium">Apps</h2>

      {apps.length === 0 ? (
        <div className="space-y-1">
          <p className="text-black/60 dark:text-white/60">No apps yet.</p>
          {can(access, "admin.apps") && (
            <p className="text-black/60 dark:text-white/60">
              <Link className="text-blue-700 dark:text-blue-400 hover:underline" href="/admin/apps">Register one</Link>, then
              give its CI the ingest token.
            </p>
          )}
        </div>
      ) : (
        <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
              <tr>
                <th className="py-2.5 px-4 font-medium">App</th>
                <th className="py-2.5 px-4 font-medium">Last gated commit</th>
                <th className="py-2.5 px-4 font-medium">Active designs</th>
                <th className="py-2.5 px-4 font-medium">Awaiting approval</th>
                <th className="py-2.5 px-4 font-medium">Unrepaired failures</th>
                <th className="py-2.5 px-4 font-medium">Data</th>
              </tr>
            </thead>
            <tbody>
              {apps.map(({ tenant, lastGated, activeDesigns, awaitingApproval, unrepaired, lastRun }) => {
                const received = lastRun !== null;
                return (
                  <tr key={tenant.tenantId} className="border-t border-black/10 dark:border-white/10 align-top">
                    <td className="py-2.5 px-4">
                      <Link className="text-blue-700 dark:text-blue-400 hover:underline" href={`/dev/apps/${tenant.tenantId}`}>
                        {tenant.name}
                      </Link>
                      <div className="text-xs text-black/40 dark:text-white/40">
                        {tenant.repoUrl ? tenant.repoUrl.replace(/^https?:\/\//, "") : "no repository registered"}
                      </div>
                    </td>
                    <td className="py-2.5 px-4">
                      {lastGated ? (
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <VerdictBadge verdict={lastGated.verdict} />
                            <ShortSha sha={lastGated.sha} href={commitUrl(tenant, lastGated.sha)} />
                          </div>
                          <div className="text-black/70 dark:text-white/70">{lastGated.subject}</div>
                        </div>
                      ) : (
                        <span className="text-black/40 dark:text-white/40">—</span>
                      )}
                    </td>
                    {/* Counts only mean something once data has arrived; before
                        that they are unknown, not zero. */}
                    <td className="py-2.5 px-4">{received ? activeDesigns : "—"}</td>
                    <td className="py-2.5 px-4">
                      {!received ? "—" : awaitingApproval > 0 ? <Badge tone="warning">{awaitingApproval}</Badge> : 0}
                    </td>
                    <td className="py-2.5 px-4">
                      {!received ? "—" : unrepaired > 0 ? <Badge tone="danger">{unrepaired}</Badge> : 0}
                    </td>
                    <td className="py-2.5 px-4 text-sm">
                      <Freshness lastReceived={lastRun?.receivedAt ?? null} provider={tenant.repoProvider} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
