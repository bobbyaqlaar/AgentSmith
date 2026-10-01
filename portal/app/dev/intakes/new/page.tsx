// Start a tenant (Dev workspace; .agent-rfc/designs/intake-form.md). The page
// is a server component: it decides who may see the form, and the form only
// collects — POST /api/dev/intakes validates, and refuses again whatever the
// page decided.

import { IntakeForm } from "@/components/IntakeForm";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export default function NewIntakePage() {
  if (!can(currentAccess(), "dev.create")) {
    // Denied, not missing: a different screen from "no such page", because it
    // points at a different next step.
    return (
      <div className="space-y-2">
        <h2 className="text-xl font-medium">You cannot start a tenant</h2>
        <p className="text-black/60 dark:text-white/60">
          Starting a tenant needs the Developer role or above. An Administrator can grant it.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-medium">Start a tenant</h2>
        <p className="text-black/60 dark:text-white/60 max-w-xl">
          Describe the tenant and its first change. The portal keeps your answers; you then create the
          repository on your own machine with one command, and its first commit is made there.
        </p>
      </div>
      <IntakeForm />
    </div>
  );
}
