// portal/lib/db.ts — shared Postgres pool. Same DATABASE_URL as
// runtime/llm_gateway.py's Postgres budget backend (SPECS.md §26).

import { Pool } from "pg";

let pool: Pool | null = null;

export function getPool(): Pool {
  if (!pool) {
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl) {
      throw new Error("DATABASE_URL is not set. The Ops Portal requires the same Postgres instance used by runtime/llm_gateway.py.");
    }
    pool = new Pool({ connectionString: databaseUrl, max: 10 });
  }
  return pool;
}

export async function tableExists(tableName: string): Promise<boolean> {
  const { rows } = await getPool().query(
    "SELECT to_regclass($1) IS NOT NULL AS exists",
    [`public.${tableName}`]
  );
  return Boolean(rows[0]?.exists);
}

// dlq_entries is migrated by runtime/dead_letter.py (Python), not this
// portal's own schema.sql — a worker running an older dead_letter.py
// before the reason/workflow_id/gate_id columns existed means this table
// can lag behind what the portal's code expects. Check before querying
// columns that might not exist yet, same graceful-degrade philosophy as
// tableExists above (an old worker isn't an error, just a narrower view).
export async function columnExists(tableName: string, columnName: string): Promise<boolean> {
  const { rows } = await getPool().query(
    `SELECT 1 FROM information_schema.columns WHERE table_name = $1 AND column_name = $2`,
    [tableName, columnName]
  );
  return rows.length > 0;
}
