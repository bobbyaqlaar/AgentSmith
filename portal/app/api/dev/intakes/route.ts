// POST /api/dev/intakes — an author's answers for a new tenant, stored for
// `agentsmith tenant init --from <id>` to pull (.agent-rfc/designs/portal-intake-pull.md).
// Human, behind middleware.ts. Needs admin.apps over the tenant id — the same
// two-step check as registering an app, so a new id needs an org-wide grant.
// Slice 3 of the intake plan widens this to dev.create, deliberately and on its
// own review. The token is in this response and nowhere else, ever.

import { NextResponse } from "next/server";

import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { createIntake, parseIntakeInput } from "@/lib/intakes";

export async function POST(request: Request) {
  const access = currentAccess();
  if (!can(access, "admin.apps")) {
    return NextResponse.json({ error: "Administrator role required to create a tenant intake" }, { status: 403 });
  }
  const parsed = parseIntakeInput(await request.json().catch(() => null));
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });
  if (!can(access, "admin.apps", parsed.value.tenant_id)) {
    return NextResponse.json({ error: `forbidden: no access to app ${parsed.value.tenant_id}` }, { status: 403 });
  }

  const issued = await createIntake(parsed.value, access.actor ?? "unknown");
  return NextResponse.json(
    {
      ...issued,
      // The command carries no token: a token on a command line lands in shell
      // history and in `ps`. The CLI reads it from AGENTSMITH_INTAKE_TOKEN.
      command: `agentsmith tenant init --from ${issued.intake_id}`,
      note: "Store the token now — it is not shown again. It works once, for 24 hours, for this intake only.",
    },
    { status: 201, headers: { "Cache-Control": "no-store" } },
  );
}
