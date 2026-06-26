#!/usr/bin/env bash
# scripts/load-airgapped.sh — run on the air-gapped target server. Loads a
# bundle produced by bundle-airgapped.sh; never pulls from any registry.
set -euo pipefail

BUNDLE="${1:-onprem-bundle.tar.gz}"
if [ ! -f "$BUNDLE" ]; then
  echo "❌ Bundle not found: $BUNDLE"
  echo "   Usage: ./load-airgapped.sh <path-to-onprem-bundle.tar.gz>"
  exit 1
fi

DEST="${2:-.}"
mkdir -p "$DEST"
echo "📦 Extracting bundle to ${DEST}..."
tar -xzf "$BUNDLE" -C "$DEST"

echo "💾 Loading images (no network access required)..."
docker load -i "${DEST}/images.tar"

echo "✅ Bundle loaded into ${DEST}. Next steps:"
echo "   cd ${DEST} && cp .env.example .env   # edit .env, then:"
echo "   ./scripts/up.sh"
