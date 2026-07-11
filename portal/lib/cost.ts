// portal/lib/cost.ts — reads runtime/llm_gateway.py's Postgres budget table
// directly (read-only). Schema is owned by llm_gateway.py's _PostgresBudgetBackend,
// not by this app — see runtime/llm_gateway.py for the canonical definition.

import { getPool, tableExists } from "./db";
import { getTenant } from "./tenants";

export interface CostByPeriod {
  period: string;     // "YYYY-MM"
  spentUsd: number;
}

export interface TenantCost {
  tenantId: string;
  spentUsd: number;       // current month
  cap: number | null;     // tenants.budget_cap_usd — null until synced from tenant.yaml (Product_Archive.md P2b)
  history: CostByPeriod[];
}

export async function getTenantCost(tenantId: string, months = 6): Promise<TenantCost> {
  const tenant = await getTenant(tenantId);
  const cap = tenant?.budgetCapUsd ?? null;

  const hasTable = await tableExists("llm_gateway_budget");
  if (!hasTable) {
    return { tenantId, spentUsd: 0, cap, history: [] };
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

  const currentPeriod = new Date().toISOString().slice(0, 7);
  const current = history.find((h) => h.period === currentPeriod);

  return {
    tenantId,
    spentUsd: current?.spentUsd ?? 0,
    cap,
    history,
  };
}

export async function getAllTenantsCurrentSpend(): Promise<Record<string, number>> {
  const hasTable = await tableExists("llm_gateway_budget");
  if (!hasTable) return {};

  const currentPeriod = new Date().toISOString().slice(0, 7);
  const { rows } = await getPool().query(
    `SELECT tenant_id, spent_usd FROM llm_gateway_budget WHERE period = $1`,
    [currentPeriod]
  );
  const out: Record<string, number> = {};
  for (const r of rows) out[r.tenant_id] = Number(r.spent_usd);
  return out;
}
