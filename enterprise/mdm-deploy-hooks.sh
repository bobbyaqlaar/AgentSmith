#!/usr/bin/env bash
# enterprise/mdm-deploy-hooks.sh — IT deployment script template (SPECS.md §30).
#
# Run by an MDM (Jamf, Intune, Kandji, etc.) on every managed developer
# machine. Verifies the GPG signature of the hook bundle against the org's
# public key BEFORE extracting anything — a corrupted or unsigned bundle is
# refused, not installed.
#
# Expects, in the same directory as this script (or pass --bundle-dir):
#   agenticframework-hooks-<version>.tar.gz
#   agenticframework-hooks-<version>.tar.gz.sig
#   agenticframework-org.yaml
#
# Usage (typically invoked by the MDM agent, not interactively):
#   ./mdm-deploy-hooks.sh <version> --org-pubkey <path/to/org-public-key.asc> [--bundle-dir <dir>]

set -euo pipefail

VERSION="${1:-}"
[ -n "$VERSION" ] || { echo "❌ Usage: $0 <version> --org-pubkey <path> [--bundle-dir <dir>]"; exit 1; }
shift

ORG_PUBKEY=""
BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

while [ $# -gt 0 ]; do
  case "$1" in
    --org-pubkey)  ORG_PUBKEY="${2:-}"; shift 2 ;;
    --bundle-dir)  BUNDLE_DIR="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

[ -n "$ORG_PUBKEY" ] || { echo "❌ --org-pubkey <path/to/org-public-key.asc> is required"; exit 1; }
[ -f "$ORG_PUBKEY" ] || { echo "❌ Org public key not found: $ORG_PUBKEY"; exit 1; }

TARBALL="$BUNDLE_DIR/agenticframework-hooks-${VERSION}.tar.gz"
SIGFILE="${TARBALL}.sig"
ORG_YAML="$BUNDLE_DIR/agenticframework-org.yaml"

for f in "$TARBALL" "$SIGFILE" "$ORG_YAML"; do
  [ -f "$f" ] || { echo "❌ Missing required bundle file: $f"; exit 1; }
done

command -v gpg >/dev/null 2>&1 || { echo "❌ gpg is required on this machine"; exit 1; }

echo "🔑 Importing org public key..."
GNUPGHOME="$(mktemp -d)"
export GNUPGHOME
gpg --batch --quiet --import "$ORG_PUBKEY"

echo "🔏 Verifying signature..."
if ! gpg --batch --verify "$SIGFILE" "$TARBALL" 2>&1; then
  echo "❌ SIGNATURE VERIFICATION FAILED — refusing to install a corrupted or unsigned hook bundle."
  rm -rf "$GNUPGHOME"
  exit 1
fi
echo "✅ Signature verified."
rm -rf "$GNUPGHOME"

TEMPLATE_DIR="$HOME/.git_templates"
mkdir -p "$TEMPLATE_DIR"

echo "📦 Extracting hooks to $TEMPLATE_DIR..."
tar -xzf "$TARBALL" -C "$TEMPLATE_DIR"
chmod +x "$TEMPLATE_DIR"/hooks/*

echo "🔗 Linking git templateDir..."
git config --global init.templateDir "$TEMPLATE_DIR"

echo "📋 Installing org policy..."
FRAMEWORK_DIR="$HOME/.agent-framework"
mkdir -p "$FRAMEWORK_DIR"
cp "$ORG_YAML" "$FRAMEWORK_DIR/agenticframework-org.yaml"

echo ""
echo "🎯 Hook bundle v${VERSION} installed and verified on this machine."
echo "   Org policy: $FRAMEWORK_DIR/agenticframework-org.yaml"
echo "   ai-stack-off now enforces this org's bypass_policy."
