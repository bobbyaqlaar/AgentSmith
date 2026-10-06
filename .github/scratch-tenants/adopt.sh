#!/usr/bin/env bash
# .github/scratch-tenants/adopt.sh — build the ADOPTED scratch tenant: an existing
# repository brought under the gates by `agentsmith tenant adopt`, the path every
# real tenant now takes (.agent-rfc/designs/scratch-adopted.md).
#
#   usage: adopt.sh <target-dir> <framework-ref>
#          framework-ref = the AgentSmith commit (or tag) the tenant's gates
#                          workflow installs the provider from — in CI, the
#                          commit under test.
#
# The other scratch tenants are built by the machine's post-checkout hook (the
# vendored path); this one by the command a real repository runs. It:
#
#   1. starts an orphan `main` in <target-dir> — adopt refuses a repository
#      already under the gates, so every build re-adopts from a clean history
#      (the workflow force-pushes; owner-approved, 2026-10-06);
#   2. commits adopted/ as the repository's own code — no gates exist yet, so
#      there are no hooks to run;
#   3. runs `agentsmith tenant adopt` against <framework-ref>;
#   4. makes the adoption commit exactly as adopt prints it — through the
#      tenant's own contract-3 commit gate, answered by the provider installed
#      on this machine. Nothing bypasses a hook.

set -euo pipefail

TARGET="${1:?usage: adopt.sh <target-dir> <framework-ref>}"
REF="${2:?usage: adopt.sh <target-dir> <framework-ref>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/adopted"
BOT="AgentSmith scratch-tenants"

command -v agentsmith >/dev/null || { echo "::error::agentsmith is not on PATH — run install-ai-stack.sh first" >&2; exit 1; }

mkdir -p "$TARGET"
cd "$TARGET"
[ -d .git ] || git init -q -b main --template=
git config user.name "$BOT"
git config user.email "scratch-tenants@users.noreply.github.com"
# A previous build armed the gates in this clone; the repository's own code is
# committed before they exist, as it was before adoption.
git config --unset core.hooksPath 2>/dev/null || true

# ── 1. A clean history ───────────────────────────────────────────────────────
git checkout -q --orphan scratch-rebuild
git rm -rq --cached . 2>/dev/null || true
find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +

# ── 2. The repository as it stood before adoption ────────────────────────────
# Files git would publish from adopted/, not the raw directory (as build.sh).
git -C "$SRC" ls-files -z --cached --others --exclude-standard . |
  while IFS= read -r -d '' f; do
    [ -f "$SRC/$f" ] || continue
    mkdir -p "$(dirname "$f")"
    cp -p "$SRC/$f" "$f"
  done
git add -A
git commit -q -m "feat: the ledger and its CI, before AgentSmith"
git branch -M main

# ── 3. Adopt it ──────────────────────────────────────────────────────────────
out="$(agentsmith tenant adopt scratch-adopted --framework-ref "$REF" --yes --root . 2>&1)" || {
  echo "$out" >&2
  echo "::error::tenant adopt failed" >&2
  exit 1
}

# ── 4. The adoption commit, as adopt printed it, through the gate ────────────
commit="$(printf '%s\n' "$out" | sed -n 's/^  \(git add -- .*\)$/\1/p' | head -n 1)"
if [ -z "$commit" ]; then
  echo "$out" >&2
  echo "::error::tenant adopt printed no commit command" >&2
  exit 1
fi
eval "$commit"
echo "adopted at $(git rev-parse --short HEAD): $(git log -1 --format=%s)"
