// portal/lib/compliance.ts — the app's signatures, in Postgres. The catalogue is a
// generated copy of fixtures/compliance/catalogue.json
// (scripts/generate-ide-config.py --compliance holds it to its source).

import { randomBytes } from "node:crypto";

import { appendAuditEvent } from "./auditLog";
import catalogueJson from "./complianceCatalogue.json";
import type { AttestationRecord, ObligationRow } from "./complianceState";
import { getPool, withTransaction } from "./db";

export const CATALOGUE = catalogueJson as unknown as ObligationRow[];
export const KNOWN_OBLIGATIONS = new Set(CATALOGUE.map((r) => r.id));

function toRecord(row: Record<string, unknown>): AttestationRecord {
  return {
    id: row.attestation_id as string,
    obligation: row.obligation_id as string,
    actor: row.actor as string,
    role: row.role as string,
    evidence: row.evidence as string,
    attested_at: (row.attested_at as Date).toISOString(),
    expires_at: row.expires_at ? (row.expires_at as Date).toISOString() : null,
    note: row.note as string,
    channel: row.channel as "tty" | "portal",
  };
}

export async function listAttestations(tenantId: string, channel?: "tty" | "portal"): Promise<AttestationRecord[]> {
  const { rows } = await getPool().query(
    `SELECT * FROM compliance_attestations WHERE tenant_id = $1 AND ($2::text IS NULL OR channel = $2) ORDER BY attested_at DESC`,
    [tenantId, channel ?? null],
  );
  return rows.map(toRecord);
}

/** A repository's signatures arrive again on every run; the id makes that harmless. */
export async function storeRepoAttestations(tenantId: string, records: AttestationRecord[]): Promise<void> {
  await withTransaction("compliance_sync", async (client) => {
    for (const r of records) {
      await client.query(
        `INSERT INTO compliance_attestations (attestation_id, tenant_id, obligation_id, actor, role, evidence, note, channel, attested_at, expires_at)
         VALUES ($1,$2,$3,$4,$5,$6,$7,'tty',$8,$9) ON CONFLICT (tenant_id, attestation_id) DO NOTHING`,
        [r.id, tenantId, r.obligation, r.actor, r.role, r.evidence, r.note, r.attested_at, r.expires_at],
      );
    }
  });
}

export class NotAttestable extends Error {}

/** A signature given in the portal, and its line in the audit log, in one transaction. */
export async function signObligation(input: {
  tenantId: string; obligation: string; actor: string; evidence: string; note: string;
}): Promise<AttestationRecord> {
  const row = CATALOGUE.find((r) => r.id === input.obligation);
  if (!row || row.class !== "attested") throw new NotAttestable(`${input.obligation} is not an attested obligation`);
  const now = new Date();
  const expires = row.recurrence_days ? new Date(now.getTime() + row.recurrence_days * 86_400_000) : null;
  const id = `T-${randomBytes(4).toString("hex")}`;
  return withTransaction("compliance_attest", async (client) => {
    const { rows } = await client.query(
      `INSERT INTO compliance_attestations (attestation_id, tenant_id, obligation_id, actor, role, evidence, note, channel, attested_at, expires_at)
       VALUES ($1,$2,$3,$4,'compliance_officer',$5,$6,'portal',$7,$8) RETURNING *`,
      [id, input.tenantId, input.obligation, input.actor, input.evidence, input.note, now, expires],
    );
    await appendAuditEvent(
      { eventType: "compliance_attestation", actorId: input.actor, tenantId: input.tenantId,
        details: { obligation: input.obligation, attestation: id, evidence: input.evidence } },
      client,
    );
    return toRecord(rows[0]);
  });
}
