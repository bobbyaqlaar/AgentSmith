// portal/lib/tenants.ts — tenant registry (SPECS.md §23, §26).

import { getPool } from "./db";

export interface Tenant {
  tenantId: string;
  name: string;
  isolation: "shared" | "dedicated";
  phoenixBaseUrl: string | null;
  createdAt: string;
}

export async function listTenants(): Promise<Tenant[]> {
  const { rows } = await getPool().query(
    `SELECT tenant_id, name, isolation, phoenix_base_url, created_at
     FROM tenants ORDER BY tenant_id`
  );
  return rows.map((r) => ({
    tenantId: r.tenant_id,
    name: r.name,
    isolation: r.isolation,
    phoenixBaseUrl: r.phoenix_base_url,
    createdAt: r.created_at,
  }));
}

export async function getTenant(tenantId: string): Promise<Tenant | null> {
  const { rows } = await getPool().query(
    `SELECT tenant_id, name, isolation, phoenix_base_url, created_at
     FROM tenants WHERE tenant_id = $1`,
    [tenantId]
  );
  if (rows.length === 0) return null;
  const r = rows[0];
  return {
    tenantId: r.tenant_id,
    name: r.name,
    isolation: r.isolation,
    phoenixBaseUrl: r.phoenix_base_url,
    createdAt: r.created_at,
  };
}

export async function upsertTenant(t: { tenantId: string; name: string; isolation?: string; phoenixBaseUrl?: string }): Promise<void> {
  await getPool().query(
    `INSERT INTO tenants (tenant_id, name, isolation, phoenix_base_url)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (tenant_id) DO UPDATE SET
       name = EXCLUDED.name,
       isolation = EXCLUDED.isolation,
       phoenix_base_url = COALESCE(EXCLUDED.phoenix_base_url, tenants.phoenix_base_url)`,
    [t.tenantId, t.name, t.isolation ?? "shared", t.phoenixBaseUrl ?? null]
  );
}
