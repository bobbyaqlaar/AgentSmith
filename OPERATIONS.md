# AgenticFramework — Operations Guide

**Covers:** install → configure → test → operate, for everything beyond solo
dev mode: multi-tenancy, the production runtime, the Ops Portal, the In-App
Widget, and the enterprise pack.

**See also:** [Readme.md](./Readme.md) for the high-level overview ·
[UserManual.md](./UserManual.md) for day-to-day solo/team dev-mode usage ·
[SPECS.md](./SPECS.md) for the full formal specification.

Every command and code path in this document has been run against real
infrastructure while building it — real Postgres, real Redis, a real local
OIDC provider, a real `kind` Kubernetes cluster, real GPG keys — not just
read from source. Where something is a known limitation (not yet wired),
it's called out explicitly rather than glossed over.

---

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Part A — Solo Dev Install (recap)](#part-a--solo-dev-install-recap)
3. [Part B — Team-Shared Phoenix with Auth](#part-b--team-shared-phoenix-with-auth)
4. [Part C — Multi-Tenancy](#part-c--multi-tenancy)
5. [Part D — Production Runtime](#part-d--production-runtime)
6. [Part E — Ops Portal](#part-e--ops-portal)
7. [Part F — In-App Widget](#part-f--in-app-widget)
8. [Part G — Enterprise Pack](#part-g--enterprise-pack)
9. [Testing Checklist](#9-testing-checklist)
10. [Day-2 Operations](#10-day-2-operations)
11. [Troubleshooting](#11-troubleshooting)
12. [Spec Cross-Reference](#12-spec-cross-reference)

---

## 1. Prerequisites

| Tool | Needed for | Check |
|---|---|---|
| Python 3.11+ | Everything | `python3 --version` |
| Git 2.x | Everything | `git --version` |
| Docker 20+ | Team Phoenix, Ops Portal Postgres, dedicated worker pool testing | `docker --version` |
| Node.js 20+ | Ops Portal, In-App Widget | `node --version` |
| `gh` CLI | `ai-tenant-promote` (opens the promotion PR) | `gh --version` |
| GnuPG | Enterprise hook bundle signing | `gpg --version` |
| `kubectl` | Dedicated tenant worker pools | `kubectl version --client` |
| Ollama | Local/offline dev mode | `ollama --version` |

Production runtime extras (only needed if you're actually running
`runtime/llm_gateway.py` against real backends):

```bash
pip install psycopg2-binary redis temporalio langgraph-checkpoint-postgres cryptography
```

---

## Part A — Solo Dev Install (recap)

Full detail is in [UserManual.md §1–2](./UserManual.md). The short version:

```bash
curl -fsSL https://raw.githubusercontent.com/<org>/AgenticFramework/main/install-ai-stack.sh | bash
source ~/.zshrc
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"
ai-mode-local      # or ai-mode-hybrid
ai-dashboard-start
ai-stack-check
```

Everything below assumes this is done.

---

## Part B — Team-Shared Phoenix with Auth

An unauthenticated shared Phoenix instance is non-compliant (SPECS.md §15) —
the base `docker-compose.yml` binds Phoenix's own port to `127.0.0.1` only,
so by default it's **not reachable from other machines at all**.

### B.1 — Solo dev (unchanged)

```bash
docker compose up -d
curl http://localhost:6006/healthz   # works — you're on localhost
```

### B.2 — Team server: add the auth overlay

```bash
# Generate a bcrypt hash for the basic-auth password. The hash contains
# literal '$' characters that Compose's .env interpolation will otherwise
# corrupt — this one-liner escapes them correctly:
echo "PHOENIX_BASIC_AUTH_HASH=$(docker run --rm caddy:2-alpine caddy hash-password --plaintext '<your-password>' | sed 's/\$/\$\$/g')" >> .env
echo "PHOENIX_BASIC_AUTH_USER=ops" >> .env

# Base stack + auth overlay together (NOT just `docker compose up -d` —
# that alone leaves Phoenix loopback-only with no remote access at all)
docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d
```

Verify:

```bash
curl http://localhost:6007/healthz                                    # 401, no creds
curl -u ops:<your-password> http://localhost:6007/healthz             # 200
```

Developers and CI then point at port **6007** (the auth sidecar), not 6006:

```bash
export AGENT_PHOENIX_ENDPOINT="http://ops:<password>@<server-ip>:6007"
```

See [docker-compose.yml](./docker-compose.yml) and
[docker-compose.auth.yml](./docker-compose.auth.yml) header comments for the
full rationale (why this is a separate file, not a Compose profile).

---

## Part C — Multi-Tenancy

A tenant is a customer application with its own independent repository,
agents, eval suite, and deployment track (SPECS.md §23).

### C.1 — Scaffold a new tenant repo

```bash
cd /path/to/your-tenant-repo   # must be a git repo
ai-tenant-init acme --stack python-fastapi
```

Stack options: `python-fastapi` (default), `go`, `ts-react`. Add
`--isolation dedicated` if this tenant needs its own worker pool (Part D.4).

This writes:
- `.agenticframework/tenant.yaml` — tenant id, isolation tier, framework version pin, per-environment Phoenix namespaces and eval thresholds
- `.github/workflows/ci-<stack>.yml`, `cd-staging.yml`, `cd-production.yml`

Re-running is idempotent — existing files are never overwritten.

### C.2 — Configure GitHub Environments

In the tenant repo: **Settings → Environments**, create `staging` and
`production`, each with:
- Required reviewers (production)
- Environment secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `AGENT_PHOENIX_ENDPOINT`, `AGENT_OWNER_ID`

### C.3 — Promote staging → production

```bash
ai-tenant-promote acme --from staging --to production
```

This verifies the staging eval gate (`run-evals.py --fail-below 0.75`) and,
only if it passes, opens a `develop → main` PR via `gh pr create` — it never
pushes directly to `main`.

### C.4 — Dedicated isolation tier

If you scaffolded with `--isolation dedicated`, provision the tenant's own
Kubernetes worker pool:

```bash
cd runtime/k8s/dedicated-tenant
./render.sh acme my-registry/acme-worker:1.0.0 --apply

kubectl create secret generic agenticframework-secrets -n tenant-acme \
  --from-literal=DATABASE_URL="postgresql://..." \
  --from-literal=ANTHROPIC_API_KEY="..." \
  --from-literal=OPENAI_API_KEY="..." \
  --from-literal=AGENT_OWNER_ID="..."
```

The Deployment will sit at `CreateContainerConfigError` until that secret
exists — this is intentional, not a bug: it cannot silently start without
tenant-scoped credentials. See
[runtime/k8s/dedicated-tenant/README.md](./runtime/k8s/dedicated-tenant/README.md).

---

## Part D — Production Runtime

`scripts/multi_agent_system.py` / `local_agent_stack.py` are the **dev/IDE**
path. Production agent execution uses `runtime/` instead — never deployed
directly from this repo (tenant repos build their own worker image, §25).

### D.1 — LLM Gateway (budget + degrade ladder)

```python
from runtime.llm_gateway import LLMGateway

gateway = LLMGateway(tenant_id="acme", budget_cap_usd=150.0)
result = await gateway.complete(prompt="...", model_hint="developer")
```

Model registry: `runtime/models.yaml` (framework defaults) →
tenant-repo-root `models.yaml` (override) → `.agenticframework/tenant.yaml`
`gateway.routing_overrides` (per-role shorthand).

Budget backend — set before instantiating:

```bash
export BUDGET_BACKEND=postgres   # or redis, or memory (dev/CI only)
export DATABASE_URL="postgresql://..."
```

When the tenant's monthly spend breaches the cap, the gateway automatically
walks the `degrade_to` chain in `models.yaml` (e.g. `architect` →
`developer` → `validator` → `fast`/Ollama) rather than failing outright. If
the requested tier is already the free/local tier, a breach never blocks it.

Budget spend is reserved atomically **before** the provider call (an upper
bound from `max_tokens`), then reconciled to the actual cost afterward —
not read-checked-then-written-after, which would let concurrent in-flight
calls for the same tenant all slip past the cap before any of them recorded
spend. If a reservation would exceed the cap, `complete()` raises
`BudgetExceededError` immediately rather than making the provider call.

### D.2 — Trace redaction

```bash
export ENVIRONMENT=development   # explicit opt-in for local/IDE work — see note below
```

```python
from runtime.trace_redactor import TraceRedactor
provider.add_span_processor(TraceRedactor())
```

`$ENVIRONMENT` is resolved by the shared, **fail-closed**
`runtime/environment.py:get_environment()` — an unset or unrecognized value
(typo, blank, etc.) resolves to `"production"`, never to `"development"`.
This is a deliberate change from "missing var = least-restrictive
default": a worker that loses its `ENVIRONMENT` var should fail toward
*more* redaction and *more* durable checkpointing, not less. **Set
`ENVIRONMENT=development` explicitly for local/IDE work** — don't rely on
it being the default for an unset variable.

| `ENVIRONMENT` (resolved) | Behaviour |
|---|---|
| `development` (must be set explicitly) | No scrubbing |
| `staging` | Secrets/PII replaced with `[REDACTED:<hash8>]`; structure preserved |
| `production` (also the fallback for unset/unrecognized) | Scrubbed + truncated to 50 chars; full original payload stored in an AES-256-GCM-encrypted blob (`HITL_ENCRYPTION_KEY` / `HITL_ENCRYPTION_KEY_<TENANT>`), keyed per-span by `{trace_id}.{span_id}.{attr_key}` |

The tenant id used for HITL blob encryption is read from each span's own
`tenant.id` attribute, not bound once when the processor is constructed —
required for correctness on a shared (non-dedicated) worker pool processing
spans for more than one tenant in the same process.

CI check (also wired into `cd-staging.yml` / `cd-production.yml`):

```bash
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction
```

### D.3 — Postgres checkpointer (staging/production LangGraph)

```bash
export ENVIRONMENT=production
export DATABASE_URL="postgresql://..."
```

`scripts/multi_agent_system.py` uses the same `get_environment()` resolver
as D.2 above and will use a real `PostgresSaver` instead of `MemorySaver`
whenever the resolved environment is `staging`/`production` — **including
an unset or unrecognized `ENVIRONMENT`**, which now resolves to
`production` rather than `development`. It **raises** rather than silently
falling back if `DATABASE_URL` is missing in that case — `MemorySaver`
loses all HITL pause state on crash and is dev-only by design (SPECS.md §25,
§28). Local/IDE runs must set `ENVIRONMENT=development` explicitly to get
`MemorySaver` without a `DATABASE_URL`.

### D.4 — Temporal workflow pattern

`runtime/workflows/base_workflow.py` is the generic HITL-gate pattern
(execute → optionally wait on a signal with a 24h timeout → dead-letter on
timeout). `examples/oil-price-agent/workflows/` shows it applied to a
concrete domain — copy that shape into your own tenant repo, don't deploy
the example directly.

```bash
pip install temporalio
cd examples/oil-price-agent
TENANT_ID=oil-price-demo TEMPORAL_ADDRESS=localhost:7233 python3 worker.py
```

**Known gap:** `runtime/idempotency.py` and `runtime/dead_letter.py` have no
persistent store implementation yet (both raise `NotImplementedError`) —
the gateway and workflows tolerate this gracefully (treated as a cache miss
/ silent no-op), but duplicate-call suppression and DLQ depth are not yet
real in production. The Ops Portal's DLQ view reports this honestly as
`wired: false` rather than fabricating zeros.

---

## Part E — Ops Portal

Cross-tenant cost/issues dashboard. Full detail:
[portal/README.md](./portal/README.md).

### E.1 — Setup

```bash
cd portal
cp .env.example .env.local
npm install
npm run db:migrate      # applies db/schema.sql against DATABASE_URL
npm run dev             # http://localhost:3000
```

Minimum required env vars: `DATABASE_URL` (same Postgres as the LLM
Gateway's budget backend — the portal reads `llm_gateway_budget` directly,
read-only), `OPS_PORTAL_USER`, `OPS_PORTAL_PASSWORD`. The portal **refuses
to serve traffic** without basic-auth credentials configured (or, with SSO
enabled, without `SSO_SESSION_SECRET`) — there is no unauthenticated mode.

**Multi-user RBAC (optional):** set `OPS_PORTAL_USERS` instead of/alongside
`OPS_PORTAL_USER`/`PASSWORD` for per-user roles and tenant scoping:

```bash
OPS_PORTAL_USERS='[
  {"username":"alice","password":"...","role":"admin","tenants":"*"},
  {"username":"bob-readonly","password":"...","role":"viewer","tenants":["acme"]}
]'
```

For SSO, set `OPS_PORTAL_SSO_USERS` the same way, keyed by email instead of
username/password:

```bash
OPS_PORTAL_SSO_USERS='[{"email":"alice@corp.com","role":"admin","tenants":"*"}]'
```

Roles: `viewer` (read-only, scoped tenants), `operator` (+ create tenants,
mint widget tokens), `admin` (+ revoke widget tokens, read the audit log,
implicitly all tenants if `"tenants": "*"`). An authenticated SSO identity
not listed in `OPS_PORTAL_SSO_USERS` gets `viewer` with **zero** tenant
access, not full access — there is no implicit-admin fallback for "any
authenticated user." See SPECS.md §26 "Role-Based Access Control".

### E.2 — Wire tenant history sync

In each tenant's CD workflow (or a local `ai-stack-check` run):

```bash
curl -X POST https://ops.example.com/api/sync/history \
  -H "Authorization: Bearer $OPS_PORTAL_SYNC_TOKEN" -H "Content-Type: application/json" \
  -d '{"tenantId":"acme","entries":[{"entryId":"...","level":"CRITICAL","event":"...","timestamp":"...","raw":{}}]}'
```

A tenant auto-registers on its first sync — no separate provisioning step.

### E.3 — Audit log (enterprise pack, §30)

```bash
# .env.local
AUDIT_LOG_WRITE_TOKEN=...
AUDIT_LOG_HMAC_KEY=...     # rotate carefully — old events stay signed with the old key
```

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" "http://localhost:3000/api/audit?tenantId=acme"
```

Every event is HMAC-signed and the table has DB-level `UPDATE`/`DELETE`
triggers — `GET /api/audit` recomputes each signature on read and flags
`verified: false` on any row altered outside the app (even by someone who
disabled the trigger). `GET /api/audit` requires the `admin` role. Wired
call sites: `ai-tenant-init` → `tenant_created`, `ai-tenant-promote` →
`hitl_promotion`, `ai-stack-off` under an enterprise policy →
`hook_bypass`. Set `OPS_PORTAL_URL` and `AUDIT_LOG_WRITE_TOKEN` in the
shell environment those commands run in.

**Local fallback:** if `OPS_PORTAL_URL`/`AUDIT_LOG_WRITE_TOKEN` aren't set,
or the write to the portal fails (down, network error, non-2xx), the event
is appended to `~/.agent-framework/local-audit-fallback.log` as a JSON line
instead of being dropped silently. This is a local, unsigned trace for
manual reconciliation — it is not a substitute for the portal's audit log
and has no tamper protection.

### E.4 — SSO/OIDC (replaces basic auth, §30)

```bash
SSO_ENABLED=true
SSO_ISSUER=https://corp.okta.com
SSO_CLIENT_ID=...
SSO_CLIENT_SECRET=...
SSO_REDIRECT_URI=https://ops.example.com/api/auth/callback
SSO_SESSION_SECRET=<random 32+ byte string>
```

This is exclusive with basic auth, not additive — once `SSO_ENABLED=true`,
`OPS_PORTAL_USER`/`PASSWORD` no longer grant access. Machine-to-machine
endpoints (`/api/sync/*`, `/api/widget/*`, `/api/audit/append`) are
unaffected either way.

`SSO_ALLOW_INSECURE_HTTP=true` is for testing against a local non-TLS IdP
only — never set it in a real deployment.

Each SSO identity's role and tenant access are resolved via
`OPS_PORTAL_SSO_USERS` (see Part E.1 above) — logging in via SSO grants
`viewer`/no-tenants by default, not admin access, until the identity is
added to that list.

`POST /api/auth/logout` revokes the session server-side (not just the
client cookie) by recording the session's `jti` claim in the
`revoked_sessions` table; every subsequent request's session check calls
`GET /api/auth/session-status` to confirm the `jti` isn't revoked before
trusting an otherwise-valid cookie. This check fails open on a DB/network
error — it won't lock out every SSO user over a transient outage, given the
session's 8h TTL already bounds the exposure of a missed revocation.

---

## Part F — In-App Widget

Embeddable, read-only status component for tenant end users. Full detail:
[templates/in-app-widget/README.md](./templates/in-app-widget/README.md).

### F.1 — Mint a token

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" -X POST https://ops.example.com/api/tenants/acme/widget-token
# => { "token": "...", "note": "Store this now — it will not be shown again." }
```

Minting (and revoking) widget tokens requires the `admin` role.

### F.1a — Revoke a leaked token

The portal never retains a token's plaintext after minting (only its hash),
so revocation is by tenant, not by the specific token string — it revokes
**every** still-active token for that tenant:

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" -X DELETE https://ops.example.com/api/tenants/acme/widget-token
# => { "ok": true, "revoked": 2 }
```

Mint a replacement and update the tenant's embed snippet afterward.

### F.2 — Embed

```html
<script src="https://cdn.agenticframework.io/widget.js"></script>
<agent-status tenant-id="acme" token="<token>" portal-url="https://ops.example.com"></agent-status>
```

The token is the **only** access-control boundary — `tenant-id` is a
display label. A forged `tenant-id` cannot read another tenant's data.

**Known gap:** status is derived from the most recent synced
`.agent-history.log` entry (no dedicated "run" event stream yet), so
`running` is never shown — only `success` / `degraded` / `failed`.

---

## Part G — Enterprise Pack

Optional governance layer (SPECS.md §30). Full detail:
[enterprise/README.md](./enterprise/README.md).

### G.1 — Generate an org signing key (once)

```bash
gpg --full-generate-key
gpg --armor --export it-sec@example.com > org-public-key.asc   # distribute to MDM
```

### G.2 — Package and sign the hook bundle

```bash
# On a machine with hooks already installed:
./enterprise/package-hook-bundle.sh 1.0.0 \
  --gpg-key it-sec@example.com \
  --org-policy ./our-org-policy.yaml \
  --out ./dist
```

Produces `agenticframework-hooks-1.0.0.tar.gz` + `.sig`,
`agenticframework-org.yaml`, `mdm-deploy-hooks.sh`.

### G.3 — MDM deploys to every managed machine

```bash
./mdm-deploy-hooks.sh 1.0.0 --org-pubkey ./org-public-key.asc
```

This verifies the GPG signature **before** extracting anything — a
tampered or unsigned bundle is refused, not installed. Sets
`git config --global init.templateDir`, installs
`~/.agent-framework/agenticframework-org.yaml`.

### G.4 — Bypass policy enforcement

Once the org policy is installed, `ai-stack-off` enforces
`hooks.bypass_policy`:

| Policy | Behaviour |
|---|---|
| (no policy file) | Unrestricted — default dev mode |
| `disabled` | Always refuses; prints `break_glass_approvers` |
| `break-glass` | Refuses unless `AI_BREAK_GLASS_TOKEN` is set **and validates** |

`AI_BREAK_GLASS_TOKEN` is not just checked for presence — it must be a
real token IT issues, in the form `<actor>:<expires_epoch>.<hex_hmac>`,
validated locally against `BREAK_GLASS_HMAC_KEY` (a separate secret IT
distributes to managed machines, e.g. via the MDM-deployed org policy —
never the same value as the per-use token). A present-but-invalid or
expired token is refused exactly like a missing one. If
`BREAK_GLASS_HMAC_KEY` isn't configured on the machine, break-glass bypass
cannot be validated and is refused outright, regardless of what token is
supplied.

Every attempt (granted or denied) is audit-logged as `hook_bypass` —
best-effort to the Ops Portal when configured, falling back to
`~/.agent-framework/local-audit-fallback.log` otherwise so a bypass attempt
is never silently unrecorded (see Part E.3).

### G.5 — Uninstall on a managed machine

```bash
ai-stack-uninstall
```

Restores `git init.templateDir` to its value **before** AgenticFramework
was installed (not just unset), removes the shell-rc block surgically
(your own customizations before/after it are untouched), warns if an
enterprise `bypass_policy: disabled` policy is present, prompts before
removing `~/.agent-framework` / `~/.git_templates`.

---

## 9. Testing Checklist

Minimal real validation for each subsystem (no mocks):

```bash
# Framework scripts + shell
find scripts runtime examples -name "*.py" -print0 | xargs -0 -n1 python3 -m py_compile
bash -n install-ai-stack.sh && zsh -n install-ai-stack.sh

# Ops Portal (includes a cross-tenant isolation regression suite — see SPECS.md §26)
cd portal && npx tsc --noEmit && npm test && npm run build

# In-App Widget (includes an XSS-attribute-injection regression test)
cd templates/in-app-widget && npm install && npm test

# Redaction (needs ENVIRONMENT set; staging/production exercise real scrubbing)
ENVIRONMENT=staging python3 scripts/verify_system.py --check-redaction
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction

# Hook bundle signing (needs a real GPG key; see Part G.1)
gpg --verify agenticframework-hooks-<version>.tar.gz.sig agenticframework-hooks-<version>.tar.gz

# Dedicated worker pool manifests — kubectl (even --dry-run=client) needs a
# reachable cluster for API discovery; a free local one takes ~30s:
brew install kind && kind create cluster --name af-test
runtime/k8s/dedicated-tenant/render.sh acme nginx:alpine --apply
kubectl get pods -n tenant-acme   # CreateContainerConfigError until you create the Secret — expected
kind delete cluster --name af-test
```

For LLM Gateway / Postgres checkpointer / Ops Portal database code, spin up
a throwaway Postgres rather than trusting the code path untested:

```bash
docker run -d --name pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -e POSTGRES_DB=test -p 55432:5432 postgres:16-alpine
export DATABASE_URL="postgresql://test:test@localhost:55432/test"
# ... run your test, then:
docker rm -f pg-test
```

---

## 10. Day-2 Operations

| Task | Command |
|---|---|
| Upgrade vendored scripts in a tenant repo | `ai-stack-upgrade --to <version>` |
| Promote staging → production | `ai-tenant-promote <id> --from staging --to production` |
| Rotate a widget token | Mint a new one (`POST .../widget-token`) — old one keeps working until explicitly revoked |
| Rotate the audit-log HMAC key | New events sign with the new key; old events will report `verified: false` against it — re-sign history or accept the discontinuity, document which |
| Rotate the org GPG signing key | Re-run `package-hook-bundle.sh` with the new key; redistribute the new public key to MDM before the next deploy |
| Check unresolved MAJOR/CRITICAL | `ai-stack-check`, or `GET /api/audit` / `GET /api/tenants` on the Ops Portal |
| Remove the framework from a machine | `ai-stack-uninstall` |

---

## 11. Troubleshooting

See [UserManual.md §16](./UserManual.md#16-troubleshooting) for dev-mode
issues (Phoenix, Ollama, hooks, commit message format, circuit breaker).
Production/enterprise-specific:

**`ai-tenant-promote` fails with "eval gate failed"** — the staging eval
score is below 0.75; fix the regression on `develop` before retrying.

**Ops Portal won't start** — check `DATABASE_URL` is set and reachable, and
either `OPS_PORTAL_USER`+`PASSWORD` or the full `SSO_*` set is present; the
portal intentionally refuses to boot half-configured.

**Widget shows "invalid or revoked token"** — the token was never minted,
was revoked, or you're pointing `portal-url` at the wrong portal instance.

**`mdm-deploy-hooks.sh` refuses with "BAD signature"** — the bundle was
modified after signing, or you're verifying against the wrong public key.
Re-package from a clean checkout; never patch a signed tarball.

**LangGraph raises "MemorySaver is prohibited"** — you set
`ENVIRONMENT=production`/`staging` without `DATABASE_URL`, **or you simply
didn't set `ENVIRONMENT` at all** — unset/unrecognized values resolve to
`production` (fail-closed, see D.2/D.3), not `development`. Either set
`DATABASE_URL`, or set `ENVIRONMENT=development` explicitly for a
throwaway/dev run.

---

## 12. Spec Cross-Reference

| Area | SPECS.md section | Implementation |
|---|---|---|
| Tenancy model | §23, §24 | `ai-tenant-init`, `ai-tenant-promote` in `install-ai-stack.sh` |
| Production runtime | §25, §29 | `runtime/` |
| Trace redaction | §27 | `runtime/trace_redactor.py` |
| Observability / Ops Portal | §15, §26 | `portal/` |
| In-App Widget | §15, §26 | `templates/in-app-widget/` |
| Enterprise pack | §30 | `enterprise/`, `portal/lib/auditLog.ts`, `portal/lib/oidc.ts` |
| Framework hygiene | §22 Phase 5 | `hooks/`, `scripts/generate-ide-config.py`, `.github/workflows/` |
