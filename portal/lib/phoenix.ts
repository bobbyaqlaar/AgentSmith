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

/**
 * One traced request to a tenant's Phoenix.
 *
 * Shared with lib/promotions.ts, which had its own copy: its own trailing-slash
 * strip, its own AbortSignal, and — the part that mattered — NO span, so the
 * shadow-eval read stayed invisible when this module was instrumented. Three
 * outbound calls, two of them traced, is the shape this repo keeps finding: a
 * fix applied at one call site and not its identical neighbour.
 */
export async function phoenixFetch(
  baseUrl: string,
  path: string,
  opts: {
    spanName: string;
    timeoutMs: number;
    init?: RequestInit;
    attributes?: Record<string, string | number | boolean>;
  },
): Promise<Response> {
  return portalSpan(
    opts.spanName,
    {
      kind: SpanKind.CLIENT,
      attributes: { "server.address": hostOf(baseUrl), ...(opts.attributes ?? {}) },
    },
    async (span) => {
      const resp = await fetch(`${baseUrl.replace(/\/+$/, "")}${path}`, {
        ...opts.init,
        signal: AbortSignal.timeout(opts.timeoutMs),
      });
      span.setAttribute("http.response.status_code", resp.status);
      return resp;
    },
  );
}

export function tenantTraceUrl(phoenixBaseUrl: string, opts: { environment?: string } = {}): string {
  const params = new URLSearchParams();
  if (opts.environment) params.set("filter", `environment = "${opts.environment}"`);
  const qs = params.toString();
  return `${phoenixBaseUrl.replace(/\/$/, "")}/projects${qs ? `?${qs}` : ""}`;
}

export async function checkPhoenixHealth(phoenixBaseUrl: string): Promise<boolean> {
  try {
    const resp = await phoenixFetch(phoenixBaseUrl, "/healthz", {
      spanName: "portal.phoenix.health",
      timeoutMs: 3000,
    });
    return resp.ok;
  } catch {
    // An unreachable Phoenix is a degraded card, not a failed page. The span
    // opened above still records the failure and its type — a timeout and a
    // refused connection both used to render as the same silent `false` with
    // nothing anywhere to tell them apart.
    return false;
  }
}

export interface RecentTraceStats {
  traceCount: number;
  errorCount: number;
  errorRate: number | null;
  /** WHICH project these numbers came from. The query takes the first project
   *  the instance reports, which is fine for the single-project default and a
   *  silent misattribution otherwise — the page presented the figure as the
   *  tenant's without ever naming its source. */
  projectName: string;
  /** How many projects the instance has. > 1 means the number above covers
   *  one of several, which the page says out loud. */
  projectCount: number;
}

async function graphqlQuery<T>(
  phoenixBaseUrl: string,
  query: string,
  variables: Record<string, unknown>,
  operation: string,
): Promise<T> {
  const resp = await phoenixFetch(phoenixBaseUrl, "/graphql", {
    spanName: "portal.phoenix.graphql",
    timeoutMs: 5000,
    // The operation NAME, not the query text and never the variables — a
    // closed set of two, which keeps the attribute groupable.
    attributes: { "graphql.operation.name": operation },
    init: {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, variables }),
    },
  });
  if (!resp.ok) throw new Error(`Phoenix GraphQL HTTP ${resp.status}`);
  const json = await resp.json();
  if (json.errors?.length) throw new Error(json.errors[0]?.message ?? "Phoenix GraphQL error");
  return json.data as T;
}

// `name` alongside `id` — validated against a live Phoenix instance, like the
// rest of the shapes in this file, not guessed at.
const PROJECTS_QUERY = `{ projects { edges { node { id name } } } }`;

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
    const projects = await graphqlQuery<{
      projects: { edges: Array<{ node: { id: string; name: string } }> };
    }>(phoenixBaseUrl, PROJECTS_QUERY, {}, "projects");
    const edges = projects.projects.edges;
    const project = edges[0]?.node;
    if (!project) return null;

    const end = new Date();
    const start = new Date(end.getTime() - sinceHours * 60 * 60 * 1000);
    const data = await graphqlQuery<{
      node: { traceCountByStatusTimeSeries: { data: Array<{ okCount: number; errorCount: number; totalCount: number }> } } | null;
    }>(
      phoenixBaseUrl,
      TRACE_STATS_QUERY,
      {
        id: project.id,
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
      projectName: project.name,
      projectCount: edges.length,
    };
  } catch {
    return null;
  }
}
