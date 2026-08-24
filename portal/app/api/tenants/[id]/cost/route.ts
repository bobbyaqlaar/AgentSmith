import { NextResponse } from "next/server";
import { getTenantCost } from "@/lib/cost";
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
    const cost = await withIdentity({ tenantId: params.id, actorRole: access.role }, () =>
      getTenantCost(params.id),
    );
    return NextResponse.json(cost);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
