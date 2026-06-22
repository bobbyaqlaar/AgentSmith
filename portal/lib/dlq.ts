// portal/lib/dlq.ts — dead-letter queue depth per tenant.
//
// runtime/dead_letter.py does not yet have a persistent store implementation
// (it's a Phase 2 follow-up — see SPECS.md §25 TODOs). This reads the
// `dlq_entries` table that the eventual Postgres-backed DeadLetterQueue
// would write to; until that lands, the table won't exist and callers get
// an explicit "not wired" result instead of fabricated zeros.

import { getPool, tableExists } from "./db";

export interface DLQStatus {
  wired: boolean;
  pendingByTenant: Record<string, number>;
}

export async function getDLQStatus(): Promise<DLQStatus> {
  const hasTable = await tableExists("dlq_entries");
  if (!hasTable) {
    return { wired: false, pendingByTenant: {} };
  }
  const { rows } = await getPool().query(
    `SELECT tenant_id, count(*) AS n FROM dlq_entries WHERE status = 'pending' GROUP BY tenant_id`
  );
  const pendingByTenant: Record<string, number> = {};
  for (const r of rows) pendingByTenant[r.tenant_id] = Number(r.n);
  return { wired: true, pendingByTenant };
}
