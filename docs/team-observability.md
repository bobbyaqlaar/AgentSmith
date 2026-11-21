# Team-Shared Observability Setup

Configuring a single Arize Phoenix instance shared across all developers on a team,
with TLS termination, reverse proxy, and branch protection.

---

## 1. Quick Start (Local — single developer)

```bash
# Start Phoenix locally (no Docker required)
agentsmith dashboard start

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

**Authentication is mandatory here, not optional** — docs/DESIGN.md › Universal Observability Platform: "An
unauthenticated shared Phoenix instance is non-compliant — production traces
may contain sensitive metadata even with redaction active." `docker-compose.yml`
binds Phoenix's own port to `127.0.0.1` only (loopback), so by default it is
**not reachable from other machines at all**, even with plain `docker compose
up -d`. Reaching it remotely requires explicitly applying the auth overlay
below — there is no way to accidentally expose it unauthenticated.

### 2.1 Start the stack on the server

```bash
# Clone the framework
git clone https://github.com/bobbyaqlaar/AgentSmith.git
cd AgentSmith

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

Add to `~/.zshrc` or `~/.bashrc` on every developer machine. `<phoenix-host>`
is a name that serves TLS in front of the **auth port** (6007), not Phoenix's
own port (6006), which is unreachable remotely by design — see §3 for the TLS
front:

```bash
export AGENT_PHOENIX_ENDPOINT="https://<phoenix-host>"
export OTEL_EXPORTER_OTLP_ENDPOINT="https://<phoenix-host>/v1/traces"
```

The collector must serve TLS. AgentSmith's exporter (`agentsmith/otlp.py`)
sends spans and metrics only over https, or plain http to this machine
(`localhost`, `127.0.0.1`, `::1`); an address like `http://<server-ip>:6007`
is refused with an ERROR log line and nothing is exported.

`AGENT_PHOENIX_ENDPOINT` carries no credential. Send the sidecar's basic-auth
credential as an `Authorization` header: for span and metric export, set
`OTEL_EXPORTER_OTLP_HEADERS` as shown in §3.3. Do not write it into the URL
(`https://ops:<password>@…`). AgentSmith's own senders use urllib, which
cannot send a password in the address: it refuses the request, and session
start says "cannot be opened as written". An address is also printed and
logged in more places than a header.
OTLP trace export over gRPC (port 4317) is unaffected by this auth sidecar —
it remains a separate, directly-exposed ingestion path (write-only).

Reload and verify:

```bash
source ~/.zshrc
agentsmith check
```

### 2.3 Configure CI

Add two GitHub Actions repository secrets: the address of the TLS front for
the **auth port**, and the header that carries its credential (§3.3):

```
Settings → Secrets and variables → Actions → New repository secret
Name:  AGENT_PHOENIX_ENDPOINT
Value: https://<phoenix-host>

Name:  OTEL_EXPORTER_OTLP_HEADERS
Value: Authorization=Basic%20<base64 of user:password>
```

---

## 3. TLS / HTTPS (required for export from another machine)

AgentSmith exports to a collector on another machine only over https, so a
team server needs a TLS front.

Point the TLS front at the auth sidecar's port (6007), not Phoenix's (6006);
6006 has no authentication.

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
    # the auth sidecar (PHOENIX_AUTH_PORT, default 6007) — never Phoenix's own 6006, which has no auth
    reverse_proxy localhost:6007

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

The TLS front reaches Phoenix through the auth sidecar, so the span and metric
exporter (`agentsmith/otlp.py`, the OpenTelemetry SDK's) must send the
sidecar's basic-auth credential, or every export is refused with 401:

```bash
export AGENT_PHOENIX_ENDPOINT="https://phoenix.yourcompany.com"
export OTEL_EXPORTER_OTLP_ENDPOINT="https://phoenix.yourcompany.com/v1/traces"
# base64 of "<user>:<password>": PHOENIX_BASIC_AUTH_USER and the password you hashed in §2.1
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic%20$(printf '%s' '<user>:<password>' | base64 | tr -d '\n')"
```

The header value is URL-encoded, so the space after `Basic` is written `%20`.
Keep the line in your shell profile or a secrets manager, not in a repository:
it is a credential.

Not covered yet: the gate's own spans (`scripts/gate_tracing.py`, shipped at
session start) are sent without this header, so behind the auth sidecar they
stay spooled and session start says "gate spans NOT exported — … Unauthorized".
That is on the backlog (`docs/PRODUCT_BACKLOG.md`).

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
        # the auth sidecar (PHOENIX_AUTH_PORT, default 6007) — never Phoenix's own 6006, which has no auth
        proxy_pass         http://localhost:6007;
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
| provider keys per `models.yaml` | GitHub → Actions secrets        | One per route the active profile binds   |
| `OPENAI_API_KEY`           | GitHub → Actions secrets            | GPT-4o (complex routing tier)            |
| `AGENT_PHOENIX_ENDPOINT`   | GitHub → Actions secrets            | Team Phoenix URL                         |
| `AGENT_JUDGE_MODEL`        | Not needed — declare a `judge` role in `models.yaml` | Ignored when a role is declared; the registry wins |
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
1. Open `https://phoenix.yourcompany.com` and sign in with the sidecar's credential
2. Projects → select your project name

To query across all projects, use the Phoenix Python SDK:

```python
import phoenix as px
client = px.Client(endpoint="https://phoenix.yourcompany.com")
spans = client.get_spans_dataframe(project_name="my-api")
```

The TLS front reaches Phoenix through the auth sidecar (§3), so the client must
send the same basic-auth `Authorization` header as in §3.3; how it takes extra
headers depends on your Phoenix client's version.
