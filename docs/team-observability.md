# Team-Shared Observability Setup

Configuring a single Arize Phoenix instance shared across all developers on a team,
with TLS termination, reverse proxy, and branch protection.

---

## 1. Quick Start (Local — single developer)

```bash
# Start Phoenix locally (no Docker required)
ai-dashboard-start

# Or with a persistent PostgreSQL backend
docker compose up -d
```

Phoenix is now at `http://localhost:6006`.

Each developer's `AGENT_PHOENIX_ENDPOINT` defaults to `http://localhost:6006`.
No further configuration is needed for solo development.

---

## 2. Team-Shared Server

Run Phoenix on a dedicated server (Linux VM, EC2, GCE, etc.) so all developers
and CI pipelines send traces to one place.

**Authentication is mandatory here, not optional** — SPECS.md §15: "An
unauthenticated shared Phoenix instance is non-compliant — production traces
may contain sensitive metadata even with redaction active." `docker-compose.yml`
binds Phoenix's own port to `127.0.0.1` only (loopback), so by default it is
**not reachable from other machines at all**, even with plain `docker compose
up -d`. Reaching it remotely requires explicitly applying the auth overlay
below — there is no way to accidentally expose it unauthenticated.

### 2.1 Start the stack on the server

```bash
# Clone the framework
git clone https://github.com/<org>/AgenticFramework.git
cd AgenticFramework

# Create a .env file with your credentials
cat > .env << 'EOF'
POSTGRES_USER=phoenix
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=phoenix
PHOENIX_PORT=6006
PHOENIX_AUTH_PORT=6007
PHOENIX_BASIC_AUTH_USER=ops
EOF

# ⚠️  The bcrypt hash contains literal '$' characters (e.g. $2a$14$...).
# Compose interpolates .env file values, so a raw '$' is silently treated as
# a (nonexistent) variable reference and CORRUPTS the hash — auth then
# rejects every password, with no error at startup. Escape every '$' as
# '$$' when writing it to .env; this one-liner does both steps correctly:
echo "PHOENIX_BASIC_AUTH_HASH=$(docker run --rm caddy:2-alpine caddy hash-password --plaintext '<your-password>' | sed 's/\$/\$\$/g')" >> .env

# Base stack + auth overlay (NOT just `docker compose up -d` — that alone
# leaves Phoenix loopback-only with no remote access at all):
docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d
```

Verify Phoenix is running (from the server itself, via loopback) and that
the authenticated port is up:

```bash
curl http://localhost:6006/healthz                                    # direct, server-local only
curl -u ops:<your-password> http://localhost:${PHOENIX_AUTH_PORT:-6007}/healthz  # via the auth sidecar
curl http://localhost:${PHOENIX_AUTH_PORT:-6007}/healthz               # should 401 without credentials
```

### 2.2 Configure each developer

Add to `~/.zshrc` or `~/.bashrc` on every developer machine — note the
**auth port** (6007), not Phoenix's own port (6006), which is unreachable
remotely by design:

```bash
export AGENT_PHOENIX_ENDPOINT="http://<server-ip>:6007"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://<server-ip>:6007/v1/traces"
```

`AGENT_PHOENIX_ENDPOINT` doesn't carry HTTP basic-auth credentials itself —
either embed them in the URL (`http://ops:<password>@<server-ip>:6007`) or
configure your HTTP client/agent runtime to send the `Authorization` header.
OTLP trace export over gRPC (port 4317) is unaffected by this auth sidecar —
it remains a separate, directly-exposed ingestion path (write-only).

Reload and verify:

```bash
source ~/.zshrc
ai-stack-check
```

### 2.3 Configure CI

Add `AGENT_PHOENIX_ENDPOINT` (pointing at the **auth port**, with embedded
credentials) as a GitHub Actions repository secret:

```
Settings → Secrets and variables → Actions → New repository secret
Name:  AGENT_PHOENIX_ENDPOINT
Value: http://ops:<password>@<server-ip>:6007
```

---

## 3. TLS / HTTPS (Recommended for team servers)

Use Caddy as a reverse proxy — it auto-provisions Let's Encrypt certificates.

### 3.1 Install Caddy

```bash
# Debian/Ubuntu
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

### 3.2 Caddyfile

```
# /etc/caddy/Caddyfile

phoenix.yourcompany.com {
    reverse_proxy localhost:6006

    # Optional: restrict to VPN / office IP range
    # @blocked not remote_ip 10.0.0.0/8 192.168.0.0/16
    # handle @blocked {
    #     respond "Forbidden" 403
    # }
}
```

Reload Caddy:

```bash
sudo systemctl reload caddy
```

### 3.3 Update developer endpoints

```bash
export AGENT_PHOENIX_ENDPOINT="https://phoenix.yourcompany.com"
export OTEL_EXPORTER_OTLP_ENDPOINT="https://phoenix.yourcompany.com/v1/traces"
```

---

## 4. Nginx Alternative

```nginx
# /etc/nginx/sites-available/phoenix

server {
    listen 443 ssl;
    server_name phoenix.yourcompany.com;

    ssl_certificate     /etc/letsencrypt/live/phoenix.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/phoenix.yourcompany.com/privkey.pem;

    location / {
        proxy_pass         http://localhost:6006;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}

server {
    listen 80;
    server_name phoenix.yourcompany.com;
    return 301 https://$host$request_uri;
}
```

```bash
sudo certbot --nginx -d phoenix.yourcompany.com
sudo systemctl reload nginx
```

---

## 5. GitHub Branch Protection

Apply branch protection to `main` so no code merges without passing CI guardrails.

### 5.1 Via `gh` CLI (recommended — idempotent)

```bash
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Guardrails — TypeScript/React"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null
```

Replace the context name with your stack's CI job name:
- TypeScript/React: `Guardrails — TypeScript/React`
- Python/FastAPI:   `Guardrails — Python/FastAPI`
- Go:               `Guardrails — Go`

### 5.2 Via GitHub UI

1. Repository → Settings → Branches → Add rule
2. Branch name pattern: `main`
3. Enable: "Require status checks to pass before merging"
4. Add the CI job name as a required check
5. Enable: "Require branches to be up to date before merging"
6. Enable: "Require a pull request before merging" (1 approval)
7. Enable: "Dismiss stale pull request approvals when new commits are pushed"
8. Save

---

## 6. Secrets Inventory

| Secret                     | Where to set                        | Description                              |
|----------------------------|-------------------------------------|------------------------------------------|
| `ANTHROPIC_API_KEY`        | GitHub → Actions secrets            | Claude models (judge + architect)        |
| `OPENAI_API_KEY`           | GitHub → Actions secrets            | GPT-4o (complex routing tier)            |
| `AGENT_PHOENIX_ENDPOINT`   | GitHub → Actions secrets            | Team Phoenix URL                         |
| `AGENT_JUDGE_MODEL`        | GitHub → Actions secrets (optional) | Defaults to `claude-3-5-sonnet-20241022` |
| `AGENT_OWNER_ID`           | GitHub → Actions secrets            | CI bot identity (e.g. `ci@example.com`)  |
| `GROQ_API_KEY`             | GitHub → Actions secrets (optional) | Standard routing tier via Groq           |

---

## 7. Backup & Recovery

### Backup PostgreSQL

```bash
# On the server
docker exec agenticframework-db pg_dump \
  -U phoenix phoenix | gzip > phoenix_backup_$(date +%Y%m%d).sql.gz
```

### Restore

```bash
gunzip -c phoenix_backup_YYYYMMDD.sql.gz | \
  docker exec -i agenticframework-db psql -U phoenix phoenix
```

### Backup golden dataset (per-repo)

The golden dataset and judge criteria are regular JSON files committed to the
repo. They are automatically backed up via git history.

```bash
git log --oneline .agent-rfc/fixtures/golden_evals.json
```

---

## 8. Multi-Project Namespacing

Each project's spans are separated in Phoenix by the `project.name` attribute,
which the post-checkout hook sets automatically from the repo name.

To view a specific project in the Phoenix UI:
1. Open `http://phoenix.yourcompany.com`
2. Projects → select your project name

To query across all projects, use the Phoenix Python SDK:

```python
import phoenix as px
client = px.Client(endpoint="http://phoenix.yourcompany.com")
spans = client.get_spans_dataframe(project_name="my-api")
```
