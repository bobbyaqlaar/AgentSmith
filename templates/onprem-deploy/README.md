# On-premise / air-gapped deployment template

Opt-in deployment artifact for tenants whose customers run the agent app on
their own hardware instead of a managed cloud platform — see
`OPERATIONS.md` "On-premise / air-gapped deployment". This directory is
copied into a tenant repo as `deploy/onprem/` by `ai-onprem-deploy-scaffold`
(install-ai-stack.sh); it is never auto-written by `ai-tenant-init` the way
the CI/CD workflow templates are, because not every tenant needs it.

## The contract this template assumes

AgentSmith is deliberately stack-agnostic (a tenant repo can be
Python/FastAPI, TS/React, Go, or anything else) — so this template doesn't
know or care what's inside your agent app. It only assumes your app:

1. **Ships as a single container image.** Built by the
   `build-push-ghcr` composite action already wired into
   `cd-staging.yml`/`cd-production.yml` — set the `DEPLOY_COMMAND` secret
   aside and let CD push to `ghcr.io/<org>/<repo>:<sha>` instead, or build
   your own image any way you like. Either way, this template just needs
   an image reference per version (prod / canary / shadow).
2. **Listens on one HTTP port and answers `GET /healthz` with 200.** Same
   convention Phoenix's own healthcheck in the root `docker-compose.yml`
   uses — pick whatever port, set it in `.env`.
3. **Reads all configuration from environment variables.** No calls out to
   AWS Secrets Manager / GCP Secret Manager / any cloud metadata service —
   consistent with `runtime/environment.py`'s existing fail-closed
   `ENVIRONMENT` resolver and the rest of the framework's `.env` convention.
   On Kubernetes, the same variables are sourced from a `Secret` instead
   (see `kubernetes/templates/secret.yaml`) — your app code doesn't need to
   know which.
4. **Logs JSON-Lines to stdout.** Already how `scripts/agent_logger.py`
   works framework-wide — Docker's default `json-file` log driver and
   Kubernetes' own log pipeline both capture this without extra config.
   Point the customer's own ELK/Loki/Splunk at the container runtime's log
   output; this template does not ship a logging sidecar.

If your app isn't containerized yet, that's the only real prerequisite —
everything else below treats the image as a black box.

## Two deployment targets

| | When to use | What you get |
|---|---|---|
| **Docker Compose** (this directory's `docker-compose.yml`) | ~80% of on-prem customers: a single bare-metal server or VM, minimal infra prerequisites | `docker compose up -d`, canary + shadow routing via your choice of proxy |
| **Kubernetes / Helm** (`kubernetes/`) | High-compliance enterprise customers running their own managed K8s cluster who won't run raw Docker | `helm install`, same canary/shadow behavior via the Kubernetes Gateway API |

## Choice of proxy: Traefik or Envoy

Both are real open-source options for canary weighting + shadow traffic
mirroring without touching your application code — pick based on what the
customer's ops team already knows:

- **Traefik** (`proxy/traefik/`) — simpler, label/file-based config,
  smaller learning curve. Uses Traefik's native `weighted` and `mirroring`
  service kinds (file provider, not Docker-label discovery, so it works
  identically whether the customer's images come from Docker labels or not).
- **Envoy** (`proxy/envoy/`) — more precise traffic-shaping primitives
  (`weighted_clusters` + `request_mirror_policies` on the route), heavier
  config surface, the better choice if the customer already runs Envoy
  elsewhere (service mesh, existing Envoy-based ingress).

Select with the `PROXY_ENGINE` variable in `.env` (`traefik` or `envoy`,
default `traefik`) — `docker compose` then picks up the matching overlay
file automatically via the launch script below.

## Quickstart (Docker Compose)

```bash
cp .env.example .env
# edit .env: set APP_IMAGE_PROD (required), APP_IMAGE_CANARY/APP_IMAGE_SHADOW
# (optional — omit to run prod-only with no canary/shadow), PROXY_ENGINE,
# CANARY_WEIGHT_PERCENT, DB credentials if WITH_DB=true.

./scripts/up.sh        # picks the right -f overlay based on PROXY_ENGINE
```

Traffic flow once running: `http://<server>/` → 100% prod if no canary
configured, or split `100 - CANARY_WEIGHT_PERCENT`/`CANARY_WEIGHT_PERCENT`
between prod/canary with 100% additionally mirrored (fire-and-forget,
response discarded) to the shadow container if `APP_IMAGE_SHADOW` is set.

**Why mirroring is proxy-level, not application-level, here:** the
framework's separate shadow-eval sampler (`scripts/shadow-eval.py`,
SPECS.md §9) already does *application-level* shadow evaluation — judging
a 5% sample of already-served production *traces* after the fact, safely,
because it only reads from Phoenix, never re-executes the request. This
template's proxy-level mirroring is a different thing: it's for testing a
**new version of the whole app** against live traffic shape before a real
canary promotion, not for re-running an agent's side effects. If your
agent performs side effects (writes, external API calls), do not point
`APP_IMAGE_SHADOW` at a version that isn't side-effect-safe in a dry-run
mode — Envoy/Traefik mirror the HTTP request itself, they have no
knowledge of what your app does with it. Build a read-only/dry-run mode
into the shadow image if your app has side effects; this template can't
do that for you since it doesn't know your app's internals (see "the
contract" above).

## Air-gapped bundling

No internet access is assumed once the bundle reaches the customer's
server:

```bash
# On a machine WITH internet access (build/staging):
./scripts/bundle-airgapped.sh ghcr.io/acme/app:abc1234 [ghcr.io/acme/app:canary] [...]
# Produces onprem-bundle.tar.gz containing every image, this directory's
# compose/proxy config, and pgvector's image if WITH_DB=true in .env.

# Transfer onprem-bundle.tar.gz via USB drive / private registry / secure copy.

# On the air-gapped customer server:
./scripts/load-airgapped.sh onprem-bundle.tar.gz
./scripts/up.sh
```

`bundle-airgapped.sh` uses `docker save`; `load-airgapped.sh` uses
`docker load` — no registry pull happens on the target host.

## Kubernetes / Helm

See `kubernetes/README.md`. Same `PROXY_ENGINE` choice, expressed as
`--set proxyEngine=traefik|envoy` at `helm install` time; canary weight via
`--set canary.weightPercent=10`; shadow via `--set shadow.enabled=true`.
