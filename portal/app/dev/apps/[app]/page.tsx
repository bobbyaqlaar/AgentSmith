// /dev/apps/<app> — the app's commits as its CI gate judged them, newest
// first, filterable by verdict and author (portal phase 1).

import Link from "next/link";

import { PillarSummary, ShortSha, VerdictBadge } from "@/components/DevBits";
import { Timestamp } from "@/components/ui/Timestamp";
import { DEV_VERDICTS, type DevVerdict } from "@/lib/devIngest";
import { COMMIT_PAGE, listDevCommits } from "@/lib/devRead";
import { commitUrl, fileUrl } from "@/lib/devView";
import { getTenant } from "@/lib/tenants";
import { verdictLabel } from "@/components/ui/Badge";

export const dynamic = "force-dynamic";

function isVerdict(value: string | undefined): value is DevVerdict {
  return value !== undefined && (DEV_VERDICTS as readonly string[]).includes(value);
}

export default async function DevChangesPage({
  params,
  searchParams,
}: {
  params: { app: string };
  searchParams: { verdict?: string; author?: string };
}) {
  // The layout has already refused a missing app or one the user may not see.
  const tenant = await getTenant(params.app);
  if (!tenant) return null;
  const verdict = isVerdict(searchParams.verdict) ? searchParams.verdict : undefined;
  const author = searchParams.author?.slice(0, 320) || undefined;
  const { commits, truncated } = await listDevCommits(tenant.tenantId, { verdict, author });
  const base = `/dev/apps/${tenant.tenantId}`;
  const filterHref = (v?: string) => {
    const q = new URLSearchParams();
    if (v) q.set("verdict", v);
    if (author) q.set("author", author);
    const s = q.toString();
    return s ? `${base}?${s}` : base;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-black/60 dark:text-white/60">Show:</span>
        {[undefined, ...DEV_VERDICTS].map((v) => (
          <Link
            key={v ?? "all"}
            href={filterHref(v)}
            aria-current={v === verdict ? "page" : undefined}
            className={`px-2 py-0.5 rounded-md ${
              v === verdict ? "bg-black/[0.06] dark:bg-white/[0.1]" : "text-blue-700 dark:text-blue-400 hover:underline"
            }`}
          >
            {v ? verdictLabel(v) : "all"}
          </Link>
        ))}
        {author && (
          <span className="ml-2">
            by <strong>{author}</strong> ·{" "}
            <Link className="text-blue-700 dark:text-blue-400 hover:underline" href={filterHref(verdict)}>
              any author
            </Link>
          </span>
        )}
      </div>

      {commits.length === 0 ? (
        <p className="text-black/60 dark:text-white/60">
          {verdict || author
            ? "No commits match this filter."
            : "No commits received for this app yet — its CI has not sent a gate result."}
        </p>
      ) : (
        <ol className="space-y-3">
          {commits.map((c) => (
            <li key={c.sha} className="border border-black/10 dark:border-white/10 rounded-lg p-4 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <VerdictBadge verdict={c.verdict} />
                <Link className="font-medium hover:underline" href={`${base}/commits/${c.sha}`}>
                  {c.subject}
                </Link>
              </div>
              <div className="text-sm text-black/60 dark:text-white/60 flex flex-wrap gap-x-3 gap-y-1">
                <ShortSha sha={c.sha} href={commitUrl(tenant, c.sha)} />
                {c.authorName && (
                  <Link className="hover:underline" href={`${base}?author=${encodeURIComponent(c.authorName)}`}>
                    {c.authorName}
                  </Link>
                )}
                {c.committedAt && <Timestamp value={c.committedAt} />}
                {c.verdict === "before_adoption" && <span>before this app adopted the gates — not checked</span>}
              </div>
              {c.design && (
                <div className="text-sm flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="text-black/60 dark:text-white/60">Design</span>
                  {c.design.resolved && c.design.path ? (
                    <>
                      <Link
                        className="text-blue-700 dark:text-blue-400 hover:underline"
                        href={`${base}/designs/${c.design.path.split("/").map(encodeURIComponent).join("/")}`}
                      >
                        {c.design.title ?? c.design.path}
                      </Link>
                      {fileUrl(tenant, c.sha, c.design.path) && (
                        <a className="text-xs text-black/50 dark:text-white/50 hover:underline" rel="noreferrer" target="_blank"
                           href={fileUrl(tenant, c.sha, c.design.path)!}>
                          file at this commit
                        </a>
                      )}
                      <PillarSummary design={c.design} />
                    </>
                  ) : (
                    <span className="text-amber-700 dark:text-amber-400">{c.design.ref} — {c.design.reason}</span>
                  )}
                </div>
              )}
              {c.review && (
                <div className="text-sm flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="text-black/60 dark:text-white/60">Review</span>
                  {c.review.resolved ? (
                    <>
                      <span>
                        {c.review.passes.length} pass{c.review.passes.length === 1 ? "" : "es"}
                        {c.review.passes.length > 0 && ` (findings ${c.review.passes.map((p) => p.findings).join(" → ")})`}
                      </span>
                      <span>{c.review.signedOff === null ? "sign-off not judged" : c.review.signedOff ? "signed off" : "sign-off incomplete"}</span>
                      {c.review.kgQuery && <code className="font-mono text-xs">{c.review.kgQuery}</code>}
                    </>
                  ) : (
                    <span className="text-amber-700 dark:text-amber-400">{c.review.ref} — {c.review.reason}</span>
                  )}
                </div>
              )}
              {(c.errors.length > 0 || c.notes.length > 0) && (
                <details className="text-sm">
                  <summary className="cursor-pointer text-black/60 dark:text-white/60">
                    {c.errors.length} error{c.errors.length === 1 ? "" : "s"}, {c.notes.length} note{c.notes.length === 1 ? "" : "s"}
                  </summary>
                  <ul className="mt-2 space-y-1 list-disc pl-5">
                    {c.errors.map((e, i) => (
                      <li key={`e${i}`} className="text-red-700 dark:text-red-400 break-words">{e}</li>
                    ))}
                    {c.notes.map((n, i) => (
                      <li key={`n${i}`} className="text-amber-700 dark:text-amber-400 break-words">{n}</li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          ))}
        </ol>
      )}
      {truncated && (
        <p className="text-sm text-black/50 dark:text-white/50">
          Showing the newest {COMMIT_PAGE}. Filter by verdict or author to narrow it.
        </p>
      )}
    </div>
  );
}
