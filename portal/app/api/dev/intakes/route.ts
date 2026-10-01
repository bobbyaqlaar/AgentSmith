// POST /api/dev/intakes — an author's answers for a new tenant, stored for
// `agentsmith tenant init --from <id>` to pull (.agent-rfc/designs/portal-intake-pull.md).
// Human, behind middleware.ts. Needs dev.create — held by Developers and up —
// asked app-less, because the tenant is not an app yet; an id that is already a
// registered app, or that an open intake names, is refused with 409
// (.agent-rfc/designs/intake-dev-create.md). The token is in this response and
// nowhere else, ever.

import { NextResponse } from "next/server";

import { roleFor } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { createIntake, IntakeTakenError, parseIntakeInput } from "@/lib/intakes";

export async function POST(request: Request) {
  const access = currentAccess();
  const role = roleFor(access, "dev.create");
  if (!role) {
    return NextResponse.json({ error: "creating a tenant intake needs the Developer role or above" }, { status: 403 });
  }
  const parsed = parseIntakeInput(await request.json().catch(() => null));
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });

  let issued;
  try {
    issued = await createIntake(parsed.value, access.actor ?? "unknown", role);
  } catch (err) {
    if (err instanceof IntakeTakenError) return NextResponse.json({ error: err.message }, { status: 409 });
    throw err;
  }
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
