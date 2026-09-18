// /dev/apps/<app>/designs — every design this app's commits named, as its
// latest commit described it; active first (portal phase 1).

import Link from "next/link";

import { PillarSummary } from "@/components/DevBits";
import { Badge } from "@/components/ui/Badge";
import { listDevDesigns } from "@/lib/devRead";
import { getTenant } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function DevDesignsPage({ params }: { params: { app: string } }) {
  const tenant = await getTenant(params.app);
  if (!tenant) return null;
  const designs = await listDevDesigns(tenant.tenantId);
  const base = `/dev/apps/${tenant.tenantId}/designs`;

  if (designs.length === 0) {
    return <p className="text-black/60 dark:text-white/60">No commit received so far names a design that resolves.</p>;
  }
  return (
    <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
          <tr>
            <th className="py-2.5 px-4 font-medium">Design</th>
            <th className="py-2.5 px-4 font-medium">Status</th>
            <th className="py-2.5 px-4 font-medium" title="applies · n/a · gap · deviation">Pillars</th>
            <th className="py-2.5 px-4 font-medium">Deviations</th>
            <th className="py-2.5 px-4 font-medium">Commits citing it</th>
          </tr>
        </thead>
        <tbody>
          {designs.map(({ design, citedBy }) => {
            const awaiting = design.deviations.filter((d) => !d.approvalId).length;
            return (
              <tr key={design.path} className="border-t border-black/10 dark:border-white/10 align-top">
                <td className="py-2.5 px-4">
                  <Link
                    className="text-blue-700 dark:text-blue-400 hover:underline"
                    href={`${base}/${(design.path ?? "").split("/").map(encodeURIComponent).join("/")}`}
                  >
                    {design.title ?? design.path}
                  </Link>
                  <div className="text-xs text-black/40 dark:text-white/40 font-mono">{design.path}</div>
                </td>
                <td className="py-2.5 px-4">
                  <Badge tone={design.status === "active" ? "warning" : "neutral"}>{design.status ?? "unknown"}</Badge>
                </td>
                <td className="py-2.5 px-4"><PillarSummary design={design} /></td>
                <td className="py-2.5 px-4">
                  {design.deviations.length === 0
                    ? "none"
                    : `${design.deviations.length - awaiting} approved · ${awaiting} awaiting`}
                </td>
                <td className="py-2.5 px-4">{citedBy}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
