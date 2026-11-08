// /ops/apps/:id/decisions — the record of what this app did, by run: each model
// call, what was asked for review, who decided and why. Digests, not content: the
// words stay in the app's own stores.

import Link from "next/link";
import { notFound } from "next/navigation";

import { Timestamp } from "@/components/ui/Timestamp";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { getPool } from "@/lib/db";
import { getTenant } from "@/lib/tenants";

export const dynamic = "force-dynamic";

/** What a reviewer was shown can hold the case itself. Only a reviewer sees it here. */
function visiblePayload(payload: Record<string, unknown>, mayReview: boolean): Record<string, unknown> {
  if (mayReview || !("input" in payload)) return payload;
  const { input: _input, ...rest } = payload;
  return { ...rest, input: "(visible to HITL reviewers)" };
}

export default async function DecisionsPage(props: { params: Promise<{ id: string }>; searchParams: Promise<{ workflow?: string }> }) {
  const [params, searchParams] = await Promise.all([props.params, props.searchParams]);
  const access = await currentAccess();
  if (!can(access, "compliance.read", params.id)) notFound();
  const mayReview = can(access, "ops.hitl", params.id);
  const tenant = await getTenant(params.id);
  if (!tenant) notFound();
  const workflow = searchParams.workflow?.trim() || null;
  const { rows } = await getPool().query(
    `SELECT record_id, record_kind, payload, created_at FROM compliance_records
     WHERE tenant_id = $1 AND ($2::text IS NULL OR payload->>'workflow_id' = $2) ORDER BY record_id DESC LIMIT 200`,
    [tenant.tenantId, workflow],
  );
  return (
    <div className="space-y-4">
      <Link href={`/ops/apps/${encodeURIComponent(tenant.tenantId)}`} className="text-sm text-blue-700 dark:text-blue-400 hover:underline">← {tenant.name}</Link>
      <h2 className="text-xl font-medium">Decision trail</h2>
      <form className="flex gap-2 text-sm">
        <input name="workflow" defaultValue={workflow ?? ""} placeholder="Workflow id" aria-label="Workflow id"
          className="rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-2 py-1" />
        <button type="submit" className="px-3 py-1 rounded-md border border-black/20 dark:border-white/20">Show this run</button>
      </form>
      {rows.length === 0 && <p className="text-black/60 dark:text-white/60">No records yet. A worker sends them with <code>agentsmith ops forward</code>.</p>}
      <ol className="space-y-2">
        {rows.map((r) => (
          <li key={String(r.record_id)} className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm">
            <div className="flex gap-3"><span className="font-medium">{String(r.record_kind).replace(/_/g, " ").replace("hitl", "HITL")}</span><Timestamp value={r.created_at} className="text-black/60 dark:text-white/60" /></div>
            <pre className="text-xs overflow-x-auto mt-1 text-black/70 dark:text-white/70">{JSON.stringify(visiblePayload(r.payload, mayReview), null, 2)}</pre>
          </li>
        ))}
      </ol>
    </div>
  );
}
