// portal/lib/issues.ts — unresolved MAJOR/CRITICAL .agent-history.log entries,
// synced per-tenant via POST /api/sync/history (SPECS.md §19, §26).

import { getPool } from "./db";

export interface HistoryEntry {
  entryId: string;
  level: "INFO" | "MINOR" | "MAJOR" | "CRITICAL";
  event: string;
  timestamp: string;
  hitlResolved: boolean;
  raw: Record<string, unknown>;
}

export async function getUnresolvedIssues(tenantId: string): Promise<HistoryEntry[]> {
  const { rows } = await getPool().query(
    `SELECT entry_id, level, event, timestamp, hitl_resolved, raw
     FROM agent_history_entries
     WHERE tenant_id = $1 AND hitl_resolved = FALSE AND level IN ('MAJOR', 'CRITICAL')
     ORDER BY timestamp DESC
     LIMIT 200`,
    [tenantId]
  );
  return rows.map((r) => ({
    entryId: r.entry_id,
    level: r.level,
    event: r.event,
    timestamp: r.timestamp,
    hitlResolved: r.hitl_resolved,
    raw: r.raw,
  }));
}

export async function getUnresolvedCountByTenant(): Promise<Record<string, number>> {
  const { rows } = await getPool().query(
    `SELECT tenant_id, count(*) AS n
     FROM agent_history_entries
     WHERE hitl_resolved = FALSE AND level IN ('MAJOR', 'CRITICAL')
     GROUP BY tenant_id`
  );
  const out: Record<string, number> = {};
  for (const r of rows) out[r.tenant_id] = Number(r.n);
  return out;
}

export interface SyncEntryInput {
  entryId: string;
  level: string;
  event: string;
  timestamp: string;
  hitlResolved?: boolean;
  raw: Record<string, unknown>;
}

/**
 * Idempotent upsert of .agent-history.log entries for a tenant. Called by
 * cd-staging.yml / cd-production.yml (or a local ai-stack-check push) with
 * the tail of unresolved/changed entries since the last sync.
 */
export async function syncHistoryEntries(tenantId: string, entries: SyncEntryInput[]): Promise<number> {
  if (entries.length === 0) return 0;
  const pool = getPool();
  let written = 0;
  for (const e of entries) {
    await pool.query(
      `INSERT INTO agent_history_entries (tenant_id, entry_id, level, event, timestamp, hitl_resolved, raw)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       ON CONFLICT (tenant_id, entry_id) DO UPDATE SET
         hitl_resolved = EXCLUDED.hitl_resolved,
         raw = EXCLUDED.raw,
         synced_at = now()`,
      [tenantId, e.entryId, e.level, e.event, e.timestamp, e.hitlResolved ?? false, JSON.stringify(e.raw)]
    );
    written += 1;
  }
  return written;
}
