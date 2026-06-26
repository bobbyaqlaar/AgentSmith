// portal/lib/tenants.ts — tenant registry (SPECS.md §23, §26).

import { getPool } from "./db";

export interface Tenant {
  tenantId: string;
  name: string;
  isolation: "shared" | "dedicated";
  phoenixBaseUrl: string | null;
  budgetCapUsd: number | null;
  // URL only — never the secret. replay_webhook_secret is read-only-by-
  // server-side-code-that-needs-it (see getReplayWebhookConfig below); it
  // must never appear in any API response or be added to this interface.
  replayWebhookUrl: string | null;
  createdAt: string;
}

const TENANT_COLUMNS = "tenant_id, name, isolation, phoenix_base_url, budget_cap_usd, replay_webhook_url, created_at";

function rowToTenant(r: any): Tenant {
  return {
    tenantId: r.tenant_id,
    name: r.name,
    isolation: r.isolation,
    phoenixBaseUrl: r.phoenix_base_url,
    budgetCapUsd: r.budget_cap_usd !== null ? Number(r.budget_cap_usd) : null,
    replayWebhookUrl: r.replay_webhook_url,
    createdAt: r.created_at,
  };
}

export async function listTenants(): Promise<Tenant[]> {
  const { rows } = await getPool().query(`SELECT ${TENANT_COLUMNS} FROM tenants ORDER BY tenant_id`);
  return rows.map(rowToTenant);
}

export async function getTenant(tenantId: string): Promise<Tenant | null> {
  const { rows } = await getPool().query(`SELECT ${TENANT_COLUMNS} FROM tenants WHERE tenant_id = $1`, [tenantId]);
  return rows.length === 0 ? null : rowToTenant(rows[0]);
}

// Deliberately separate from getTenant()/Tenant — this is the one place
// the secret is allowed to leave the database, and only into server-side
// code that signs an outgoing webhook (portal/lib/dlq.ts's
// replayDlqEntry()). Never expose this via an API route.
export async function getReplayWebhookConfig(
  tenantId: string
): Promise<{ url: string; secret: string } | null> {
  const { rows } = await getPool().query(
    `SELECT replay_webhook_url, replay_webhook_secret FROM tenants WHERE tenant_id = $1`,
    [tenantId]
  );
  const r = rows[0];
  if (!r?.replay_webhook_url || !r?.replay_webhook_secret) return null;
  return { url: r.replay_webhook_url, secret: r.replay_webhook_secret };
}

export async function upsertTenant(t: {
  tenantId: string;
  name: string;
  isolation?: string;
  phoenixBaseUrl?: string;
  budgetCapUsd?: number | null;
  replayWebhookUrl?: string | null;
  replayWebhookSecret?: string | null;
}): Promise<void> {
  await getPool().query(
    `INSERT INTO tenants (tenant_id, name, isolation, phoenix_base_url, budget_cap_usd, replay_webhook_url, replay_webhook_secret)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     ON CONFLICT (tenant_id) DO UPDATE SET
       name = EXCLUDED.name,
       isolation = EXCLUDED.isolation,
       phoenix_base_url = COALESCE(EXCLUDED.phoenix_base_url, tenants.phoenix_base_url),
       budget_cap_usd = COALESCE(EXCLUDED.budget_cap_usd, tenants.budget_cap_usd),
       replay_webhook_url = COALESCE(EXCLUDED.replay_webhook_url, tenants.replay_webhook_url),
       replay_webhook_secret = COALESCE(EXCLUDED.replay_webhook_secret, tenants.replay_webhook_secret)`,
    [
      t.tenantId, t.name, t.isolation ?? "shared", t.phoenixBaseUrl ?? null, t.budgetCapUsd ?? null,
      t.replayWebhookUrl ?? null, t.replayWebhookSecret ?? null,
    ]
  );
}
