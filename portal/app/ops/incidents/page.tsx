// /ops/incidents — the incident register (DESC ISR domain 4).

import { IncidentClose } from "@/components/IncidentClose";
import { IncidentForm } from "@/components/IncidentForm";
import { Badge } from "@/components/ui/Badge";
import { Timestamp } from "@/components/ui/Timestamp";
import { appsWith } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { getPool } from "@/lib/db";
import { listTenants } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function IncidentsPage() {
  const access = await currentAccess();
  const ids = (await listTenants()).map((t) => t.tenantId);
  const visible = appsWith(access, "ops.read", ids);
  const writable = appsWith(access, "ops.incident", ids);
  const { rows } = visible.length
    ? await getPool().query(`SELECT * FROM incidents WHERE tenant_id = ANY($1) ORDER BY opened_at DESC LIMIT 200`, [visible])
    : { rows: [] };
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-medium">Incidents</h2>
      {writable.length > 0 && <IncidentForm apps={writable} />}
      {rows.length === 0 && <p className="text-black/60 dark:text-white/60">No incidents recorded.</p>}
      <ul className="space-y-2">
        {rows.map((i) => (
          <li key={String(i.incident_id)} className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm space-y-1">
            <div className="flex flex-wrap gap-2 items-center">
              <Badge tone={i.status === "open" ? "danger" : "neutral"}>{i.status}</Badge>
              <span className="font-medium">{i.title}</span>
              <span className="text-black/60 dark:text-white/60">{i.tenant_id} · {i.severity}</span>
              {i.status === "open" && writable.includes(i.tenant_id) && <IncidentClose tenantId={i.tenant_id} incidentId={Number(i.incident_id)} />}
            </div>
            <div className="text-black/60 dark:text-white/60">Opened by {i.opened_by} · <Timestamp value={i.opened_at} />{i.closed_at && <> · closed by {i.closed_by}</>}</div>
            {i.details && <p>{i.details}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
