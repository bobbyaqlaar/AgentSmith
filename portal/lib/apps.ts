// portal/lib/apps.ts — registering and editing apps, and their ingest tokens
// (Administration › Apps; portal phase 1, S6).
//
// Every change writes its audit event inside the same transaction as the
// change, with the person who made it: the change and its record commit or
// roll back together. A token is never written to the audit log — only that
// one was issued, by whom, and how many it replaced.

import { appendAuditEvent } from "./auditLog";
import { withTransaction } from "./db";
import { newIngestToken } from "./ingestTokens";
import { isSafeHttpUrl } from "./safeUrl";
import { REPO_PROVIDERS, type RepoProvider } from "./tenants";

/** An app id appears in URLs, CI secrets and span attributes: lower-case, digits, dashes. */
export const APP_ID = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
const BRANCH = /^[A-Za-z0-9._/-]{1,255}$/;

export interface AppInput {
  id?: string;
  name: string;
  repoUrl: string | null;
  repoProvider: RepoProvider | null;
  defaultBranch: string | null;
}

export type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

function optional(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text === "" ? null : text;
}

/**
 * A registration (`create`, which names the id) or an edit (`update`, where the
 * URL names the app and any id in the body is ignored). Pure, so the test runs
 * the validator the routes run.
 */
export function parseAppInput(body: unknown, mode: "create" | "update"): Parsed<AppInput> {
  if (typeof body !== "object" || body === null) return { ok: false, error: "the body must be a JSON object" };
  const b = body as Record<string, unknown>;
  let id: string | undefined;
  if (mode === "create") {
    id = typeof b.id === "string" ? b.id.trim() : "";
    if (!APP_ID.test(id)) {
      return { ok: false, error: "id must be lower-case letters, digits and dashes, 1–63 characters, not starting or ending with a dash" };
    }
  }
  const name = typeof b.name === "string" ? b.name.trim() : "";
  if (name.length < 1 || name.length > 200) return { ok: false, error: "name must be 1–200 characters" };
  const repoUrl = optional(b.repoUrl);
  const provider = optional(b.repoProvider);
  const branch = optional(b.defaultBranch);
  if ((repoUrl === null) !== (provider === null)) {
    return { ok: false, error: "repoUrl and repoProvider go together — give both, or neither" };
  }
  if (repoUrl !== null && !isSafeHttpUrl(repoUrl)) return { ok: false, error: "repoUrl must be an http(s) URL" };
  if (provider !== null && !(REPO_PROVIDERS as readonly string[]).includes(provider)) {
    return { ok: false, error: `repoProvider must be one of ${REPO_PROVIDERS.join(", ")}` };
  }
  if (branch !== null && !BRANCH.test(branch)) return { ok: false, error: "defaultBranch is not a branch name" };
  return {
    ok: true,
    value: { ...(id ? { id } : {}), name, repoUrl, repoProvider: provider as RepoProvider | null, defaultBranch: branch },
  };
}

export class AppExistsError extends Error {}
export class AppMissingError extends Error {}

/** Registers a new app. Refuses an id that exists — registration never overwrites. */
export async function createApp(input: AppInput & { id: string }, actor: string): Promise<void> {
  await withTransaction("app_create", async (client) => {
    const { rowCount } = await client.query(
      `INSERT INTO tenants (tenant_id, name, repo_url, repo_provider, default_branch)
       VALUES ($1, $2, $3, $4, $5) ON CONFLICT (tenant_id) DO NOTHING`,
      [input.id, input.name, input.repoUrl, input.repoProvider, input.defaultBranch],
    );
    if (rowCount === 0) throw new AppExistsError(`an app called ${input.id} is already registered`);
    await appendAuditEvent(
      {
        eventType: "tenant_created",
        actorId: actor,
        tenantId: input.id,
        details: { action: "app_registered", name: input.name, repoUrl: input.repoUrl, repoProvider: input.repoProvider },
      },
      client,
    );
  });
}

/** Edits an app's name and repository, auditing which fields changed. */
export async function updateApp(id: string, input: AppInput, actor: string): Promise<void> {
  await withTransaction("app_update", async (client) => {
    const { rows } = await client.query(
      `SELECT name, repo_url, repo_provider, default_branch FROM tenants WHERE tenant_id = $1 FOR UPDATE`,
      [id],
    );
    if (rows.length === 0) throw new AppMissingError(`no app called ${id}`);
    const before = rows[0];
    const changed = [
      before.name !== input.name && "name",
      before.repo_url !== input.repoUrl && "repoUrl",
      before.repo_provider !== input.repoProvider && "repoProvider",
      before.default_branch !== input.defaultBranch && "defaultBranch",
    ].filter(Boolean);
    if (changed.length === 0) return;
    await client.query(
      `UPDATE tenants SET name = $2, repo_url = $3, repo_provider = $4, default_branch = $5 WHERE tenant_id = $1`,
      [id, input.name, input.repoUrl, input.repoProvider, input.defaultBranch],
    );
    await appendAuditEvent(
      { eventType: "config_change", actorId: actor, tenantId: id, details: { action: "app_updated", changed } },
      client,
    );
  });
}

/**
 * Revokes every live ingest token for the app and issues one new one, in one
 * transaction. Returns the new token — the only time it exists outside a hash.
 */
export async function rotateIngestToken(id: string, actor: string): Promise<string> {
  const { token, hash } = newIngestToken();
  await withTransaction("ingest_token_rotate", async (client) => {
    const exists = await client.query(`SELECT 1 FROM tenants WHERE tenant_id = $1`, [id]);
    if (exists.rowCount === 0) throw new AppMissingError(`no app called ${id}`);
    const revoked = await client.query(
      `UPDATE app_ingest_tokens SET revoked_at = now() WHERE tenant_id = $1 AND revoked_at IS NULL`,
      [id],
    );
    await client.query(`INSERT INTO app_ingest_tokens (token_hash, tenant_id, created_by) VALUES ($1, $2, $3)`, [
      hash,
      id,
      actor,
    ]);
    await appendAuditEvent(
      {
        eventType: "config_change",
        actorId: actor,
        tenantId: id,
        details: { action: "ingest_token_issued", revoked: revoked.rowCount ?? 0 },
      },
      client,
    );
  });
  return token;
}

/** Revokes every live ingest token for the app. Returns how many. */
export async function revokeAppIngestTokens(id: string, actor: string): Promise<number> {
  return withTransaction("ingest_token_revoke", async (client) => {
    const revoked = await client.query(
      `UPDATE app_ingest_tokens SET revoked_at = now() WHERE tenant_id = $1 AND revoked_at IS NULL`,
      [id],
    );
    const count = revoked.rowCount ?? 0;
    await appendAuditEvent(
      { eventType: "config_change", actorId: actor, tenantId: id, details: { action: "ingest_token_revoked", revoked: count } },
      client,
    );
    return count;
  });
}
