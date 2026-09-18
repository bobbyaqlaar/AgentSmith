// portal/lib/devIngestHandler.ts — POST /api/dev/ingest without Next
// (portal phase 1, S3). The route adapts this; the database test drives it end
// to end — token, size, JSON, validation, storage — with nothing mocked.

import { DEV_LIMITS, parseDevIngest } from "./devIngest";
import { storeDevIngest } from "./devStore";
import { bearerToken, resolveIngestToken } from "./ingestTokens";
import { portalSpan, withIdentity } from "./tracing";

export interface IngestResult {
  status: number;
  body: Record<string, unknown>;
}

export async function handleDevIngest(authorization: string | null, bodyText: string): Promise<IngestResult> {
  const token = bearerToken(authorization);
  if (!token) return { status: 401, body: { error: "Authorization: Bearer <app ingest token> is required" } };
  // The app is the token's, never an id in the body: a token for one app
  // cannot write another's commits.
  const tenantId = await resolveIngestToken(token);
  if (!tenantId) return { status: 401, body: { error: "unknown or revoked ingest token" } };

  if (Buffer.byteLength(bodyText, "utf8") > DEV_LIMITS.bodyBytes) {
    return { status: 413, body: { error: `the body is larger than ${DEV_LIMITS.bodyBytes} bytes — send the range in parts` } };
  }
  let body: unknown;
  try {
    body = JSON.parse(bodyText);
  } catch {
    return { status: 400, body: { error: "the body is not JSON" } };
  }
  const parsed = parseDevIngest(body);
  if (!parsed.ok) return { status: 400, body: { error: parsed.error } };

  const stored = await withIdentity({ tenantId }, () =>
    portalSpan("portal.dev.ingest", { attributes: { "dev.commits": parsed.value.commits.length } }, () =>
      storeDevIngest(tenantId, parsed.value),
    ),
  );
  return { status: 200, body: { app: tenantId, stored } };
}
