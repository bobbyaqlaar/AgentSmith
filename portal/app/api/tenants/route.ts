import { NextResponse } from "next/server";
import { listTenants, upsertTenant } from "@/lib/tenants";
import { getAllTenantsCurrentSpend } from "@/lib/cost";
import { getUnresolvedCountByTenant } from "@/lib/issues";
import { getDLQStatus } from "@/lib/dlq";
import { canAccessTenant, canWrite, filterTenantIds } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { ISOLATION_VALUES, isValidIsolation } from "@/lib/isolation";
import { isSafeHttpUrl } from "@/lib/safeUrl";

export async function GET() {
  const access = currentAccess();

  try {
    const [tenants, spend, issues, dlq] = await Promise.all([
      listTenants(),
      getAllTenantsCurrentSpend(),
      getUnresolvedCountByTenant(),
      getDLQStatus(),
    ]);

    const visibleIds = new Set(filterTenantIds(access, tenants.map((t) => t.tenantId)));

    const data = tenants
      .filter((t) => visibleIds.has(t.tenantId))
      .map((t) => ({
        ...t,
        // null, not 0, when the gateway's budget table does not exist — the
        // same distinction dlqPending draws one line below.
        currentSpendUsd: spend.wired ? spend.byTenant[t.tenantId] ?? 0 : null,
        unresolvedIssues: issues[t.tenantId] ?? 0,
        dlqPending: dlq.wired ? dlq.pendingByTenant[t.tenantId] ?? 0 : null,
      }));

    return NextResponse.json({ tenants: data, dlqWired: dlq.wired, spendWired: spend.wired });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function POST(request: Request) {
  const access = currentAccess();
  if (!canWrite(access)) {
    return NextResponse.json({ error: "operator or admin role required" }, { status: 403 });
  }

  // `.catch(() => null)` like every other body-reading route — malformed JSON
  // is the caller's 400, not this route's 500. It was the one route without it.
  const body = await request.json().catch(() => null);
  if (!body?.tenantId || !body?.name) {
    return NextResponse.json({ error: "tenantId and name are required" }, { status: 400 });
  }

  // TENANT SCOPE. Every other mutating route checks this — both DLQ actions,
  // both widget-token actions — and this one checked only the role. Since
  // upsertTenant is an UPSERT, an operator scoped to one tenant could rewrite
  // ANOTHER tenant's row: its name, its isolation, its budget cap, and the
  // replay webhook URL and secret the portal signs outgoing payloads with.
  // A scoped operator can still edit its own tenants; creating a new one
  // requires the "*" scope, which is what an unscoped operator/admin has.
  if (!canAccessTenant(access, body.tenantId)) {
    return NextResponse.json(
      { error: `forbidden: no access to tenant ${body.tenantId}` },
      { status: 403 },
    );
  }

  if (body.isolation !== undefined && !isValidIsolation(body.isolation)) {
    return NextResponse.json({ error: `isolation must be one of: ${ISOLATION_VALUES.join(", ")}` }, { status: 400 });
  }
  // Both of these are FETCHED server-side by the portal, and phoenixBaseUrl is
  // also rendered as an <a href> on the tenant page — so an unvalidated value
  // is a `javascript:` link and a server-side request to any scheme at all.
  // See lib/safeUrl for why the check is the scheme and not the host.
  for (const field of ["phoenixBaseUrl", "replayWebhookUrl"] as const) {
    if (body[field] !== undefined && body[field] !== null && !isSafeHttpUrl(body[field])) {
      return NextResponse.json({ error: `${field} must be an http(s) URL` }, { status: 400 });
    }
  }

  if (body.budgetCapUsd !== undefined && body.budgetCapUsd !== null && typeof body.budgetCapUsd !== "number") {
    // Rejected rather than coerced or quietly dropped. A cap that arrives as
    // "50" and is silently discarded leaves the dashboard showing the previous
    // number, which is the shape of an ambiguous signal: the caller believes it
    // set a cap and the portal believes nothing changed.
    return NextResponse.json({ error: "budgetCapUsd must be a number" }, { status: 400 });
  }
  for (const field of ["tenantId", "name", "replayWebhookSecret"] as const) {
    if (body[field] !== undefined && body[field] !== null && typeof body[field] !== "string") {
      return NextResponse.json({ error: `${field} must be a string` }, { status: 400 });
    }
  }

  // Named fields, not the request body. `upsertTenant(body)` forwarded whatever
  // arrived — every column the helper knows how to write, set by anything the
  // caller chose to include. The field list is the same one portal/README.md
  // documents; the difference is that it is now a list.
  await upsertTenant({
    tenantId: body.tenantId,
    name: body.name,
    isolation: body.isolation,
    phoenixBaseUrl: body.phoenixBaseUrl,
    budgetCapUsd: body.budgetCapUsd ?? null,
    replayWebhookUrl: body.replayWebhookUrl ?? null,
    replayWebhookSecret: body.replayWebhookSecret ?? null,
  });
  return NextResponse.json({ ok: true });
}
