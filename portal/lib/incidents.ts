// portal/lib/incidents.ts — open and close an incident, each with its audit line in the
// same transaction (DESC ISR domain 4).

import { appendAuditEvent } from "./auditLog";
import { withTransaction } from "./db";

export const SEVERITIES = ["low", "medium", "high", "critical"] as const;
export type Severity = (typeof SEVERITIES)[number];

export async function openIncident(input: {
  tenantId: string; title: string; severity: Severity; details: string; actor: string;
}): Promise<number> {
  let id = 0;
  await withTransaction("incident_open", async (client) => {
    const { rows } = await client.query(
      `INSERT INTO incidents (tenant_id, title, severity, details, opened_by) VALUES ($1,$2,$3,$4,$5) RETURNING incident_id`,
      [input.tenantId, input.title, input.severity, input.details, input.actor],
    );
    id = Number(rows[0].incident_id);
    await appendAuditEvent({ eventType: "incident", actorId: input.actor, tenantId: input.tenantId,
                             details: { action: "open", incident: id, severity: input.severity } }, client);
  });
  return id;
}

/** True when it closed an open incident of this app. The audit line is written only then:
 *  a second click, or another app's id, changed nothing and was audited as a close before
 *  (the 4.1.0 review's second pass, P2-R21). */
export async function closeIncident(tenantId: string, incidentId: number, actor: string): Promise<boolean> {
  let closed = false;
  await withTransaction("incident_close", async (client) => {
    const { rowCount } = await client.query(
      `UPDATE incidents SET status = 'closed', closed_by = $1, closed_at = now()
         WHERE incident_id = $2 AND tenant_id = $3 AND status = 'open'`,
      [actor, incidentId, tenantId],
    );
    closed = rowCount === 1;
    if (closed) {
      await appendAuditEvent({ eventType: "incident", actorId: actor, tenantId, details: { action: "close", incident: incidentId } }, client);
    }
  });
  return closed;
}
