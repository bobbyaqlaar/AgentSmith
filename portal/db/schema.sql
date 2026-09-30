-- AgentSmith Ops Portal — schema (docs/DESIGN.md › Universal Observability Platform, Federated Observability).
--
-- Runs against the same Postgres instance used by runtime/llm_gateway.py's
-- Postgres budget backend (DATABASE_URL) — the portal reads `llm_gateway_budget`
-- directly (read-only) and owns these additional tables itself.

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    isolation    TEXT NOT NULL DEFAULT 'shared' CHECK (isolation IN ('shared', 'dedicated')),
    phoenix_base_url TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- budget_cap_usd (docs/PRODUCT_ARCHIVE.md P2b), added after the table already
-- shipped — CREATE TABLE IF NOT EXISTS above is a no-op against an
-- already-existing `tenants` table, so the column has to be added via
-- ALTER for this migration to actually apply to a pre-existing database
-- (confirmed: without this, re-running the migration left `column
-- "budget_cap_usd" does not exist` errors against pre-existing data).
-- Synced from .agenticframework/tenant.yaml's gateway.budget_cap_usd via
-- scripts/sync-portal-history.py — NULL until a tenant repo's CD pipeline
-- has synced at least once. This is a *display* cap for the Ops Portal's
-- cost page; it does not enforce anything — the actual enforcement is
-- runtime/llm_gateway.py's own AGENT_MONTHLY_USD_CAP env var on the
-- worker, which this is meant to mirror, not replace (deliberately not
-- threading the worker's env var into the portal directly — that would be
-- a second, harder-to-audit path for the same number to reach this table).
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS budget_cap_usd DOUBLE PRECISION;

-- replay_webhook_url / replay_webhook_secret (HITL/DLQ redesign): where the
-- Ops Portal's DLQ "Replay with edits" action sends an edited payload for
-- THIS tenant — deliberately per-tenant, not a single shared endpoint, so a
-- human-in-the-loop fix is routed to the specific team running that
-- tenant's worker (runtime/replay_webhook_server.py), never cross-tenant.
-- Synced the same way budget_cap_usd is, from
-- .agenticframework/tenant.yaml's hitl.replay_webhook_url /
-- hitl.replay_webhook_secret. The secret is used to HMAC-sign the portal's
-- outgoing webhook body so the tenant's receiver can verify the request
-- actually came from this portal — see portal/lib/dlq.ts's replayDlqEntry().
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS replay_webhook_url TEXT;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS replay_webhook_secret TEXT;

-- Synced from each tenant repo's .agent-history.log via POST /api/sync/history
-- (called from cd-staging.yml / cd-production.yml, or ai-stack-check locally).
CREATE TABLE IF NOT EXISTS agent_history_entries (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    entry_id      TEXT NOT NULL,            -- dedupe key: original log entry's own id/timestamp+event hash
    level         TEXT NOT NULL,            -- INFO | MINOR | MAJOR | CRITICAL
    event         TEXT NOT NULL,
    timestamp     TIMESTAMPTZ NOT NULL,
    hitl_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    raw           JSONB NOT NULL,
    synced_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, entry_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_history_unresolved
    ON agent_history_entries (tenant_id, level)
    WHERE hitl_resolved = FALSE AND level IN ('MAJOR', 'CRITICAL');

-- Read-only scoped tokens for the In-App Widget (templates/in-app-widget/,
-- docs/DESIGN.md › Universal Observability Platform, Federated Observability). The token itself is the only access-control boundary —
-- never trust a client-supplied tenant-id for this. Only the hash is stored;
-- the plaintext token is shown once at creation time (POST /api/tenants/:id/widget-token).
CREATE TABLE IF NOT EXISTS widget_tokens (
    token_hash   TEXT PRIMARY KEY,        -- sha256(plaintext token)
    tenant_id    TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at   TIMESTAMPTZ
);

-- Immutable audit log (docs/DESIGN.md › Enterprise Install and Compliance Pack, enterprise pack). Every event is signed
-- with HMAC-SHA256 over its own fields (see portal/lib/auditLog.ts) so
-- tampering is detectable even by someone with direct DB access — and a
-- trigger below blocks UPDATE/DELETE outright (append-only at the DB level).
CREATE TABLE IF NOT EXISTS audit_log (
    event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type  TEXT NOT NULL CHECK (event_type IN ('hook_bypass', 'hitl_promotion', 'config_change', 'tenant_created')),
    actor_id    TEXT NOT NULL,
    -- Deliberately no ON DELETE CASCADE (unlike agent_history_entries) and no
    -- ON DELETE SET NULL either — the latter would itself be an UPDATE on
    -- this table and get rejected by the append-only trigger below. Default
    -- FK behavior (RESTRICT) means a tenant with audit history simply can't
    -- be deleted, which matches "audit log is append-only/immutable" better
    -- than silently losing rows or erroring inside a trigger.
    tenant_id   TEXT REFERENCES tenants(tenant_id),
    details     JSONB NOT NULL DEFAULT '{}'::jsonb,
    signature   TEXT NOT NULL    -- hex HMAC-SHA256 of (event_id, timestamp, event_type, actor_id, tenant_id, details)
);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log (tenant_id, "timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_type ON audit_log (event_type, "timestamp" DESC);

CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only — % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log;
CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

-- Server-side session revocation (docs/PRODUCT_ARCHIVE.md 4.14). The SSO
-- session JWT (portal/lib/sessionToken.ts) is stateless and otherwise valid
-- for its full 8h TTL even after logout if it was copied/leaked elsewhere —
-- this lets POST /api/auth/logout actually invalidate it server-side instead
-- of only deleting the cookie on the responding client. Keyed by jti, not
-- the token itself, so this table never holds anything bearer-equivalent.
CREATE TABLE IF NOT EXISTS revoked_sessions (
    jti        TEXT PRIMARY KEY,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Revoked entries only matter inside the token's own 8h TTL, so anything older
-- is dead weight and safe to prune:
--
--   DELETE FROM revoked_sessions WHERE revoked_at < now() - interval '1 day';
--
-- Not automated here — this file runs migrations, not cron. It is listed as a
-- Day-2 task in docs/UserManual.md › Maintain (Day-2 Operations), which it was not until 2026-08-25: a
-- maintenance instruction that exists only inside a schema file is filed where
-- nobody maintaining the portal will read it, and the table grew one row per
-- logout, forever.

-- Agent run status (docs/PRODUCT_ARCHIVE.md P2a). Unlike dlq_entries/
-- llm_gateway_budget, this IS portal-owned state — runtime/llm_gateway.py
-- only ever POSTs to it via the ingest API (best-effort, optional), it
-- never connects to Postgres to create this table itself — so the
-- migration owns the DDL. Backing portal/lib/runStatus.ts's "running"
-- status, which was previously unreachable (derived only from
-- .agent-history.log, which has no concept of an in-progress run).
CREATE TABLE IF NOT EXISTS agent_runs (
    run_id        TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    workflow_id   TEXT,
    status        TEXT NOT NULL CHECK (status IN ('running', 'success', 'degraded', 'failed')),
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    trace_id      TEXT,
    error_summary TEXT,
    -- Usage, NULLABLE on purpose. NULL means the provider reported none — a
    -- streamed call has no usage in v1 — and 0 means it reported zero. A
    -- NOT NULL DEFAULT 0 here would make a dashboard that SUMs these silently
    -- undercount every streamed run instead of showing a gap.
    input_tokens  INTEGER,
    output_tokens INTEGER,
    cost_usd      NUMERIC(12, 6),
    -- Which AgentSmith wrote this row. NULLABLE, and the NULL is meaningful:
    -- it is a row from a framework old enough not to report one, which is a
    -- different fact from a current tenant that failed to. This portal is run
    -- by IT and the tenants by the business on independent cadences, so it is
    -- always reading a fleet spanning several versions — and a version decides
    -- which of the columns above a tenant can populate at all. See
    -- portal/lib/wireContract.ts.
    framework_version TEXT
);

-- agent_runs predates these three, and CREATE TABLE IF NOT EXISTS is a no-op
-- against a database that already has the table — so a deployed portal would
-- never gain the columns from the definition above. Same lesson as
-- tenants.budget_cap_usd (Product_Archive P2b): the image bakes schema.sql at
-- build time and db:migrate re-runs it, which silently no-ops new columns.
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS input_tokens  INTEGER;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS output_tokens INTEGER;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS cost_usd      NUMERIC(12, 6);
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS framework_version TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_runs_tenant_started
    ON agent_runs (tenant_id, started_at DESC);

-- ── The Dev workspace (portal phase 1, .agent-rfc/designs/portal-phase1.md) ──
--
-- What the process gate decided about each commit, sent by the app's CI
-- (`process_gate.py ci --json`). These tables are a CACHE of git: every fact
-- in them can be rebuilt from the app's history, and the portal never decides
-- a verdict of its own.

-- One row today. Every new table carries org_id so a later multi-organisation
-- portal is a data change, not a schema rewrite; nothing isolates by it yet.
CREATE TABLE IF NOT EXISTS orgs (
    org_id      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO orgs (org_id, name) VALUES ('default', 'Default organisation') ON CONFLICT (org_id) DO NOTHING;

-- An app's repository. The table keeps the name `tenants`; the UI says "app".
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS repo_url       TEXT;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS repo_provider  TEXT CHECK (repo_provider IN ('github', 'gitlab'));
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS default_branch TEXT;

-- One app's CI credential for the Dev ingest. Only the SHA-256 is stored; the
-- token is shown once, when issued. The app a request writes to is the app
-- its token belongs to — never an id in the request body.
CREATE TABLE IF NOT EXISTS app_ingest_tokens (
    token_hash  TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL DEFAULT 'default' REFERENCES orgs(org_id),
    tenant_id   TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  TEXT,
    revoked_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_app_ingest_tokens_tenant ON app_ingest_tokens (tenant_id);

-- One commit as the gate judged it. Keyed on (app, commit): the same CI run
-- posted twice leaves one row.
CREATE TABLE IF NOT EXISTS dev_commits (
    org_id        TEXT NOT NULL DEFAULT 'default' REFERENCES orgs(org_id),
    tenant_id     TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    sha           TEXT NOT NULL,
    parent_sha    TEXT,
    subject       TEXT NOT NULL,
    author_name   TEXT,
    author_email  TEXT,
    committed_at  TIMESTAMPTZ,
    adopted       BOOLEAN NOT NULL,
    gated         BOOLEAN NOT NULL,
    verdict       TEXT NOT NULL CHECK (verdict IN ('passed', 'failed', 'passed_with_notes', 'not_gated', 'before_adoption')),
    errors        JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes         JSONB NOT NULL DEFAULT '[]'::jsonb,
    repairs       JSONB NOT NULL DEFAULT '[]'::jsonb,
    design        JSONB,
    review        JSONB,
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, sha)
);
CREATE INDEX IF NOT EXISTS idx_dev_commits_tenant_committed ON dev_commits (tenant_id, committed_at DESC);

-- Every design document as it stood at the newest head an app's CI has sent.
-- Status and approvals are read from here, not from the commits that cited a
-- design: a design is closed by a records commit that does not cite it, so the
-- last citing commit still says `active`. One row per app, replaced only by a
-- head at least as new, so a re-run of an old CI job cannot roll it back.
CREATE TABLE IF NOT EXISTS dev_design_snapshots (
    tenant_id          TEXT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    org_id             TEXT NOT NULL DEFAULT 'default' REFERENCES orgs(org_id),
    head_sha           TEXT NOT NULL,
    head_committed_at  TIMESTAMPTZ,
    designs            JSONB NOT NULL,
    received_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Each accepted ingest: when an app's CI last reached the portal, and from
-- which run. "Last received" on every Dev page reads this.
CREATE TABLE IF NOT EXISTS dev_ingest_runs (
    ingest_id       BIGSERIAL PRIMARY KEY,
    org_id          TEXT NOT NULL DEFAULT 'default' REFERENCES orgs(org_id),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    head_sha        TEXT NOT NULL,
    ci_run_url      TEXT,
    commits         INTEGER NOT NULL,
    schema_version  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dev_ingest_runs_tenant_received ON dev_ingest_runs (tenant_id, received_at DESC);

-- An author's answers for a tenant not yet created, pulled by
-- `agentsmith tenant init --from <id>` (.agent-rfc/designs/portal-intake-pull.md).
-- tenant_id is deliberately NOT a foreign key: the tenant does not exist yet,
-- which is the whole point. No CHECK on stack or isolation either: those sets
-- are pinned against their Python owners by test/catalogs.test.ts, and a second
-- CHECK on `isolation` would be one catalogs.test.ts's reader never reaches.
-- The token is shown once; only its SHA-256 is kept, as for app_ingest_tokens.
CREATE TABLE IF NOT EXISTS tenant_intakes (
    intake_id     BIGSERIAL PRIMARY KEY,
    org_id        TEXT NOT NULL DEFAULT 'default' REFERENCES orgs(org_id),
    token_hash    TEXT NOT NULL UNIQUE,
    tenant_id     TEXT NOT NULL,
    stack         TEXT NOT NULL,
    isolation     TEXT NOT NULL,
    architecture  TEXT,
    agentic       BOOLEAN NOT NULL,
    ides          JSONB NOT NULL DEFAULT '[]'::jsonb,
    rfc           JSONB NOT NULL,
    created_by    TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,
    consumed_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tenant_intakes_tenant ON tenant_intakes (tenant_id);

-- Deliberately NOT created here: dlq_entries, idempotency_keys.
--
-- Both are owned and created by the Python runtime side, not this
-- migration — runtime/dead_letter.py's DeadLetterQueue and
-- runtime/idempotency.py's _PostgresBackend each run `CREATE TABLE IF NOT
-- EXISTS` against DATABASE_URL on first construction, the same pattern
-- runtime/llm_gateway.py's _PostgresBudgetBackend already uses for
-- `llm_gateway_budget` (also not in this file). portal/lib/dlq.ts checks
-- whether `dlq_entries` exists and reports `wired: false` until a worker
-- has actually constructed a DeadLetterQueue at least once against this
-- database — that "have workers actually run against this DB" signal is
-- the whole point; this migration pre-creating the table would make it
-- meaningless (the portal would always claim "wired" with zero entries).
--
-- `dlq_entries` columns, for reference (see DeadLetterQueue.__init__ for
-- the authoritative DDL):
--   task_id TEXT PRIMARY KEY, tenant_id TEXT, payload JSONB, error TEXT,
--   status TEXT DEFAULT 'pending', created_at TIMESTAMPTZ,
--   replayed_at TIMESTAMPTZ, discarded_at TIMESTAMPTZ
