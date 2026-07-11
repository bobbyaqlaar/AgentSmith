// portal/lib/sessionRevocation.ts — server-side denylist for SSO session
// JWTs (Product_Archive.md 4.14). Node-runtime only (uses `pg` via
// lib/db.ts) — see lib/sessionToken.ts's header comment for why this can't
// be imported directly from middleware.ts (Edge runtime). middleware.ts
// instead calls GET /api/auth/session-status (Node runtime) over fetch,
// which itself calls isSessionRevoked() below.

import { getPool } from "./db";

export async function revokeSession(jti: string): Promise<void> {
  await getPool().query(
    `INSERT INTO revoked_sessions (jti) VALUES ($1) ON CONFLICT (jti) DO NOTHING`,
    [jti]
  );
}

export async function isSessionRevoked(jti: string): Promise<boolean> {
  const { rows } = await getPool().query(
    `SELECT 1 FROM revoked_sessions WHERE jti = $1`,
    [jti]
  );
  return rows.length > 0;
}
