// /ops/compliance — every app's checklist at a glance: what is unsigned or
// running out, so nobody has to open each app to find it.

import Link from "next/link";

import { appsWith } from "@/lib/authz";
import { CATALOGUE, listAttestations } from "@/lib/compliance";
import { checklist } from "@/lib/complianceState";
import { currentAccess } from "@/lib/currentAccess";
import { listTenants } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function AdminCompliancePage() {
  const all = await listTenants();
  const visible = new Set(appsWith(await currentAccess(), "compliance.read", all.map((t) => t.tenantId)));
  const now = new Date();
  const apps = await Promise.all(all.filter((t) => visible.has(t.tenantId)).map(async (t) => {
    const rows = checklist(CATALOGUE, await listAttestations(t.tenantId), now);
    const count = (...states: string[]) => rows.filter((r) => states.includes(r.state)).length;
    return { id: t.tenantId, name: t.name, unsigned: count("missing", "expired"), expiring: count("expiring"), signed: count("signed") };
  }));

  return (
    <section className="space-y-3">
      <h2 className="text-xl font-medium">Compliance</h2>
      {apps.length === 0 ? (
        <p className="text-black/60 dark:text-white/60">No apps you can see.</p>
      ) : (
        <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
              <tr>
                <th className="py-2.5 px-4 font-medium">App</th>
                <th className="py-2.5 px-4 font-medium">Unsigned or expired</th>
                <th className="py-2.5 px-4 font-medium">Expiring soon</th>
                <th className="py-2.5 px-4 font-medium">Signed</th>
              </tr>
            </thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.id} className="border-t border-black/10 dark:border-white/10">
                  <td className="py-2.5 px-4">
                    <Link className="text-blue-700 dark:text-blue-400 hover:underline" href={`/ops/apps/${encodeURIComponent(a.id)}/compliance`}>{a.name}</Link>
                  </td>
                  <td className="py-2.5 px-4">{a.unsigned}</td>
                  <td className="py-2.5 px-4">{a.expiring}</td>
                  <td className="py-2.5 px-4">{a.signed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
