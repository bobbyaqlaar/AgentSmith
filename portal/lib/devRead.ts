// portal/lib/devRead.ts — what the Dev workspace reads (portal phase 1, S5).
//
// Everything here is read from dev_commits and dev_ingest_runs, which are a
// cache of each app's git history as its CI gate judged it. Nothing is decided
// here: verdicts are the gate's, and "awaiting approval" is a deviation whose
// latest design snapshot carries no approval id.

import { getPool } from "./db";
import type { DevCommit, DevDesign, DevReview, DevVerdict } from "./devIngest";
import { unrepairedFailures } from "./devView";
import { listTenants, type Tenant } from "./tenants";

/** A stored `DevCommit`, plus when this portal received it. Extended rather
 *  than restated: a field added to DevCommit was previously invisible here. */
export interface DevCommitRow extends DevCommit {
  receivedAt: string;
}

const COMMIT_COLUMNS =
  "sha, parent_sha, subject, author_name, author_email, committed_at, adopted, gated, verdict, " +
  "errors, notes, repairs, design, review, received_at";

/** The row `COMMIT_COLUMNS` selects — named, so the mapping below is checked. */
interface CommitDbRow {
  sha: string;
  parent_sha: string | null;
  subject: string;
  author_name: string | null;
  author_email: string | null;
  committed_at: string | Date | null;
  adopted: boolean;
  gated: boolean;
  verdict: DevVerdict;
  errors: string[] | null;
  notes: string[] | null;
  repairs: string[] | null;
  design: DevDesign | null;
  review: DevReview | null;
  received_at: string | Date;
}

function toCommit(r: CommitDbRow): DevCommitRow {
  return {
    sha: r.sha,
    parentSha: r.parent_sha,
    subject: r.subject,
    authorName: r.author_name,
    authorEmail: r.author_email,
    committedAt: r.committed_at ? new Date(r.committed_at).toISOString() : null,
    adopted: r.adopted,
    gated: r.gated,
    verdict: r.verdict,
    errors: r.errors ?? [],
    notes: r.notes ?? [],
    repairs: r.repairs ?? [],
    design: r.design,
    review: r.review,
    receivedAt: new Date(r.received_at).toISOString(),
  };
}

/** A design as it stands at the app's newest head, with the commit that last cited it. */
export interface DesignSnapshot {
  tenantId: string;
  design: DevDesign;
  /** The commit that last cited this design, or the head when none did. */
  sha: string;
  committedAt: string | null;
  authorName: string | null;
}

/**
 * Every design at each app's newest head (dev_design_snapshots). Status and
 * approvals come from here, never from the commits that cited a design — a
 * design is closed by a records commit that does not cite it. The commit shown
 * beside it is the last one that did cite it, for "who and since when".
 */
async function headDesigns(appIds: string[]): Promise<DesignSnapshot[]> {
  if (appIds.length === 0) return [];
  const pool = getPool();
  const [heads, citations] = await Promise.all([
    pool.query(
      `SELECT tenant_id, head_sha, head_committed_at, designs FROM dev_design_snapshots WHERE tenant_id = ANY($1)`,
      [appIds],
    ),
    pool.query(
      `SELECT DISTINCT ON (tenant_id, design->>'path') tenant_id, design->>'path' AS path, sha, committed_at, author_name
         FROM dev_commits
        WHERE tenant_id = ANY($1) AND design IS NOT NULL
        ORDER BY tenant_id, design->>'path', committed_at DESC NULLS LAST, received_at DESC`,
      [appIds],
    ),
  ]);
  const cited = new Map(citations.rows.map((r) => [`${r.tenant_id}\0${r.path}`, r]));
  return heads.rows.flatMap((h) =>
    (h.designs as DevDesign[]).map((design) => {
      const last = cited.get(`${h.tenant_id}\0${design.path}`);
      const time = last?.committed_at ?? h.head_committed_at;
      return {
        tenantId: h.tenant_id,
        design,
        sha: last?.sha ?? h.head_sha,
        committedAt: time ? new Date(time).toISOString() : null,
        authorName: last?.author_name ?? null,
      };
    }),
  );
}

export interface AwaitingApproval extends DesignSnapshot {
  deviationId: string;
}

/** Deviations in active designs whose latest snapshot carries no approval. */
export async function listAwaitingApprovals(appIds: string[]): Promise<AwaitingApproval[]> {
  const snapshots = await headDesigns(appIds);
  return snapshots
    .filter((s) => s.design.status === "active")
    .flatMap((s) => s.design.deviations.filter((d) => !d.approvalId).map((d) => ({ ...s, deviationId: d.id })))
    .sort((a, b) => (a.committedAt ?? "").localeCompare(b.committedAt ?? ""));
}

export interface IngestRun {
  receivedAt: string;
  headSha: string;
  ciRunUrl: string | null;
  commits: number;
}

export interface DevAppSummary {
  tenant: Tenant;
  lastGated: DevCommitRow | null;
  activeDesigns: number;
  awaitingApproval: number;
  unrepaired: number;
  lastRun: IngestRun | null;
}

/** One row per app for the Dev landing page, in the order given. */
export async function listDevApps(appIds: string[]): Promise<DevAppSummary[]> {
  if (appIds.length === 0) return [];
  const pool = getPool();
  const [tenants, lastGated, designs, failures, runs] = await Promise.all([
    listTenants(),
    pool.query(
      `SELECT DISTINCT ON (tenant_id) tenant_id, ${COMMIT_COLUMNS}
         FROM dev_commits WHERE tenant_id = ANY($1) AND gated
        ORDER BY tenant_id, committed_at DESC NULLS LAST, received_at DESC`,
      [appIds],
    ),
    headDesigns(appIds),
    pool.query(
      `SELECT tenant_id, sha, verdict, repairs FROM dev_commits
        WHERE tenant_id = ANY($1) AND (verdict = 'failed' OR repairs <> '[]'::jsonb)`,
      [appIds],
    ),
    pool.query(
      `SELECT DISTINCT ON (tenant_id) tenant_id, received_at, head_sha, ci_run_url, commits
         FROM dev_ingest_runs WHERE tenant_id = ANY($1)
        ORDER BY tenant_id, received_at DESC`,
      [appIds],
    ),
  ]);
  const byId = new Map(tenants.map((t) => [t.tenantId, t]));
  return appIds
    .filter((id) => byId.has(id))
    .map((id) => {
      const gated = lastGated.rows.find((r) => r.tenant_id === id);
      const mine = designs.filter((d) => d.tenantId === id && d.design.status === "active");
      const run = runs.rows.find((r) => r.tenant_id === id);
      return {
        tenant: byId.get(id)!,
        lastGated: gated ? toCommit(gated) : null,
        activeDesigns: mine.length,
        awaitingApproval: mine.reduce((n, d) => n + d.design.deviations.filter((x) => !x.approvalId).length, 0),
        unrepaired: unrepairedFailures(
          failures.rows.filter((r) => r.tenant_id === id).map((r) => ({ sha: r.sha, verdict: r.verdict, repairs: r.repairs })),
        ).length,
        lastRun: run
          ? { receivedAt: new Date(run.received_at).toISOString(), headSha: run.head_sha, ciRunUrl: run.ci_run_url, commits: run.commits }
          : null,
      };
    });
}

/** How many commits the changes page shows at once. */
export const COMMIT_PAGE = 200;

export async function listDevCommits(
  appId: string,
  filter: { verdict?: DevVerdict; author?: string } = {},
): Promise<{ commits: DevCommitRow[]; truncated: boolean }> {
  const { rows } = await getPool().query(
    `SELECT ${COMMIT_COLUMNS} FROM dev_commits
      WHERE tenant_id = $1 AND ($2::text IS NULL OR verdict = $2) AND ($3::text IS NULL OR author_name = $3)
      ORDER BY committed_at DESC NULLS LAST, received_at DESC
      LIMIT ${COMMIT_PAGE + 1}`,
    [appId, filter.verdict ?? null, filter.author ?? null],
  );
  return { commits: rows.slice(0, COMMIT_PAGE).map(toCommit), truncated: rows.length > COMMIT_PAGE };
}

/**
 * The full hashes of this app's commits that start with `prefix` — at most two,
 * which is enough to tell "exactly one" from "ambiguous". People paste short
 * hashes; the page resolves them rather than refusing them.
 */
export async function commitsStartingWith(appId: string, prefix: string): Promise<string[]> {
  if (!/^[0-9a-f]{7,64}$/.test(prefix)) return [];
  const { rows } = await getPool().query(
    `SELECT sha FROM dev_commits WHERE tenant_id = $1 AND sha LIKE $2 ORDER BY sha LIMIT 2`,
    [appId, `${prefix}%`],
  );
  return rows.map((r) => r.sha);
}

export async function getDevCommit(appId: string, sha: string): Promise<DevCommitRow | null> {
  const { rows } = await getPool().query(`SELECT ${COMMIT_COLUMNS} FROM dev_commits WHERE tenant_id = $1 AND sha = $2`, [
    appId,
    sha,
  ]);
  return rows[0] ? toCommit(rows[0]) : null;
}

export interface DesignListing extends DesignSnapshot {
  citedBy: number;
}

export async function listDevDesigns(appId: string): Promise<DesignListing[]> {
  const [snapshots, counts] = await Promise.all([
    headDesigns([appId]),
    getPool().query(
      `SELECT design->>'path' AS path, count(*)::int AS n FROM dev_commits
        WHERE tenant_id = $1 AND design IS NOT NULL GROUP BY 1`,
      [appId],
    ),
  ]);
  const cited = new Map(counts.rows.map((r) => [r.path, r.n]));
  return snapshots
    .map((s) => ({ ...s, citedBy: cited.get(s.design.path) ?? 0 }))
    .sort((a, b) => Number(b.design.status === "active") - Number(a.design.status === "active")
      || (a.design.path ?? "").localeCompare(b.design.path ?? ""));
}

export async function getDevDesign(
  appId: string,
  path: string,
): Promise<{ latest: DesignSnapshot; commits: DevCommitRow[]; atHead: boolean } | null> {
  const [heads, { rows }] = await Promise.all([
    headDesigns([appId]),
    getPool().query(
      `SELECT ${COMMIT_COLUMNS} FROM dev_commits
        WHERE tenant_id = $1 AND design->>'path' = $2
        ORDER BY committed_at DESC NULLS LAST, received_at DESC LIMIT ${COMMIT_PAGE}`,
      [appId, path],
    ),
  ]);
  const commits = rows.map(toCommit);
  const atHead = heads.find((h) => h.design.path === path);
  if (atHead) return { latest: atHead, commits, atHead: true };
  // Not in the repository at the newest head — deleted or renamed. Its last
  // resolved citation is all there is, and the page says so.
  const cited = commits.find((c) => c.design?.resolved);
  if (!cited || !cited.design) return null;
  return {
    latest: { tenantId: appId, design: cited.design, sha: cited.sha, committedAt: cited.committedAt, authorName: cited.authorName },
    commits,
    atHead: false,
  };
}

export async function listIngestRuns(appId: string, limit = 20): Promise<IngestRun[]> {
  const { rows } = await getPool().query(
    `SELECT received_at, head_sha, ci_run_url, commits FROM dev_ingest_runs
      WHERE tenant_id = $1 ORDER BY received_at DESC LIMIT $2`,
    [appId, limit],
  );
  return rows.map((r) => ({
    receivedAt: new Date(r.received_at).toISOString(),
    headSha: r.head_sha,
    ciRunUrl: r.ci_run_url,
    commits: r.commits,
  }));
}

/** Every failed commit, newest first, and the commit that repaired each (or null). */
export async function listGateFailures(
  appId: string,
): Promise<{ failure: DevCommitRow; repairedBy: DevCommitRow | null }[]> {
  const { rows } = await getPool().query(
    `SELECT ${COMMIT_COLUMNS} FROM dev_commits
      WHERE tenant_id = $1 AND (verdict = 'failed' OR repairs <> '[]'::jsonb)
      ORDER BY committed_at DESC NULLS LAST`,
    [appId],
  );
  const commits = rows.map(toCommit);
  return commits
    .filter((c) => c.verdict === "failed")
    .map((failure) => ({ failure, repairedBy: commits.find((c) => c.repairs.includes(failure.sha)) ?? null }));
}
