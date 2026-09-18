// portal/lib/ingestTokens.ts — an app's CI credential for the Dev ingest
// (portal phase 1, S3). Same shape as lib/widgetTokens.ts: a random token shown
// once, only its SHA-256 stored, and the token alone decides which app a
// request writes to — never an id supplied alongside it.

import { createHash, randomBytes } from "node:crypto";

import { getPool } from "./db";

export function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

/** A new token and the hash that is all the portal keeps of it. The one place tokens are made. */
export function newIngestToken(): { token: string; hash: string } {
  const token = `asi_${randomBytes(32).toString("base64url")}`;
  return { token, hash: hashToken(token) };
}

/** Issues a new token for `tenantId`, alongside any it already has. For tests and
 *  seeding; Administration › Apps rotates instead (lib/apps.rotateIngestToken). */
export async function createIngestToken(tenantId: string, createdBy: string | null): Promise<string> {
  const { token, hash } = newIngestToken();
  await getPool().query(
    `INSERT INTO app_ingest_tokens (token_hash, tenant_id, created_by) VALUES ($1, $2, $3)`,
    [hash, tenantId, createdBy],
  );
  return token;
}

/** The app an unrevoked token belongs to, or null. */
export async function resolveIngestToken(token: string): Promise<string | null> {
  if (!token) return null;
  const { rows } = await getPool().query(
    `SELECT tenant_id FROM app_ingest_tokens WHERE token_hash = $1 AND revoked_at IS NULL`,
    [hashToken(token)],
  );
  return rows[0]?.tenant_id ?? null;
}

/** Revokes every live token for `tenantId` — the portal never holds a plaintext to revoke one by. */
export async function revokeIngestTokens(tenantId: string): Promise<number> {
  const { rowCount } = await getPool().query(
    `UPDATE app_ingest_tokens SET revoked_at = now() WHERE tenant_id = $1 AND revoked_at IS NULL`,
    [tenantId],
  );
  return rowCount ?? 0;
}

/**
 * The token of an `Authorization: Bearer <token>` header, or null. Here rather
 * than in lib/bearerAuth.ts, which compares against one environment variable
 * and imports Next: these tokens are looked up by hash, and this module is
 * imported by tests that run without Next.
 */
export function bearerToken(header: string | null): string | null {
  const match = header?.match(/^Bearer\s+(\S+)$/);
  return match ? match[1] : null;
}

export interface IngestTokenStatus {
  tenantId: string;
  /** Live tokens: normally 0 or 1. */
  active: number;
  /** When the newest live token was issued, and by whom. */
  issuedAt: string | null;
  issuedBy: string | null;
}

/** Whether each app has a working ingest token — never the token itself. */
export async function ingestTokenStatus(tenantIds: string[]): Promise<IngestTokenStatus[]> {
  const { rows } = await getPool().query(
    `SELECT t.tenant_id,
            count(k.token_hash) FILTER (WHERE k.revoked_at IS NULL)::int AS active,
            max(k.created_at) FILTER (WHERE k.revoked_at IS NULL) AS issued_at,
            (array_agg(k.created_by ORDER BY k.created_at DESC) FILTER (WHERE k.revoked_at IS NULL))[1] AS issued_by
       FROM unnest($1::text[]) AS t(tenant_id)
       LEFT JOIN app_ingest_tokens k ON k.tenant_id = t.tenant_id
      GROUP BY t.tenant_id`,
    [tenantIds],
  );
  return rows.map((r) => ({
    tenantId: r.tenant_id,
    active: r.active,
    issuedAt: r.issued_at ? new Date(r.issued_at).toISOString() : null,
    issuedBy: r.issued_by,
  }));
}
