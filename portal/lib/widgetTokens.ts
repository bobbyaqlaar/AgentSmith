// portal/lib/widgetTokens.ts — read-only scoped tokens for the In-App Widget
// (templates/in-app-widget/, SPECS.md §15, §26).
//
// Security note: the token is the ONLY thing that determines which tenant's
// data a widget request can see. Any tenant-id supplied alongside the token
// (e.g. as a display label in the embed snippet) must never be trusted for
// access control — see app/api/widget/status/route.ts.

import { randomBytes, createHash } from "node:crypto";
import { getPool } from "./db";

function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export async function createWidgetToken(tenantId: string): Promise<string> {
  const token = randomBytes(24).toString("base64url");
  await getPool().query(
    `INSERT INTO widget_tokens (token_hash, tenant_id) VALUES ($1, $2)`,
    [hashToken(token), tenantId]
  );
  return token; // shown once — only the hash is persisted
}

export async function resolveWidgetToken(token: string): Promise<string | null> {
  if (!token) return null;
  const { rows } = await getPool().query(
    `SELECT tenant_id FROM widget_tokens WHERE token_hash = $1 AND revoked_at IS NULL`,
    [hashToken(token)]
  );
  return rows[0]?.tenant_id ?? null;
}

export async function revokeWidgetToken(token: string): Promise<void> {
  await getPool().query(
    `UPDATE widget_tokens SET revoked_at = now() WHERE token_hash = $1`,
    [hashToken(token)]
  );
}

// The portal never retains a widget token's plaintext after mint (only its
// hash is stored — see createWidgetToken above), so a "revoke this leaked
// token" UI action can't call revokeWidgetToken(token) with anything the
// portal actually has on hand. Revoking by tenant instead achieves the same
// practical goal (a leaked token stops working) without needing the
// plaintext: it revokes every still-active token for that tenant, and the
// admin mints a fresh one via POST .../widget-token afterward.
export async function revokeWidgetTokensForTenant(tenantId: string): Promise<number> {
  const { rowCount } = await getPool().query(
    `UPDATE widget_tokens SET revoked_at = now() WHERE tenant_id = $1 AND revoked_at IS NULL`,
    [tenantId]
  );
  return rowCount ?? 0;
}
