// `/` — the first area this user may enter. Each area has its own home; the
// root has no page of its own beyond saying so when there is none.

import { redirect } from "next/navigation";

import { currentAccess } from "@/lib/currentAccess";
import { WORKSPACES, workspacesFor } from "@/lib/workspaces";

export const dynamic = "force-dynamic";

export default function Home() {
  const [first] = workspacesFor(currentAccess());
  if (first) redirect(WORKSPACES[first].home);
  return (
    <div className="space-y-2">
      <h2 className="text-xl font-medium">Your account has no access yet</h2>
      <p className="text-black/60 dark:text-white/60">
        You are signed in, but hold no role in any workspace. An Administrator can grant one.
      </p>
    </div>
  );
}
