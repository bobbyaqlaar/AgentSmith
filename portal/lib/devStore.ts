// portal/lib/devStore.ts — storing what the Dev ingest accepted (portal phase 1, S3).
//
// One transaction per request: every commit, then the ingest run. A failure
// part-way stores nothing, so "last received" never advances over a partial
// write. Upserts on (app, commit), so the same CI run posted twice leaves one
// row per commit.

import { withTransaction } from "./db";
import type { DevIngest } from "./devIngest";

export async function storeDevIngest(tenantId: string, ingest: DevIngest): Promise<number> {
  return withTransaction("dev_ingest", async (client) => {
    for (const c of ingest.commits) {
      await client.query(
        `INSERT INTO dev_commits (tenant_id, sha, parent_sha, subject, author_name, author_email, committed_at,
                                  adopted, gated, verdict, errors, notes, repairs, design, review, received_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, now())
         ON CONFLICT (tenant_id, sha) DO UPDATE SET
           parent_sha = EXCLUDED.parent_sha, subject = EXCLUDED.subject,
           author_name = EXCLUDED.author_name, author_email = EXCLUDED.author_email,
           committed_at = EXCLUDED.committed_at, adopted = EXCLUDED.adopted, gated = EXCLUDED.gated,
           verdict = EXCLUDED.verdict, errors = EXCLUDED.errors, notes = EXCLUDED.notes,
           repairs = EXCLUDED.repairs, design = EXCLUDED.design, review = EXCLUDED.review,
           received_at = now()`,
        [
          tenantId, c.sha, c.parentSha, c.subject, c.authorName, c.authorEmail, c.committedAt,
          c.adopted, c.gated, c.verdict, JSON.stringify(c.errors), JSON.stringify(c.notes),
          JSON.stringify(c.repairs), c.design ? JSON.stringify(c.design) : null,
          c.review ? JSON.stringify(c.review) : null,
        ],
      );
    }
    if (ingest.designs !== null) {
      const headTime = ingest.commits.find((c) => c.sha === ingest.head)?.committedAt ?? null;
      // Replaced only by a head at least as new: a re-run of an old CI job must
      // not roll the app's designs back. An unknown time cannot be compared,
      // so it replaces.
      await client.query(
        `INSERT INTO dev_design_snapshots (tenant_id, head_sha, head_committed_at, designs, received_at)
         VALUES ($1, $2, $3, $4, now())
         ON CONFLICT (tenant_id) DO UPDATE SET
           head_sha = EXCLUDED.head_sha, head_committed_at = EXCLUDED.head_committed_at,
           designs = EXCLUDED.designs, received_at = now()
         WHERE dev_design_snapshots.head_committed_at IS NULL
            OR EXCLUDED.head_committed_at IS NULL
            OR EXCLUDED.head_committed_at >= dev_design_snapshots.head_committed_at`,
        [tenantId, ingest.head, headTime, JSON.stringify(ingest.designs)],
      );
    }
    await client.query(
      `INSERT INTO dev_ingest_runs (tenant_id, head_sha, ci_run_url, commits, schema_version)
       VALUES ($1, $2, $3, $4, $5)`,
      [tenantId, ingest.head, ingest.ciRunUrl, ingest.commits.length, ingest.schema],
    );
    return ingest.commits.length;
  });
}
