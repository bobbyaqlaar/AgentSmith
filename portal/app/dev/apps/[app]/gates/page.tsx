// /dev/apps/<app>/gates — the commit gate's failures and whether each has been
// repaired, and the CI runs that sent them (portal phase 1). Each CI step's own
// latest result needs GitHub's API and arrives with the GitHub App in phase 2.

import Link from "next/link";

import { ShortSha } from "@/components/DevBits";
import { Badge } from "@/components/ui/Badge";
import { Timestamp } from "@/components/ui/Timestamp";
import { listGateFailures, listIngestRuns } from "@/lib/devRead";
import { commitUrl } from "@/lib/devView";
import { isSafeHttpUrl } from "@/lib/safeUrl";
import { getTenant } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function DevGatesPage({ params }: { params: { app: string } }) {
  const tenant = await getTenant(params.app);
  if (!tenant) return null;
  const [failures, runs] = await Promise.all([listGateFailures(tenant.tenantId), listIngestRuns(tenant.tenantId)]);
  const base = `/dev/apps/${tenant.tenantId}`;
  const unrepaired = failures.filter((f) => !f.repairedBy).length;

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h3 className="font-medium">Commits the gate failed</h3>
        {runs.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">No data received — CI has not sent a gate result.</p>
        ) : failures.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">
            None among the commits received — every gated commit passed.
          </p>
        ) : (
          <>
            <p className="text-sm">
              {unrepaired > 0 ? <Badge tone="danger">{unrepaired} unrepaired</Badge> : <Badge tone="success">all repaired</Badge>}
            </p>
            <ul className="space-y-3">
              {failures.map(({ failure, repairedBy }) => (
                <li key={failure.sha} className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <ShortSha sha={failure.sha} href={commitUrl(tenant, failure.sha)} />
                    <Link className="hover:underline" href={`${base}/commits/${failure.sha}`}>{failure.subject}</Link>
                  </div>
                  <ul className="list-disc pl-5 text-red-700 dark:text-red-400">
                    {failure.errors.slice(0, 5).map((e, i) => <li key={i} className="break-words">{e}</li>)}
                    {failure.errors.length > 5 && <li>and {failure.errors.length - 5} more</li>}
                  </ul>
                  <div>
                    {repairedBy ? (
                      <span className="text-black/60 dark:text-white/60">
                        Repaired by <ShortSha sha={repairedBy.sha} href={commitUrl(tenant, repairedBy.sha)} /> {repairedBy.subject}
                      </span>
                    ) : (
                      <span className="text-red-700 dark:text-red-400">
                        Unrepaired — the next commit needs a <code>Repairs: {failure.sha.slice(0, 12)}</code> trailer
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="font-medium">Received from CI</h3>
        {runs.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">Nothing yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {runs.map((r) => (
              <li key={`${r.receivedAt}-${r.headSha}`} className="flex flex-wrap gap-x-3">
                <Timestamp value={r.receivedAt} />
                <span>{r.commits} commit{r.commits === 1 ? "" : "s"} up to <ShortSha sha={r.headSha} href={commitUrl(tenant, r.headSha)} /></span>
                {r.ciRunUrl && isSafeHttpUrl(r.ciRunUrl) && (
                  <a className="text-blue-700 dark:text-blue-400 hover:underline" href={r.ciRunUrl} rel="noreferrer" target="_blank">
                    the CI run
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
