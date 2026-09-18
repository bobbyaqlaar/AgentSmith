// /dev/approvals — deviations in active designs with no approval yet, across
// every app the user may see, oldest first (portal phase 1). Approving from
// here arrives in phase 2.

import Link from "next/link";

import { ShortSha } from "@/components/DevBits";
import { Timestamp } from "@/components/ui/Timestamp";
import { appsWith } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { listAwaitingApprovals } from "@/lib/devRead";
import { commitUrl } from "@/lib/devView";
import { listTenants } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function DevApprovalsPage() {
  const tenants = await listTenants();
  const visible = appsWith(currentAccess(), "dev.read", tenants.map((t) => t.tenantId));
  const byId = new Map(tenants.map((t) => [t.tenantId, t]));
  const awaiting = await listAwaitingApprovals(visible);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-medium">Awaiting approval</h2>
      <p className="text-sm text-black/60 dark:text-white/60">
        Deviations in active designs that no approval covers yet. Approving from the portal arrives in phase 2; until
        then an approval is recorded at a terminal with <code>agentsmith approve</code>.
      </p>
      {awaiting.length === 0 ? (
        <p className="text-black/60 dark:text-white/60">
          Nothing awaits approval in the {visible.length} app{visible.length === 1 ? "" : "s"} you can see.
        </p>
      ) : (
        <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
              <tr>
                <th className="py-2.5 px-4 font-medium">App</th>
                <th className="py-2.5 px-4 font-medium">Design</th>
                <th className="py-2.5 px-4 font-medium">Deviation</th>
                <th className="py-2.5 px-4 font-medium">Author</th>
                <th className="py-2.5 px-4 font-medium">Since</th>
              </tr>
            </thead>
            <tbody>
              {awaiting.map((a) => {
                const tenant = byId.get(a.tenantId)!;
                return (
                  <tr key={`${a.tenantId}-${a.design.path}-${a.deviationId}`} className="border-t border-black/10 dark:border-white/10">
                    <td className="py-2.5 px-4">{tenant.name}</td>
                    <td className="py-2.5 px-4">
                      <Link className="text-blue-700 dark:text-blue-400 hover:underline"
                            href={`/dev/apps/${a.tenantId}/designs/${(a.design.path ?? "").split("/").map(encodeURIComponent).join("/")}`}>
                        {a.design.title ?? a.design.path}
                      </Link>
                    </td>
                    <td className="py-2.5 px-4"><code className="font-mono">{a.deviationId}</code></td>
                    <td className="py-2.5 px-4">{a.authorName ?? "—"}</td>
                    <td className="py-2.5 px-4 text-black/60 dark:text-white/60">
                      {a.committedAt ? <Timestamp value={a.committedAt} /> : "—"}{" "}
                      <ShortSha sha={a.sha} href={commitUrl(tenant, a.sha)} />
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
