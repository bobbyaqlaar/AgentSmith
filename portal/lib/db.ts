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
