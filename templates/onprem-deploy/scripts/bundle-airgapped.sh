#!/usr/bin/env bash
# scripts/bundle-airgapped.sh — run on a machine WITH internet access.
# Pulls + `docker save`s every image this stack needs into one tarball for
# transfer to an air-gapped server (USB drive, secure copy, private
# registry mirror) — see README.md "Air-gapped bundling".
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -f .env ]; then
  echo "❌ .env not found — copy .env.example to .env first."
  exit 1
fi
# shellcheck disable=SC1091
set -a; source .env; set +a

IMAGES=()
[ -n "${APP_IMAGE_PROD:-}" ]   && IMAGES+=("$APP_IMAGE_PROD")
[ -n "${APP_IMAGE_CANARY:-}" ] && IMAGES+=("$APP_IMAGE_CANARY")
[ -n "${APP_IMAGE_SHADOW:-}" ] && IMAGES+=("$APP_IMAGE_SHADOW")

case "${PROXY_ENGINE:-traefik}" in
  traefik) IMAGES+=("traefik:v3.1") ;;
  envoy)   IMAGES+=("envoyproxy/envoy:v1.31-latest") ;;
esac

[ "${WITH_DB:-false}" = "true" ] && IMAGES+=("pgvector/pgvector:pg16")

if [ "${#IMAGES[@]}" -eq 0 ]; then
  echo "❌ No images resolved from .env — set at least APP_IMAGE_PROD."
  exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "📥 Pulling ${#IMAGES[@]} image(s)..."
for img in "${IMAGES[@]}"; do
  docker pull "$img"
done

echo "💾 Saving images to ${WORKDIR}/images.tar..."
docker save -o "${WORKDIR}/images.tar" "${IMAGES[@]}"

echo "📦 Packing bundle (images + compose/proxy config)..."
cp -r docker-compose.yml docker-compose.traefik.yml docker-compose.envoy.yml \
      proxy .env.example scripts "${WORKDIR}/"
rm -f "${WORKDIR}/scripts/bundle-airgapped.sh"   # not needed on the air-gapped side

tar -czf onprem-bundle.tar.gz -C "${WORKDIR}" .
echo "✅ Wrote onprem-bundle.tar.gz ($(du -h onprem-bundle.tar.gz | cut -f1))"
echo "   Transfer this file to the air-gapped server, then run load-airgapped.sh there."
