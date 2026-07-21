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
  // One multi-VALUES statement instead of one awaited INSERT per entry
  // (ReviewFindings-2026-07-18 C3) — a sync batch is one round-trip.
  // Chunked so a very large backfill can't exceed Postgres's 65535
  // bind-parameter limit (7 params per row → 9000 rows ≈ 63k params).
  // Dedupe by entryId first (last occurrence wins): the old per-row loop
  // tolerated in-batch duplicates, but a single ON CONFLICT statement
  // errors if the same key appears twice in its VALUES list.
  const deduped = [...new Map(entries.map((e) => [e.entryId, e])).values()];
  const CHUNK = 500;
  let written = 0;
  for (let i = 0; i < deduped.length; i += CHUNK) {
    const chunk = deduped.slice(i, i + CHUNK);
    const params: unknown[] = [tenantId];
    const rows = chunk.map((e) => {
      const base = params.length;
      params.push(e.entryId, e.level, e.event, e.timestamp, e.hitlResolved ?? false, JSON.stringify(e.raw));
      return `($1, $${base + 1}, $${base + 2}, $${base + 3}, $${base + 4}, $${base + 5}, $${base + 6})`;
    });
    await pool.query(
      `INSERT INTO agent_history_entries (tenant_id, entry_id, level, event, timestamp, hitl_resolved, raw)
       VALUES ${rows.join(", ")}
       ON CONFLICT (tenant_id, entry_id) DO UPDATE SET
         hitl_resolved = EXCLUDED.hitl_resolved,
         raw = EXCLUDED.raw,
         synced_at = now()`,
      params
    );
    written += chunk.length;
  }
  return written;
}
