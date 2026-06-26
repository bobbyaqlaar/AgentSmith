// portal/scripts/migrate.ts — applies db/schema.sql against DATABASE_URL.
// Run: npm run db:migrate

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { Pool } from "pg";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main(): Promise<void> {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) {
    console.error("DATABASE_URL is required (same Postgres instance as runtime/llm_gateway.py).");
    process.exit(1);
  }

  const schemaPath = path.join(__dirname, "..", "db", "schema.sql");
  const schema = readFileSync(schemaPath, "utf-8");

  const pool = new Pool({ connectionString: databaseUrl });
  try {
    await pool.query(schema);
    console.log("Ops Portal schema applied successfully.");
  } finally {
    await pool.end();
  }
}

main().catch((err) => {
  console.error("Migration failed:", err);
  process.exit(1);
});
