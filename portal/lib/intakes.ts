// portal/lib/intakes.ts — an author's answers for a tenant not yet created,
// pulled by `agentsmith tenant init --from <id>`
// (.agent-rfc/designs/portal-intake-pull.md; wire format contract/intake/v1/).
//
// The portal never writes into a repository. It stores the record and hands
// out one token for it; the author's own machine fetches it, scaffolds, and
// only then marks it consumed — so the first commit is still made locally and
// still vouched by .agenticframework/scaffold.json.
//
// The token is the ingest token's shape (lib/ingestTokens.ts): random, shown
// once, only its SHA-256 kept. It opens exactly one intake, for 24 hours, once.
// And the same rule: the TOKEN decides which intake a request reads, never an
// id supplied beside it — the id in the URL is checked against it, and a
// mismatch is the same 404 as an id that does not exist.
//
// Everything here is pure or takes a database, never Next, so the database test
// drives the handlers end to end exactly as the routes do.

import { randomBytes } from "node:crypto";

import { APP_ID, type Parsed } from "./apps";
import { appendAuditEvent } from "./auditLog";
import { getPool, withTransaction } from "./db";
import { bearerToken, hashToken } from "./ingestTokens";
import { ISOLATION_VALUES, type Isolation } from "./isolation";
import { portalSpan } from "./tracing";

// Mirrors of the Python sets that own them — runtime/cli.py STACKS and
// scripts/gate_ides.py GENERATED — pinned by test/catalogs.test.ts, which reads
// both files and compares. The CLI re-checks every value against its own copy.
export const INTAKE_STACKS = ["python-fastapi", "ts-react", "go"] as const;
export const INTAKE_IDES = ["claude", "cursor"] as const;
export type IntakeStack = (typeof INTAKE_STACKS)[number];
export type IntakeIde = (typeof INTAKE_IDES)[number];

export const INTAKE_LIMITS = {
  objective: 4000,
  criteria: 20,
  files: 50,
  item: 500,
  ttlHours: 24,
} as const;

// A structural style's shape only: which styles exist is templates/architectures.yaml's
// business, checked by the CLI, and a copy here would be a third catalogue.
export const ARCHITECTURE = /^[a-z][a-z-]{0,39}$/;
// Newline and tab are the only control characters a paragraph needs; the rest
// have no business in a Markdown file an agent will read.
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g;

export interface IntakeRfc {
  objective: string;
  acceptance_criteria: string[];
  files_to_modify: string[];
}

export interface IntakeInput {
  tenant_id: string;
  stack: IntakeStack;
  isolation: Isolation;
  architecture: string | null;
  agentic: boolean;
  ides: IntakeIde[];
  rfc: IntakeRfc;
}

/** contract/intake/v1/record.schema.json — what the CLI receives. */
export interface IntakeRecord extends IntakeInput {
  schema_version: 1;
  intake_id: string;
  expires_at: string;
}

function text(value: unknown, max: number): string | null {
  if (typeof value !== "string") return null;
  const cleaned = value.replace(CONTROL, "").trim();
  return cleaned.length >= 1 && cleaned.length <= max ? cleaned : null;
}

function lines(value: unknown, min: number, max: number): string[] | null {
  if (value === undefined || value === null) return min === 0 ? [] : null;
  if (!Array.isArray(value) || value.length < min || value.length > max) return null;
  const out = value.map((v) => text(v, INTAKE_LIMITS.item));
  return out.every((v): v is string => v !== null) ? out : null;
}

/** An author's intake, or why not. Pure, so the test runs what the route runs. */
export function parseIntakeInput(body: unknown): Parsed<IntakeInput> {
  if (typeof body !== "object" || body === null) return { ok: false, error: "the body must be a JSON object" };
  const b = body as Record<string, unknown>;

  const tenantId = typeof b.tenant_id === "string" ? b.tenant_id.trim() : "";
  if (!APP_ID.test(tenantId)) {
    return {
      ok: false,
      error: "tenant_id must be lower-case letters, digits and dashes, 1–63 characters, not starting or ending with a dash — the rule a portal app id follows, so the tenant can register",
    };
  }
  if (!(INTAKE_STACKS as readonly unknown[]).includes(b.stack)) {
    return { ok: false, error: `stack must be one of ${INTAKE_STACKS.join(", ")}` };
  }
  const isolation = b.isolation ?? "shared";
  if (!(ISOLATION_VALUES as readonly unknown[]).includes(isolation)) {
    return { ok: false, error: `isolation must be one of ${ISOLATION_VALUES.join(", ")}` };
  }
  const architecture = b.architecture === undefined || b.architecture === null || b.architecture === "" ? null : b.architecture;
  if (architecture !== null && (typeof architecture !== "string" || !ARCHITECTURE.test(architecture))) {
    return { ok: false, error: "architecture must be a style name such as hexagonal or layered, or omitted" };
  }
  if (b.agentic !== undefined && typeof b.agentic !== "boolean") return { ok: false, error: "agentic must be true or false" };
  const ides = b.ides ?? [];
  if (
    !Array.isArray(ides) ||
    !ides.every((i) => (INTAKE_IDES as readonly unknown[]).includes(i)) ||
    new Set(ides).size !== ides.length
  ) {
    return {
      ok: false,
      error: `ides must list IDEs with a verified config schema, each once: ${INTAKE_IDES.join(", ")} — or be empty for all of them`,
    };
  }

  if (typeof b.rfc !== "object" || b.rfc === null) return { ok: false, error: "rfc is required: objective and acceptance_criteria" };
  const r = b.rfc as Record<string, unknown>;
  const objective = text(r.objective, INTAKE_LIMITS.objective);
  if (objective === null) return { ok: false, error: `rfc.objective must be 1–${INTAKE_LIMITS.objective} characters` };
  const criteria = lines(r.acceptance_criteria, 1, INTAKE_LIMITS.criteria);
  if (criteria === null) {
    return { ok: false, error: `rfc.acceptance_criteria must be 1–${INTAKE_LIMITS.criteria} items of 1–${INTAKE_LIMITS.item} characters` };
  }
  const files = lines(r.files_to_modify, 0, INTAKE_LIMITS.files);
  if (files === null) {
    return { ok: false, error: `rfc.files_to_modify must be at most ${INTAKE_LIMITS.files} items of 1–${INTAKE_LIMITS.item} characters` };
  }

  return {
    ok: true,
    value: {
      tenant_id: tenantId,
      stack: b.stack as IntakeStack,
      isolation: isolation as Isolation,
      architecture: architecture as string | null,
      agentic: b.agentic === true,
      ides: ides as IntakeIde[],
      rfc: { objective, acceptance_criteria: criteria, files_to_modify: files },
    },
  };
}

/** A new intake token and the hash that is all the portal keeps of it. */
export function newIntakeToken(): { token: string; hash: string } {
  const token = `asx_${randomBytes(32).toString("base64url")}`;
  return { token, hash: hashToken(token) };
}

export interface IssuedIntake {
  intake_id: string;
  token: string;
  expires_at: string;
}

/** Stores an intake and returns its token — the only time the token exists outside the caller. */
export async function createIntake(input: IntakeInput, actor: string): Promise<IssuedIntake> {
  const { token, hash } = newIntakeToken();
  return withTransaction("intake_create", async (client) => {
    const { rows } = await client.query(
      `INSERT INTO tenant_intakes (token_hash, tenant_id, stack, isolation, architecture, agentic, ides, rfc, created_by, expires_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now() + make_interval(hours => $10))
       RETURNING intake_id, expires_at`,
      [hash, input.tenant_id, input.stack, input.isolation, input.architecture, input.agentic,
        JSON.stringify(input.ides), JSON.stringify(input.rfc), actor, INTAKE_LIMITS.ttlHours],
    );
    const intakeId = String(rows[0].intake_id);
    // Issuing a credential is audited as ingest tokens are (lib/apps.ts
    // ingest_token_issued). tenantId is null: audit_log.tenant_id references
    // tenants, and this tenant is not registered yet.
    await appendAuditEvent(
      {
        eventType: "config_change",
        actorId: actor,
        tenantId: null,
        details: { action: "intake_issued", intake_id: intakeId, tenant_id: input.tenant_id },
      },
      client,
    );
    return { intake_id: intakeId, token, expires_at: new Date(rows[0].expires_at).toISOString() };
  });
}

interface IntakeRow {
  intake_id: string | number;
  tenant_id: string;
  stack: IntakeStack;
  isolation: Isolation;
  architecture: string | null;
  agentic: boolean;
  ides: IntakeIde[];
  rfc: IntakeRfc;
  created_by: string;
  expires_at: Date | string;
  consumed_at: Date | string | null;
  /** Judged by Postgres, never by this process's clock: the consume UPDATE
   *  compares against the database's now(), so the read must too, or clock
   *  skew lets an intake read as live and then fail to consume. */
  expired: boolean;
}

function toRecord(row: IntakeRow): IntakeRecord {
  return {
    schema_version: 1,
    intake_id: String(row.intake_id),
    tenant_id: row.tenant_id,
    stack: row.stack,
    isolation: row.isolation,
    architecture: row.architecture,
    agentic: row.agentic,
    ides: row.ides,
    rfc: row.rfc,
    expires_at: new Date(row.expires_at).toISOString(),
  };
}

export interface ScaffoldResult {
  status: number;
  body: Record<string, unknown>;
}

const iso = (value: Date | string) => new Date(value).toISOString();

/**
 * Why `row` cannot be used, or null if it can. `denied-vs-missing`: a used
 * intake and an expired one are different answers, because the fix differs —
 * one needs nothing, the other needs a new intake.
 */
function unusable(row: IntakeRow): ScaffoldResult | null {
  if (row.consumed_at !== null) {
    return {
      status: 410,
      body: { error: `intake ${row.intake_id} was already used at ${iso(row.consumed_at)} — a tenant was scaffolded from it`, reason: "consumed" },
    };
  }
  if (row.expired) {
    return {
      status: 410,
      body: { error: `intake ${row.intake_id} expired at ${iso(row.expires_at)} — ask for a new intake in the portal`, reason: "expired" },
    };
  }
  return null;
}

/** The token's intake, or the answer to give instead. */
async function resolve(authorization: string | null, id: string): Promise<{ row: IntakeRow } | ScaffoldResult> {
  const token = bearerToken(authorization);
  if (!token) return { status: 401, body: { error: "Authorization: Bearer <intake token> is required" } };
  const { rows } = await getPool().query(`SELECT *, expires_at <= now() AS expired FROM tenant_intakes WHERE token_hash = $1`, [hashToken(token)]);
  const row = rows[0] as IntakeRow | undefined;
  if (!row) return { status: 401, body: { error: "unknown intake token" } };
  // The token decided; the id only has to agree with it.
  if (String(row.intake_id) !== id) return { status: 404, body: { error: `no intake ${id} for this token` } };
  return { row };
}

/** GET /api/dev/scaffold/:id — the record, repeatable until consumed or expired. */
export async function handleScaffoldRead(authorization: string | null, id: string): Promise<ScaffoldResult> {
  return portalSpan("portal.dev.scaffold.read", { attributes: { "intake.id": id } }, async () => {
    const found = await resolve(authorization, id);
    if (!("row" in found)) return found;
    return unusable(found.row) ?? { status: 200, body: toRecord(found.row) as unknown as Record<string, unknown> };
  });
}

/**
 * POST /api/dev/scaffold/:id/consume — marks the intake used, once. Called by
 * the CLI only after the scaffold is written, so a scaffold that fails half-way
 * leaves the intake usable and the retry is the same command.
 */
export async function handleScaffoldConsume(authorization: string | null, id: string): Promise<ScaffoldResult> {
  return portalSpan("portal.dev.scaffold.consume", { attributes: { "intake.id": id } }, async () => {
    const found = await resolve(authorization, id);
    if (!("row" in found)) return found;

    return withTransaction("intake_consume", async (client) => {
      // The UPDATE's own conditions are the ONLY gate — no check on the row
      // read above, which could be stale by now. So two consumes racing each
      // other cannot both succeed, and a test of "used once" cannot pass on a
      // pre-check while the guard that matters under concurrency is missing.
      const { rows } = await client.query(
        `UPDATE tenant_intakes SET consumed_at = now()
          WHERE intake_id = $1 AND consumed_at IS NULL AND expires_at > now()
          RETURNING *`,
        [found.row.intake_id],
      );
      const row = rows[0] as IntakeRow | undefined;
      if (!row) {
        const { rows: now } = await client.query(
          `SELECT *, expires_at <= now() AS expired FROM tenant_intakes WHERE intake_id = $1`,
          [found.row.intake_id],
        );
        // The UPDATE refused, so by the same clock the row is used or expired;
        // the 409 is what a row that is neither would get, which the UPDATE's
        // conditions make unreachable.
        return unusable(now[0] as IntakeRow) ?? { status: 409, body: { error: "the intake changed while it was being consumed — retry" } };
      }
      // The actor is the author the token was issued to; the audit says the
      // token, not a login, is what authenticated this.
      await appendAuditEvent(
        {
          eventType: "tenant_created",
          actorId: row.created_by,
          tenantId: null,
          details: { action: "intake_consumed", intake_id: String(row.intake_id), tenant_id: row.tenant_id, authenticated_by: "intake_token" },
        },
        client,
      );
      return { status: 200, body: { intake_id: String(row.intake_id), consumed_at: iso(row.consumed_at!) } };
    });
  });
}
