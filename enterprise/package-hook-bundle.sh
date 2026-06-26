#!/usr/bin/env bash
# enterprise/package-hook-bundle.sh — produces the signed org hook bundle
# (SPECS.md §30):
#
#   agenticframework-hooks-<version>.tar.gz       # hook files
#   agenticframework-hooks-<version>.tar.gz.sig   # detached GPG signature
#   agenticframework-org.yaml                     # org policy file
#   mdm-deploy-hooks.sh                            # IT deployment script
#
# Usage:
#   ./enterprise/package-hook-bundle.sh <version> --gpg-key <key-id-or-email> \
#     [--org-policy <path/to/agenticframework-org.yaml>] [--out <dir>]
#
# Packages hooks from the LOCAL installed template dir ($HOME/.git_templates/hooks),
# i.e. whatever this machine currently has installed via install-ai-stack.sh —
# package what's been validated locally, then sign it for distribution.

set -euo pipefail

VERSION="${1:-}"
[ -n "$VERSION" ] || { echo "❌ Usage: $0 <version> --gpg-key <key-id-or-email> [--org-policy <path>] [--out <dir>]"; exit 1; }
shift

GPG_KEY=""
ORG_POLICY=""
OUT_DIR="."

while [ $# -gt 0 ]; do
  case "$1" in
    --gpg-key)    GPG_KEY="${2:-}"; shift 2 ;;
    --org-policy) ORG_POLICY="${2:-}"; shift 2 ;;
    --out)        OUT_DIR="${2:-.}"; shift 2 ;;
    *) shift ;;
  esac
done

[ -n "$GPG_KEY" ] || { echo "❌ --gpg-key <key-id-or-email> is required"; exit 1; }

HOOKS_DIR="$HOME/.git_templates/hooks"
if [ ! -d "$HOOKS_DIR" ] || [ -z "$(ls -A "$HOOKS_DIR" 2>/dev/null)" ]; then
  echo "❌ No hooks found at $HOOKS_DIR — run install-ai-stack.sh on this machine first"
  exit 1
fi

if ! command -v gpg >/dev/null 2>&1; then
  echo "❌ gpg is required. Install: brew install gnupg (macOS) / apt install gnupg (Debian/Ubuntu)"
  exit 1
fi

mkdir -p "$OUT_DIR"
TARBALL="$OUT_DIR/agenticframework-hooks-${VERSION}.tar.gz"
SIGFILE="${TARBALL}.sig"
ORG_YAML_OUT="$OUT_DIR/agenticframework-org.yaml"
MDM_SCRIPT_OUT="$OUT_DIR/mdm-deploy-hooks.sh"

echo "📦 Packaging hooks from $HOOKS_DIR..."
tar -czf "$TARBALL" -C "$HOME/.git_templates" hooks
echo "✅ Wrote $TARBALL"

echo "🔏 Signing with GPG key: $GPG_KEY..."
gpg --batch --yes --local-user "$GPG_KEY" --detach-sign --output "$SIGFILE" "$TARBALL"
echo "✅ Wrote $SIGFILE"

if [ -n "$ORG_POLICY" ]; then
  [ -f "$ORG_POLICY" ] || { echo "❌ --org-policy file not found: $ORG_POLICY"; exit 1; }
  cp "$ORG_POLICY" "$ORG_YAML_OUT"
  echo "✅ Copied org policy from $ORG_POLICY"
else
  cp "$(dirname "$0")/agenticframework-org.yaml.example" "$ORG_YAML_OUT"
  echo "⚠️  No --org-policy provided — wrote the example policy to $ORG_YAML_OUT. EDIT IT before distributing."
fi
# Stamp the actual bundle version into the policy file's hooks.version field.
sed -i.bak "s/^  version: .*/  version: \"${VERSION}\"/" "$ORG_YAML_OUT" && rm -f "${ORG_YAML_OUT}.bak"

cp "$(dirname "$0")/mdm-deploy-hooks.sh" "$MDM_SCRIPT_OUT"
chmod +x "$MDM_SCRIPT_OUT"
echo "✅ Copied $MDM_SCRIPT_OUT"

echo ""
echo "🎯 Bundle ready in $OUT_DIR:"
ls -la "$TARBALL" "$SIGFILE" "$ORG_YAML_OUT" "$MDM_SCRIPT_OUT"
echo ""
echo "   Verify before distributing:"
echo "   gpg --verify $SIGFILE $TARBALL"
