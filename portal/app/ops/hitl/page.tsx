// /ops/hitl — gates waiting for a named person. Only apps on a compliance profile
// send them here; other apps' gates are decided however the app chooses.

import { HitlDecision } from "@/components/HitlDecision";
import { Timestamp } from "@/components/ui/Timestamp";
import { appsWith } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { listPending } from "@/lib/hitl";
import { listTenants } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function HitlPage() {
  const access = await currentAccess();
  const apps = appsWith(access, "ops.hitl", (await listTenants()).map((t) => t.tenantId));
  const pending = apps.length ? await listPending(apps) : [];
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-medium">Human decisions</h2>
      {pending.length === 0 && <p className="text-black/60 dark:text-white/60">Nothing is waiting for a decision.</p>}
      {pending.map((g) => (
        <article key={`${g.tenantId}:${g.recordId}`} className="border border-black/10 dark:border-white/10 rounded-lg p-4 space-y-3">
          <div className="text-sm text-black/60 dark:text-white/60">{g.tenantId} · <Timestamp value={g.createdAt} />{g.requestedBy ? ` · asked by ${g.requestedBy}` : ""}</div>
          <h3 className="font-medium">{g.action}</h3>
          <pre className="text-xs overflow-x-auto bg-black/[0.03] dark:bg-white/[0.05] rounded-md p-3">{JSON.stringify(g.input, null, 2)}</pre>
          <div className="text-xs font-mono text-black/40 dark:text-white/40">gate {g.gateId} · sha256 {g.inputSha256}</div>
          <HitlDecision tenantId={g.tenantId} recordId={g.recordId} />
        </article>
      ))}
    </section>
  );
}
