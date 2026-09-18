// /dev/apps/<app>/designs/<path> — one design: its pillars, its deviations and
// their approvals, its review passes and the commits that cite it (portal
// phase 1). Approving a deviation from here arrives in phase 2.

import Link from "next/link";

import { ShortSha, VerdictBadge } from "@/components/DevBits";
import { Badge } from "@/components/ui/Badge";
import { Timestamp } from "@/components/ui/Timestamp";
import { getDevDesign } from "@/lib/devRead";
import { commitUrl, fileUrl } from "@/lib/devView";
import { getTenant } from "@/lib/tenants";

export const dynamic = "force-dynamic";

/** A path segment, decoded once — whether or not the router already decoded it. */
function safeDecode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

const KIND_TONE = { applies: "success", "n/a": "neutral", gap: "warning", deviation: "warning", unrecognised: "danger" } as const;

export default async function DevDesignPage({ params }: { params: { app: string; path: string[] } }) {
  const tenant = await getTenant(params.app);
  if (!tenant) return null;
  const path = params.path.map(safeDecode).join("/");
  const found = await getDevDesign(tenant.tenantId, path);
  if (!found) {
    return (
      <div className="space-y-1">
        <h3 className="text-lg font-medium">No design at {path}</h3>
        <p className="text-black/60 dark:text-white/60">No commit received for this app names a design at that path that resolves.</p>
      </div>
    );
  }
  const { latest, commits, atHead } = found;
  const { design } = latest;
  const review = commits.find((c) => c.review?.resolved)?.review ?? null;
  const pillars = Object.entries(design.pillars).sort(([a], [b]) => Number(a.slice(1)) - Number(b.slice(1)));
  const file = fileUrl(tenant, latest.sha, path);
  const base = `/dev/apps/${tenant.tenantId}`;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">{design.title ?? path}</h3>
        <div className="text-sm text-black/60 dark:text-white/60 flex flex-wrap gap-x-3 mt-1">
          <Badge tone={design.status === "active" ? "warning" : "neutral"}>{design.status ?? "unknown"}</Badge>
          <span className="font-mono">{path}</span>
          {file && (
            <a className="text-blue-700 dark:text-blue-400 hover:underline" href={file} rel="noreferrer" target="_blank">
              the file at that commit
            </a>
          )}
          {latest.committedAt && <span>last cited <Timestamp value={latest.committedAt} /></span>}
        </div>
        {!atHead && (
          <p className="text-sm text-amber-700 dark:text-amber-400 mt-2">
            Not in the repository at the newest commit received — deleted or renamed. Shown as its last citing commit
            described it.
          </p>
        )}
        {design.scope.length > 0 && (
          <p className="text-sm mt-2">
            <span className="text-black/60 dark:text-white/60">Scope </span>
            <code className="font-mono text-xs">{design.scope.join("  ")}</code>
          </p>
        )}
      </div>

      <section className="space-y-2">
        <h4 className="font-medium">Deviations</h4>
        {design.deviations.some((d) => !d.approvalId) && (
          <p className="text-xs text-black/50 dark:text-white/50">
            Approving from the portal arrives in phase 2. Until then an approval is recorded at a terminal with{" "}
            <code>agentsmith approve</code>.
          </p>
        )}
        {design.deviations.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">None — this design follows every rule.</p>
        ) : (
          <ul className="space-y-2">
            {design.deviations.map((d) => (
              <li key={d.id} className="text-sm flex flex-wrap items-center gap-2">
                <code className="font-mono">{d.id}</code>
                {d.approvalId ? (
                  <Badge tone="success">approved · {d.approvalId}</Badge>
                ) : (
                  <Badge tone="warning">awaiting approval</Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h4 className="font-medium">Pillars</h4>
        {pillars.length === 0 ? (
          <p className="text-sm text-black/60 dark:text-white/60">No pillar answers were read from this design.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {pillars.map(([pillar, kind]) => (
              <span key={pillar} className="text-sm">
                <code className="font-mono mr-1">{pillar}</code>
                <Badge tone={KIND_TONE[kind]}>{kind}</Badge>
              </span>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-2">
        <h4 className="font-medium">Review</h4>
        {!review ? (
          <p className="text-sm text-black/60 dark:text-white/60">No commit citing this design names a review that resolves.</p>
        ) : (
          <div className="text-sm space-y-1">
            <p>
              {review.passes.map((p) => `Pass ${p.n}: ${p.findings}`).join(" · ") || "No passes recorded"}
            </p>
            <p>{review.signedOff === null ? "Sign-off not judged" : review.signedOff ? "Signed off" : "Sign-off incomplete"}</p>
          </div>
        )}
      </section>

      <section className="space-y-2">
        <h4 className="font-medium">Commits citing it</h4>
        <ul className="space-y-1 text-sm">
          {commits.map((c) => (
            <li key={c.sha} className="flex flex-wrap items-center gap-2">
              <VerdictBadge verdict={c.verdict} />
              <ShortSha sha={c.sha} href={commitUrl(tenant, c.sha)} />
              <Link className="hover:underline" href={`${base}/commits/${c.sha}`}>{c.subject}</Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
