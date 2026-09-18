// /admin/apps/<id> — edit an app, and issue, rotate or revoke its ingest token
// (Administration › Apps; portal phase 1).

import { AppForm } from "@/components/AppForm";
import { Crumbs } from "@/components/DevBits";
import { IngestTokenPanel } from "@/components/IngestTokenPanel";
import { Timestamp } from "@/components/ui/Timestamp";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { ingestTokenStatus } from "@/lib/ingestTokens";
import { isSafeHttpUrl } from "@/lib/safeUrl";
import { getTenant } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function AdminAppPage({ params }: { params: { id: string } }) {
  const app = await getTenant(params.id);
  if (!app) {
    return (
      <div className="space-y-2">
        <Crumbs items={[{ href: "/admin/apps", text: "Apps" }, { text: params.id }]} />
        <h2 className="text-xl font-medium">No app called {params.id}</h2>
      </div>
    );
  }
  if (!can(currentAccess(), "admin.apps", app.tenantId)) {
    return (
      <div className="space-y-2">
        <Crumbs items={[{ href: "/admin/apps", text: "Apps" }, { text: params.id }]} />
        <h2 className="text-xl font-medium">You do not have access to {app.tenantId}</h2>
      </div>
    );
  }
  const [token] = await ingestTokenStatus([app.tenantId]);
  const secretsUrl =
    app.repoProvider === "github" && app.repoUrl && isSafeHttpUrl(app.repoUrl)
      ? `${app.repoUrl.replace(/\/+$/, "").replace(/\.git$/, "")}/settings/secrets/actions`
      : null;

  return (
    <div className="space-y-8">
      <div>
        <Crumbs items={[{ href: "/admin/apps", text: "Apps" }, { text: app.name }]} />
        <h2 className="text-xl font-medium">{app.name}</h2>
        <p className="text-sm text-black/50 dark:text-white/50">{app.tenantId}</p>
      </div>

      <section className="space-y-3">
        <h3 className="font-medium">App</h3>
        <AppForm
          mode="update"
          initial={{
            id: app.tenantId,
            name: app.name,
            repoUrl: app.repoUrl ?? "",
            repoProvider: app.repoProvider ?? "github",
            defaultBranch: app.defaultBranch ?? "",
          }}
        />
      </section>

      <section className="space-y-3">
        <h3 className="font-medium">Ingest token</h3>
        <p className="text-sm text-black/60 dark:text-white/60">
          The app&apos;s CI sends its process gate&apos;s record to the Dev workspace with this token.{" "}
          {token.active > 0 ? (
            <>
              One is issued{token.issuedAt && <> — <Timestamp value={token.issuedAt} /></>}
              {token.issuedBy && ` by ${token.issuedBy}`}.
            </>
          ) : (
            "None is issued, so the app's CI cannot send."
          )}
        </p>
        {app.repoProvider === "gitlab" && (
          <p className="text-sm text-amber-700 dark:text-amber-400">
            GitLab CI does not send gate records yet — a token has nothing to carry until it does.
          </p>
        )}
        <IngestTokenPanel appId={app.tenantId} active={token.active > 0} repoSecretsUrl={secretsUrl} />
      </section>
    </div>
  );
}
