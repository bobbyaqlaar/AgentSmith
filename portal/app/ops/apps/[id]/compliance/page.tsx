// /ops/apps/:id/compliance — the checklist for one app: what a person must sign,
// who signed it and when it runs out. Mechanism-backed rows are checked in CI by
// `agentsmith compliance check`; they are listed so the list is complete.

import Link from "next/link";
import { notFound } from "next/navigation";

import { AttestForm } from "@/components/AttestForm";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Timestamp } from "@/components/ui/Timestamp";
import { can } from "@/lib/authz";
import { CATALOGUE, listAttestations } from "@/lib/compliance";
import { checklist, type RowState } from "@/lib/complianceState";
import { currentAccess } from "@/lib/currentAccess";
import { getTenant } from "@/lib/tenants";

export const dynamic = "force-dynamic";

const PHASES = ["design", "build", "deploy", "operate"] as const;
const TONE: Record<RowState, BadgeTone> = { signed: "success", expiring: "warning", expired: "danger", missing: "danger", automatic: "neutral" };
const LABEL: Record<RowState, string> = { signed: "Signed", expiring: "Expiring soon", expired: "Expired", missing: "Not signed", automatic: "Checked in CI" };

export default async function CompliancePage(props: { params: Promise<{ id: string }> }) {
  const params = await props.params;
  const access = await currentAccess();
  if (!can(access, "compliance.read", params.id)) notFound();
  const tenant = await getTenant(params.id);
  if (!tenant) notFound();
  const rows = checklist(CATALOGUE, await listAttestations(tenant.tenantId), new Date());
  const mayAttest = can(access, "compliance.attest", tenant.tenantId);

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <Link href={`/ops/apps/${encodeURIComponent(tenant.tenantId)}`} className="text-sm text-blue-700 dark:text-blue-400 hover:underline">← {tenant.name}</Link>
        <h2 className="text-xl font-medium">Compliance checklist</h2>
        <p className="text-sm text-black/60 dark:text-white/60">
          Records the controls and evidence an assessor asks for. Not legal advice and not a certificate.
          {!mayAttest && " A compliance officer signs these."}
        </p>
      </div>
      {PHASES.map((phase) => (
        <section key={phase} className="space-y-3">
          <h3 className="font-medium capitalize">{phase}</h3>
          <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
                <tr>
                  <th className="py-2.5 px-4 font-medium">Obligation</th>
                  <th className="py-2.5 px-4 font-medium">Owner</th>
                  <th className="py-2.5 px-4 font-medium">State</th>
                  <th className="py-2.5 px-4 font-medium">Signed</th>
                  <th className="py-2.5 px-4 font-medium" />
                </tr>
              </thead>
              <tbody>
                {rows.filter((r) => r.obligation.phases[0] === phase).map(({ obligation: o, state, latest }) => (
                  <tr key={o.id} className="border-t border-black/10 dark:border-white/10 align-top">
                    <td className="py-2.5 px-4">
                      <div>{o.title}</div>
                      <div className="text-xs text-black/60 dark:text-white/60">{o.instructions}</div>
                      <div className="text-xs font-mono text-black/40 dark:text-white/40">{o.id}</div>
                    </td>
                    <td className="py-2.5 px-4 text-black/70 dark:text-white/70">{o.owner_role.replace(/_/g, " ")}</td>
                    <td className="py-2.5 px-4"><Badge tone={TONE[state]}>{LABEL[state]}</Badge></td>
                    <td className="py-2.5 px-4 text-black/70 dark:text-white/70">
                      {latest && <div>{latest.actor}{latest.channel === "tty" ? " (at a terminal)" : ""}</div>}
                      {latest && <Timestamp value={latest.attested_at} />}
                      {latest && <div className="text-xs break-all">{latest.evidence}</div>}
                    </td>
                    <td className="py-2.5 px-4">{mayAttest && o.class === "attested" && <AttestForm app={tenant.tenantId} obligation={o.id} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
