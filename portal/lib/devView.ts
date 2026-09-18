// portal/lib/devView.ts — what the Dev pages compute from stored records
// (portal phase 1, S5). Pure: no database, no Next, so test/devView.test.ts
// runs the same code the pages do.

import type { DevVerdict } from "./devIngest";
import { isSafeHttpUrl } from "./safeUrl";
import type { RepoProvider } from "./tenants";

/** Data older than this is marked stale on every Dev page. */
export const STALE_AFTER_HOURS = 24;

interface Repo {
  repoUrl: string | null;
  repoProvider: RepoProvider | null;
}

function base(repo: Repo): string | null {
  if (!repo.repoUrl || !repo.repoProvider || !isSafeHttpUrl(repo.repoUrl)) return null;
  return repo.repoUrl.replace(/\/+$/, "").replace(/\.git$/, "");
}

/** The commit on the provider's site, or null when the app has no usable repository link. */
export function commitUrl(repo: Repo, sha: string): string | null {
  const root = base(repo);
  if (!root) return null;
  return repo.repoProvider === "gitlab" ? `${root}/-/commit/${sha}` : `${root}/commit/${sha}`;
}

/** A file as it was at `sha` — a permalink, because files move and a commit does not. */
export function fileUrl(repo: Repo, sha: string, path: string): string | null {
  const root = base(repo);
  if (!root) return null;
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  return repo.repoProvider === "gitlab" ? `${root}/-/blob/${sha}/${encoded}` : `${root}/blob/${sha}/${encoded}`;
}

export type Freshness = "never" | "fresh" | "stale";

/** Whether an app's CI has reached the portal recently. "never" is its own answer. */
export function freshness(lastReceived: string | Date | null, now: Date = new Date()): Freshness {
  if (!lastReceived) return "never";
  const age = now.getTime() - new Date(lastReceived).getTime();
  return age > STALE_AFTER_HOURS * 3600_000 ? "stale" : "fresh";
}

/** Failed commits that no commit's `Repairs:` trailer names. */
export function unrepairedFailures<T extends { sha: string; verdict: DevVerdict; repairs: string[] }>(
  commits: T[],
): T[] {
  const repaired = new Set(commits.flatMap((c) => c.repairs));
  return commits.filter((c) => c.verdict === "failed" && !repaired.has(c.sha));
}
