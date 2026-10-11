// portal/lib/opsIngest.ts — POST /api/ops/ingest without Next (contract/ops/v1).
//
// What a running app tells its portal: a run's status, a dead letter for the
// HITL queue, and its declared settings. The app is its Ops token's — never an
// id in the body, which names no tenant. Every body is validated whole on the
// way in and refused whole on the first field that fails; keys this receiver
// does not read are dropped. The route adapts this; tests drive it directly.

import { insertDeadLetter, type DeadLetterInput } from "./dlq";
import { bearerToken, resolveIngestToken } from "./ingestTokens";
import { AGENT_RUN_STATUSES, type AgentRunStatus, upsertAgentRun } from "./runStatus";
import { isSafeHttpUrl } from "./safeUrl";
import { updateTenantSettings } from "./tenants";
import { portalSpan, withIdentity } from "./tracing";

export const OPS_LIMITS = { bodyBytes: 1_000_000, text: 4000, id: 200, version: 64, url: 2000, reason: 64 } as const;

export interface RunInput {
  kind: "run";
  runId: string;
  status: AgentRunStatus;
  workflowId: string | null;
  traceId: string | null;
  errorSummary: string | null;
  inputTokens: number | null;
  outputTokens: number | null;
  costUsd: number | null;
  frameworkVersion: string | null;
}

export interface SettingsInput {
  kind: "settings";
  budgetCapUsd: number | null;
  replayWebhookUrl: string | null;
}

export type OpsMessage = RunInput | (DeadLetterInput & { kind: "dead_letter" }) | SettingsInput;
type Parsed = { ok: true; value: OpsMessage } | { ok: false; error: string };

class Refused extends Error {}

function text(body: Record<string, unknown>, key: string, max: number, required = false): string | null {
  const value = body[key];
  if (value === undefined || value === null) {
    if (required) throw new Refused(`${key} is required`);
    return null;
  }
  if (typeof value !== "string" || value.length === 0) throw new Refused(`${key} must be a non-empty string`);
  if (value.length > max) throw new Refused(`${key} is longer than ${max} characters`);
  return value;
}

function count(body: Record<string, unknown>, key: string, integer: boolean): number | null {
  const value = body[key];
  if (value === undefined || value === null) return null;
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || (integer && !Number.isInteger(value))) {
    throw new Refused(`${key} must be a non-negative ${integer ? "integer" : "number"}`);
  }
  return value;
}

/** One message, validated whole. Pure: no database, no Next. */
export function parseOpsMessage(raw: unknown): Parsed {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return { ok: false, error: "the body is not an object" };
  const body = raw as Record<string, unknown>;
  try {
    if (body.schema !== 1) throw new Refused("schema must be 1");
    switch (body.kind) {
      case "run": {
        const status = body.status;
        if (typeof status !== "string" || !(AGENT_RUN_STATUSES as readonly string[]).includes(status)) {
          throw new Refused(`status must be one of: ${AGENT_RUN_STATUSES.join(", ")}`);
        }
        const traceId = text(body, "trace_id", 32);
        if (traceId !== null && (!/^[0-9a-f]{32}$/.test(traceId) || /^0+$/.test(traceId))) {
          throw new Refused("trace_id must be 32 lowercase hex characters, not all zero");
        }
        return {
          ok: true,
          value: {
            kind: "run",
            runId: text(body, "run_id", OPS_LIMITS.id, true) as string,
            status: status as AgentRunStatus,
            workflowId: text(body, "workflow_id", OPS_LIMITS.id),
            traceId,
            errorSummary: text(body, "error_summary", OPS_LIMITS.text),
            inputTokens: count(body, "input_tokens", true),
            outputTokens: count(body, "output_tokens", true),
            costUsd: count(body, "cost_usd", false),
            frameworkVersion: text(body, "framework_version", OPS_LIMITS.version),
          },
        };
      }
      case "dead_letter": {
        if (!("payload" in body)) throw new Refused("payload is required");
        return {
          ok: true,
          value: {
            kind: "dead_letter",
            taskId: text(body, "task_id", OPS_LIMITS.id, true) as string,
            error: text(body, "error", OPS_LIMITS.text, true) as string,
            payload: body.payload,
            reason: text(body, "reason", OPS_LIMITS.reason),
            workflowId: text(body, "workflow_id", OPS_LIMITS.id),
            gateId: text(body, "gate_id", OPS_LIMITS.id),
          },
        };
      }
      case "settings": {
        const url = text(body, "replay_webhook_url", OPS_LIMITS.url);
        // https only: the portal POSTs a human's fix there, signed.
        if (url !== null && (!url.startsWith("https://") || !isSafeHttpUrl(url))) {
          throw new Refused("replay_webhook_url must be an https URL");
        }
        if ("replay_webhook_secret" in body) {
          throw new Refused("a settings message carries no secret — the replay key is issued by the portal");
        }
        return { ok: true, value: { kind: "settings", budgetCapUsd: count(body, "budget_cap_usd", false), replayWebhookUrl: url } };
      }
      default:
        throw new Refused("kind must be one of: run, dead_letter, settings");
    }
  } catch (err) {
    if (err instanceof Refused) return { ok: false, error: err.message };
    throw err;
  }
}

export interface OpsResult {
  status: number;
  body: Record<string, unknown>;
}

async function store(tenantId: string, message: OpsMessage): Promise<OpsResult> {
  switch (message.kind) {
    case "run": {
      const { kind: _kind, ...run } = message;
      const stored = await upsertAgentRun({ tenantId, ...run });
      return stored
        ? { status: 200, body: { stored: 1 } }
        : { status: 409, body: { error: "run_id is another application's" } };
    }
    case "dead_letter": {
      const { kind: _kind, ...entry } = message;
      const outcome = await insertDeadLetter(tenantId, entry);
      if (outcome === "foreign") return { status: 409, body: { error: "task_id is another application's" } };
      return { status: 200, body: { stored: outcome === "stored" ? 1 : 0 } };
    }
    case "settings":
      await updateTenantSettings(tenantId, { budgetCapUsd: message.budgetCapUsd, replayWebhookUrl: message.replayWebhookUrl });
      return { status: 200, body: { stored: 1 } };
  }
}

export async function handleOpsIngest(authorization: string | null, bodyText: string): Promise<OpsResult> {
  const token = bearerToken(authorization);
  if (!token) return { status: 401, body: { error: "Authorization: Bearer <app Ops token> is required" } };
  // The app is the token's: a token for one app cannot write another's records,
  // and a CI (dev) token is not an Ops token.
  const tenantId = await resolveIngestToken(token, "ops");
  if (!tenantId) return { status: 401, body: { error: "unknown or revoked Ops token" } };

  if (Buffer.byteLength(bodyText, "utf8") > OPS_LIMITS.bodyBytes) {
    return { status: 413, body: { error: `the body is larger than ${OPS_LIMITS.bodyBytes} bytes` } };
  }
  let raw: unknown;
  try {
    raw = JSON.parse(bodyText);
  } catch {
    return { status: 400, body: { error: "the body is not JSON" } };
  }
  const parsed = parseOpsMessage(raw);
  if (!parsed.ok) return { status: 400, body: { error: parsed.error } };

  return withIdentity({ tenantId }, () =>
    portalSpan("portal.ops.ingest", { attributes: { "ops.kind": parsed.value.kind } }, () => store(tenantId, parsed.value)),
  );
}
