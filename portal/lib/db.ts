// portal/lib/db.ts — shared Postgres pool. Same DATABASE_URL as
// runtime/llm_gateway.py's Postgres budget backend (SPECS.md §26).
//
// The pool traces its own queries (lib/tracing.ts). Instrumented HERE, inside
// the class, rather than at the twenty-eight `getPool().query(...)` call sites
// across nine modules: a helper every caller must remember to use is a rule,
// and the observability audit's finding was precisely that rules of this shape
// are followed by most call sites and not all. A traced pool makes it true by
// construction, and the next module to open a query is traced without knowing
// this file exists.

import { Pool } from "pg";

import { SpanKind, portalSpan, truncate } from "./tracing";

let pool: Pool | null = null;

/** The leading keyword, when it is one we recognise. Kept to a closed set:
 *  the span name is built from it, and an unbounded value there is a new span
 *  name per query — the cardinality mistake runtime/metrics.py warns about,
 *  wearing a different hat.
 *
 *  Exported for test/tracing.test.ts only. */
export function operationOf(statement: string | undefined): string {
  const word = (statement ?? "").trimStart().split(/\s+/, 1)[0]?.toUpperCase() ?? "";
  return ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "BEGIN", "COMMIT", "ROLLBACK"].includes(word)
    ? word
    : "QUERY";
}

/** The `query` forms that must NOT be wrapped: a trailing callback, or a
 *  Submittable (a Cursor) as the first argument. Both return something other
 *  than a promise, so wrapping them would change what the caller gets back.
 *  Exported for test/tracing.test.ts. */
export function isPassthroughQuery(args: unknown[]): boolean {
  const first = args[0] as { submit?: unknown } | string | undefined;
  const isSubmittable = typeof first === "object" && first !== null && typeof first.submit === "function";
  const hasCallback = typeof args[args.length - 1] === "function";
  return isSubmittable || hasCallback;
}

/**
 * A pool whose `query` opens a client span.
 *
 * `db.statement` is the PARAMETERISED text — code, not data. The values live
 * in the second argument and are never recorded: a portal span has no redactor
 * behind it (the Python side's runtime/trace_redactor.py protects only the
 * worker's spans), so nothing that could hold a row value goes on.
 */
class TracedPool extends Pool {
  query(...args: any[]): any {
    const passthrough = () => (super.query as (...rest: any[]) => any)(...args);
    if (isPassthroughQuery(args)) return passthrough();

    const first = args[0];
    const statement: string | undefined = typeof first === "string" ? first : first?.text;
    const operation = operationOf(statement);
    return portalSpan(
      `portal.db.${operation}`,
      {
        kind: SpanKind.CLIENT,
        attributes: {
          "db.system": "postgresql",
          "db.operation": operation,
          ...(statement ? { "db.statement": truncate(statement) } : {}),
        },
      },
      async (span) => {
        const result = await passthrough();
        // rowCount is a shape fact, not row content — the number is what makes
        // "the dashboard is empty" distinguishable from "the query never ran".
        if (typeof result?.rowCount === "number") span.setAttribute("db.response.returned_rows", result.rowCount);
        return result;
      },
    );
  }
}

export function getPool(): Pool {
  if (!pool) {
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl) {
      throw new Error("DATABASE_URL is not set. The Ops Portal requires the same Postgres instance used by runtime/llm_gateway.py.");
    }
    pool = new TracedPool({ connectionString: databaseUrl, max: 10 });
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
