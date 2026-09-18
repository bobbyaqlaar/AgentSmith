// /admin/apps — register apps, and see each one's repository and ingest token
// (Administration › Apps; portal phase 1).

import Link from "next/link";

import { AppForm } from "@/components/AppForm";
import { Badge } from "@/components/ui/Badge";
import { Timestamp } from "@/components/ui/Timestamp";
import { appsWith } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { ingestTokenStatus } from "@/lib/ingestTokens";
import { listTenants } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function AdminAppsPage() {
  const all = await listTenants();
  const visible = new Set(appsWith(currentAccess(), "admin.apps", all.map((t) => t.tenantId)));
  const apps = all.filter((t) => visible.has(t.tenantId));
  const tokens = new Map((await ingestTokenStatus(apps.map((a) => a.tenantId))).map((s) => [s.tenantId, s]));

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h2 className="text-xl font-medium">Apps</h2>
        {apps.length === 0 ? (
          <p className="text-black/60 dark:text-white/60">No apps registered yet.</p>
        ) : (
          <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
                <tr>
                  <th className="py-2.5 px-4 font-medium">App</th>
                  <th className="py-2.5 px-4 font-medium">Repository</th>
                  <th className="py-2.5 px-4 font-medium">Ingest token</th>
                </tr>
              </thead>
              <tbody>
                {apps.map((a) => {
                  const token = tokens.get(a.tenantId);
                  return (
                    <tr key={a.tenantId} className="border-t border-black/10 dark:border-white/10">
                      <td className="py-2.5 px-4">
                        <Link className="text-blue-700 dark:text-blue-400 hover:underline" href={`/admin/apps/${a.tenantId}`}>
                          {a.name}
                        </Link>
                        <span className="ml-2 text-black/40 dark:text-white/40">({a.tenantId})</span>
                      </td>
                      <td className="py-2.5 px-4 text-black/70 dark:text-white/70">
                        {a.repoUrl ? `${a.repoUrl.replace(/^https?:\/\//, "")} · ${a.defaultBranch ?? "no branch"}` : "none registered"}
                      </td>
                      <td className="py-2.5 px-4">
                        {token && token.active > 0 ? (
                          <span className="text-black/60 dark:text-white/60">
                            <Badge tone="success">issued</Badge>{" "}
                            {token.issuedAt && <Timestamp value={token.issuedAt} />}
                            {token.issuedBy && ` by ${token.issuedBy}`}
                          </span>
                        ) : (
                          <Badge tone="neutral">none — CI cannot send</Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="font-medium">Register an app</h3>
        <AppForm mode="create" />
      </section>
    </div>
  );
}
