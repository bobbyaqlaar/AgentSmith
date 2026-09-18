// One app in the Dev workspace: its header, its tabs, and the access check
// every page under it relies on. "You may not see this app" and "there is no
// such app" are different screens (the specification's denied-vs-missing): they
// send the reader to opposite next steps.

import { Crumbs, Freshness } from "@/components/DevBits";
import { NavLinks } from "@/components/NavLinks";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { listIngestRuns } from "@/lib/devRead";
import { isSafeHttpUrl } from "@/lib/safeUrl";
import { getTenant } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function DevAppLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { app: string };
}) {
  const tenant = await getTenant(params.app);
  if (!tenant) {
    return (
      <div className="space-y-2">
        <Crumbs items={[{ href: "/dev", text: "Apps" }, { text: params.app }]} />
        <h2 className="text-xl font-medium">No app called {params.app}</h2>
        <p className="text-black/60 dark:text-white/60">Check the name, or pick one from the list of apps.</p>
      </div>
    );
  }
  if (!can(currentAccess(), "dev.read", tenant.tenantId)) {
    return (
      <div className="space-y-2">
        <Crumbs items={[{ href: "/dev", text: "Apps" }, { text: params.app }]} />
        <h2 className="text-xl font-medium">You do not have access to {tenant.tenantId}</h2>
        <p className="text-black/60 dark:text-white/60">
          Your roles do not include this app&apos;s Dev workspace. An Administrator can grant one.
        </p>
      </div>
    );
  }

  const [lastRun] = await listIngestRuns(tenant.tenantId, 1);
  const base = `/dev/apps/${tenant.tenantId}`;
  return (
    <div className="space-y-6">
      <div>
        <Crumbs items={[{ href: "/dev", text: "Apps" }, { text: tenant.name }]} />
        <h2 className="text-xl font-medium">{tenant.name}</h2>
        <div className="text-sm mt-1 flex flex-wrap gap-x-4 gap-y-1">
          {tenant.repoUrl && isSafeHttpUrl(tenant.repoUrl) ? (
            <a className="text-blue-700 dark:text-blue-400 hover:underline" href={tenant.repoUrl} rel="noreferrer" target="_blank">
              {tenant.repoUrl.replace(/^https?:\/\//, "")}
            </a>
          ) : (
            <span className="text-black/50 dark:text-white/50">No repository registered — commits cannot be linked</span>
          )}
          <Freshness lastReceived={lastRun?.receivedAt ?? null} provider={tenant.repoProvider} />
        </div>
      </div>
      <NavLinks
        label={`${tenant.name} sections`}
        variant="tabs"
        links={[
          { href: base, text: "Changes", exact: true },
          { href: `${base}/designs`, text: "Designs" },
          { href: `${base}/gates`, text: "Gates" },
        ]}
      />
      {children}
    </div>
  );
}
