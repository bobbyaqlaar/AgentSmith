// portal/lib/phoenix.ts — thin client for the per-tenant Arize Phoenix
// instance referenced by tenants.phoenix_base_url (SPECS.md §15, §26).
//
// Phoenix's primary query surface is GraphQL (not yet wired here — v1 scope
// is health + deep-linking). Trace/experiment aggregation is a documented
// follow-up once a tenant Phoenix instance is available to develop against.

export function tenantTraceUrl(phoenixBaseUrl: string, opts: { environment?: string } = {}): string {
  const params = new URLSearchParams();
  if (opts.environment) params.set("filter", `environment = "${opts.environment}"`);
  const qs = params.toString();
  return `${phoenixBaseUrl.replace(/\/$/, "")}/projects${qs ? `?${qs}` : ""}`;
}

export async function checkPhoenixHealth(phoenixBaseUrl: string): Promise<boolean> {
  try {
    const resp = await fetch(`${phoenixBaseUrl.replace(/\/$/, "")}/healthz`, {
      signal: AbortSignal.timeout(3000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}
