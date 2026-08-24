// portal/lib/cost.ts — reads runtime/llm_gateway.py's Postgres budget table
// directly (read-only). Schema is owned by llm_gateway.py's _PostgresBudgetBackend,
// not by this app — see runtime/llm_gateway.py for the canonical definition.
//
// `wired` is the same signal lib/dlq.ts carries, for the same reason and now in
// the same vocabulary: llm_gateway_budget is created by the GATEWAY on first
// use, not by this portal's migration, so "no worker has ever run against this
// database" is a normal state — and it used to be reported as `spentUsd: 0`.
// A dashboard cannot tell that apart from a tenant that spent nothing, and the
// two are opposite facts: one is a healthy quiet month, the other is a
// pipeline that has never started. The DLQ column beside it on the same page
// had this right; this one did not.

import { getPool, tableExists } from "./db";
import { getTenant } from "./tenants";

export interface CostByPeriod {
  period: string;     // "YYYY-MM"
  spentUsd: number;
}

export interface TenantCost {
  tenantId: string;
  /** False = the gateway's budget table does not exist yet. Every figure below
   *  is then an absence, not a measurement. */
  wired: boolean;
  spentUsd: number;       // current month
  cap: number | null;     // tenants.budget_cap_usd — null until synced from tenant.yaml (Product_Archive.md P2b)
  history: CostByPeriod[];
}

/** Current-month spend per tenant, plus whether anything was measurable. */
export interface CurrentSpend {
  wired: boolean;
  byTenant: Record<string, number>;
}

/** One definition of "this month", used by both queries below. UTC on
 *  purpose — see OPERATIONS.md; the gateway writes the same period key. */
function currentPeriod(): string {
  return new Date().toISOString().slice(0, 7);
}

export async function getTenantCost(tenantId: string, months = 6): Promise<TenantCost> {
  const tenant = await getTenant(tenantId);
  const cap = tenant?.budgetCapUsd ?? null;

  const hasTable = await tableExists("llm_gateway_budget");
  if (!hasTable) {
    // The cap still comes from `tenants` and is a real declared value; the
    // spend is not zero, it is unknown.
    return { tenantId, wired: false, spentUsd: 0, cap, history: [] };
  }

  const { rows } = await getPool().query(
    `SELECT period, spent_usd FROM llm_gateway_budget
     WHERE tenant_id = $1
     ORDER BY period DESC
     LIMIT $2`,
    [tenantId, months]
  );

  const history: CostByPeriod[] = rows
    .map((r) => ({ period: r.period as string, spentUsd: Number(r.spent_usd) }))
    .reverse();

  const current = history.find((h) => h.period === currentPeriod());

  return {
    tenantId,
    wired: true,
    spentUsd: current?.spentUsd ?? 0,
    cap,
    history,
  };
}

export async function getAllTenantsCurrentSpend(): Promise<CurrentSpend> {
  const hasTable = await tableExists("llm_gateway_budget");
  if (!hasTable) return { wired: false, byTenant: {} };

  const { rows } = await getPool().query(
    `SELECT tenant_id, spent_usd FROM llm_gateway_budget WHERE period = $1`,
    [currentPeriod()]
  );
  const byTenant: Record<string, number> = {};
  for (const r of rows) byTenant[r.tenant_id] = Number(r.spent_usd);
  return { wired: true, byTenant };
}
