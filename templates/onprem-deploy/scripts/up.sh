#!/usr/bin/env bash
# scripts/up.sh — renders the proxy config for whichever PROXY_ENGINE is set
# in .env, computes which optional compose profiles to activate, and brings
# the stack up. Re-run safely any time .env changes (canary/shadow weights,
# image refs) — re-renders config and does a normal `up -d` reconcile.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -f .env ]; then
  echo "❌ .env not found — copy .env.example to .env first."
  exit 1
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

PROXY_ENGINE="${PROXY_ENGINE:-traefik}"
case "$PROXY_ENGINE" in
  traefik) python3 scripts/render-traefik-config.py ;;
  envoy)   python3 scripts/render-envoy-config.py ;;
  *)
    echo "❌ PROXY_ENGINE must be 'traefik' or 'envoy', got '${PROXY_ENGINE}'"
    exit 1
    ;;
esac

PROFILES=()
[ -n "${APP_IMAGE_CANARY:-}" ] && PROFILES+=("canary")
[ -n "${APP_IMAGE_SHADOW:-}" ] && PROFILES+=("shadow")
[ "${WITH_DB:-false}" = "true" ] && PROFILES+=("with-db")

PROFILE_ARGS=()
for p in "${PROFILES[@]:-}"; do
  [ -n "$p" ] && PROFILE_ARGS+=(--profile "$p")
done

echo "🚀 Bringing up on-prem stack (proxy: ${PROXY_ENGINE}, profiles: ${PROFILES[*]:-none})..."
# "${PROFILE_ARGS[@]}" on an empty array trips "unbound variable" under
# set -u on bash <4.4 (e.g. macOS's stock /bin/bash, still 3.2) — the
# prod-only default case (no canary/shadow/with-db) hits this every time.
docker compose \
  --env-file .env \
  -f docker-compose.yml \
  -f "docker-compose.${PROXY_ENGINE}.yml" \
  ${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"} \
  up -d

echo "✅ Stack is up. Ingress: http://localhost:${PROXY_LISTEN_PORT:-80}/"
