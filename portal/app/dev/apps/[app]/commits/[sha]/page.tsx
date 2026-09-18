// /dev/apps/<app>/commits/<sha> — one commit and what stands behind it: the
// gate's verdict, its design with each deviation and who approved it, its
// review (portal phase 1). This is where the accountability chain starts; the
// link from a production run back to this page needs runs to report their
// commit, which arrives in phase 4.

import Link from "next/link";
import { redirect } from "next/navigation";

import { ShortSha, VerdictBadge } from "@/components/DevBits";
import { Badge } from "@/components/ui/Badge";
import { Timestamp } from "@/components/ui/Timestamp";
import { commitsStartingWith, getDevCommit } from "@/lib/devRead";
import { commitUrl, fileUrl } from "@/lib/devView";
import { getTenant } from "@/lib/tenants";

export const dynamic = "force-dynamic";

export default async function DevCommitPage({ params }: { params: { app: string; sha: string } }) {
  const tenant = await getTenant(params.app);
  if (!tenant) return null;
  const prefix = params.sha.toLowerCase();
  const matches = await commitsStartingWith(tenant.tenantId, prefix);
  if (matches.length === 1 && matches[0] !== prefix) redirect(`/dev/apps/${tenant.tenantId}/commits/${matches[0]}`);
  if (matches.length > 1) {
    return (
      <div className="space-y-1">
        <h3 className="text-lg font-medium">{params.sha} matches more than one commit</h3>
        <p className="text-black/60 dark:text-white/60">Use a few more characters of the hash.</p>
      </div>
    );
  }
  const commit = matches.length === 1 ? await getDevCommit(tenant.tenantId, matches[0]) : null;
  if (!commit) {
    return (
      <div className="space-y-1">
        <h3 className="text-lg font-medium">No commit {params.sha.slice(0, 12)} received for this app</h3>
        <p className="text-black/60 dark:text-white/60">
          It may predate the app sending gate results, or belong to another app.
        </p>
      </div>
    );
  }
  const base = `/dev/apps/${tenant.tenantId}`;
  const { design, review } = commit;

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <VerdictBadge verdict={commit.verdict} />
          <h3 className="text-lg font-medium">{commit.subject}</h3>
        </div>
        <div className="text-sm text-black/60 dark:text-white/60 flex flex-wrap gap-x-3">
          <ShortSha sha={commit.sha} href={commitUrl(tenant, commit.sha)} />
          {commit.authorName && <span>{commit.authorName}</span>}
          {commit.committedAt && <Timestamp value={commit.committedAt} />}
          {commit.parentSha && (
            <span>
              after <Link className="hover:underline" href={`${base}/commits/${commit.parentSha}`}>{commit.parentSha.slice(0, 10)}</Link>
            </span>
          )}
        </div>
      </div>

      {(commit.errors.length > 0 || commit.notes.length > 0) && (
        <section className="space-y-1">
          <h4 className="font-medium">What the gate said</h4>
          <ul className="list-disc pl-5 text-sm space-y-1">
            {commit.errors.map((e, i) => <li key={`e${i}`} className="text-red-700 dark:text-red-400 break-words">{e}</li>)}
            {commit.notes.map((n, i) => <li key={`n${i}`} className="text-amber-700 dark:text-amber-400 break-words">{n}</li>)}
          </ul>
        </section>
      )}

      <section className="space-y-2">
        <h4 className="font-medium">Design</h4>
        {!design ? (
          <p className="text-sm text-black/60 dark:text-white/60">This commit names no design.</p>
        ) : !design.resolved || !design.path ? (
          <p className="text-sm text-amber-700 dark:text-amber-400">{design.ref} — {design.reason}</p>
        ) : (
          <div className="text-sm space-y-2">
            <p>
              <Link className="text-blue-700 dark:text-blue-400 hover:underline"
                    href={`${base}/designs/${design.path.split("/").map(encodeURIComponent).join("/")}`}>
                {design.title ?? design.path}
              </Link>
              {fileUrl(tenant, commit.sha, design.path) && (
                <a className="ml-2 text-xs text-black/50 dark:text-white/50 hover:underline" rel="noreferrer" target="_blank"
                   href={fileUrl(tenant, commit.sha, design.path)!}>
                  as it was at this commit
                </a>
              )}
            </p>
            {design.deviations.length === 0 ? (
              <p className="text-black/60 dark:text-white/60">No deviations.</p>
            ) : (
              <ul className="space-y-1">
                {design.deviations.map((d) => (
                  <li key={d.id} className="flex flex-wrap items-center gap-2">
                    <code className="font-mono">{d.id}</code>
                    {d.approvalId ? (
                      <Badge tone="success">approved · {d.approvalId}</Badge>
                    ) : (
                      <Badge tone="warning">not approved when this was committed</Badge>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <section className="space-y-1">
        <h4 className="font-medium">Review</h4>
        {!review ? (
          <p className="text-sm text-black/60 dark:text-white/60">This commit names no review.</p>
        ) : !review.resolved ? (
          <p className="text-sm text-amber-700 dark:text-amber-400">{review.ref} — {review.reason}</p>
        ) : (
          <p className="text-sm">
            {review.passes.map((p) => `Pass ${p.n}: ${p.findings}`).join(" · ") || "No passes recorded"} ·{" "}
            {review.signedOff === null ? "sign-off not judged" : review.signedOff ? "signed off" : "sign-off incomplete"}
            {review.kgQuery && <> · <code className="font-mono text-xs">{review.kgQuery}</code></>}
          </p>
        )}
      </section>

      <section className="space-y-1">
        <h4 className="font-medium">In production</h4>
        <p className="text-sm text-black/60 dark:text-white/60">
          Production runs do not report their commit yet, so the runs and incidents this commit shipped into cannot be
          listed here.
        </p>
      </section>
    </div>
  );
}
