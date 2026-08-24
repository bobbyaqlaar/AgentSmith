// portal/lib/phoenix.ts — thin client for the per-tenant Arize Phoenix
// instance referenced by tenants.phoenix_base_url (SPECS.md §15, §26).
//
// GraphQL query shapes below (projects / Project.traceCount /
// Project.traceCountByStatusTimeSeries) were validated directly against a
// live Phoenix instance's schema, not guessed at.
//
// Every outbound call here is traced. These are the portal's slowest hop by a
// wide margin — a tenant Phoenix that is merely unreachable costs the 3s or 5s
// its AbortSignal allows, on a page render — and until now the only evidence
// that had happened was a card rendering "unknown" with no explanation
// anywhere. `server.address` is the host, not the full URL: enough to tell two
// tenants' instances apart without putting a path on a span.

import { SpanKind, portalSpan } from "./tracing";

/** The host of a configured base URL, or "invalid" — never the raw string,
 *  which may carry a path or credentials. */
function hostOf(baseUrl: string): string {
  try {
    return new URL(baseUrl).host;
  } catch {
    return "invalid";
  }
}

export function tenantTraceUrl(phoenixBaseUrl: string, opts: { environment?: string } = {}): string {
  const params = new URLSearchParams();
  if (opts.environment) params.set("filter", `environment = "${opts.environment}"`);
  const qs = params.toString();
  return `${phoenixBaseUrl.replace(/\/$/, "")}/projects${qs ? `?${qs}` : ""}`;
}

export async function checkPhoenixHealth(phoenixBaseUrl: string): Promise<boolean> {
  return portalSpan(
    "portal.phoenix.health",
    { kind: SpanKind.CLIENT, attributes: { "server.address": hostOf(phoenixBaseUrl) } },
    async (span) => {
      try {
        const resp = await fetch(`${phoenixBaseUrl.replace(/\/$/, "")}/healthz`, {
          signal: AbortSignal.timeout(3000),
        });
        span.setAttribute("http.response.status_code", resp.status);
        return resp.ok;
      } catch (err) {
        // The catch stays: an unreachable Phoenix is a degraded card, not a
        // failed page. But the span now says WHICH — a timeout and a refused
        // connection both used to render as the same silent `false`.
        span.setAttribute("error.type", err instanceof Error ? err.name : typeof err);
        return false;
      }
    },
  );
}

export interface RecentTraceStats {
  traceCount: number;
  errorCount: number;
  errorRate: number | null;
}

async function graphqlQuery<T>(
  phoenixBaseUrl: string,
  query: string,
  variables: Record<string, unknown>,
  operation: string,
): Promise<T> {
  return portalSpan(
    "portal.phoenix.graphql",
    {
      kind: SpanKind.CLIENT,
      // The operation NAME, not the query text and never the variables — a
      // closed set of two, which keeps the attribute groupable.
      attributes: { "server.address": hostOf(phoenixBaseUrl), "graphql.operation.name": operation },
    },
    async (span) => {
      const resp = await fetch(`${phoenixBaseUrl.replace(/\/$/, "")}/graphql`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query, variables }),
        signal: AbortSignal.timeout(5000),
      });
      span.setAttribute("http.response.status_code", resp.status);
      if (!resp.ok) throw new Error(`Phoenix GraphQL HTTP ${resp.status}`);
      const json = await resp.json();
      if (json.errors?.length) throw new Error(json.errors[0]?.message ?? "Phoenix GraphQL error");
      return json.data as T;
    },
  );
}

const PROJECTS_QUERY = `{ projects { edges { node { id } } } }`;

const TRACE_STATS_QUERY = `
  query($id: ID!, $timeRange: TimeRange!, $timeBinConfig: TimeBinConfig!) {
    node(id: $id) {
      ... on Project {
        traceCountByStatusTimeSeries(timeRange: $timeRange, timeBinConfig: $timeBinConfig) {
          data { okCount errorCount totalCount }
        }
      }
    }
  }
`;

/**
 * Fetches trace count + error rate for a tenant's Phoenix instance over the
 * last `sinceHours`. Returns null on any failure (unreachable instance, no
 * default project, schema mismatch) so a tenant's Phoenix being down never
 * breaks the portal page rendering it — same degrade posture as
 * checkPhoenixHealth.
 */
export async function getRecentTraceStats(
  phoenixBaseUrl: string,
  opts: { sinceHours?: number } = {},
): Promise<RecentTraceStats | null> {
  const sinceHours = opts.sinceHours ?? 24;
  try {
    const projects = await graphqlQuery<{ projects: { edges: Array<{ node: { id: string } }> } }>(
      phoenixBaseUrl,
      PROJECTS_QUERY,
      {},
      "projects",
    );
    const projectId = projects.projects.edges[0]?.node.id;
    if (!projectId) return null;

    const end = new Date();
    const start = new Date(end.getTime() - sinceHours * 60 * 60 * 1000);
    const data = await graphqlQuery<{
      node: { traceCountByStatusTimeSeries: { data: Array<{ okCount: number; errorCount: number; totalCount: number }> } } | null;
    }>(
      phoenixBaseUrl,
      TRACE_STATS_QUERY,
      {
        id: projectId,
        timeRange: { start: start.toISOString(), end: end.toISOString() },
        timeBinConfig: { scale: "HOUR" },
      },
      "traceCountByStatus",
    );

    const points = data.node?.traceCountByStatusTimeSeries.data ?? [];
    const traceCount = points.reduce((sum, p) => sum + p.totalCount, 0);
    const errorCount = points.reduce((sum, p) => sum + p.errorCount, 0);
    return {
      traceCount,
      errorCount,
      errorRate: traceCount > 0 ? errorCount / traceCount : null,
    };
  } catch {
    return null;
  }
}
