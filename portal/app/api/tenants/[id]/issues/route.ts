import { NextResponse } from "next/server";
import { getUnresolvedIssues } from "@/lib/issues";
import { canAccessTenant } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { withIdentity } from "@/lib/tracing";

// No span of its own: this route authorises and delegates, and a span named
// after it would only wrap Next's own request span with a second copy of the
// same interval. Identity IS bound, so the query spans underneath carry the
// tenant they read.

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const access = currentAccess();
  if (!canAccessTenant(access, params.id)) {
    return NextResponse.json({ error: `forbidden: no access to tenant ${params.id}` }, { status: 403 });
  }

  try {
    const issues = await withIdentity({ tenantId: params.id, actorRole: access.role }, () =>
      getUnresolvedIssues(params.id),
    );
    // `issues` stays an ARRAY — a consumer reading issues[0] or issues.length
    // keeps working — and `total`/`limit` are added beside it. The list is
    // capped at `limit`, so `issues.length` was never the number of unresolved
    // issues and a caller had no way to know that.
    return NextResponse.json({ issues: issues.entries, total: issues.total, limit: issues.limit });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
