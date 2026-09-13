#!/usr/bin/env bash
# .github/scratch-tenants/build.sh — build one scratch tenant from its app
# source in this repository, using the AgentSmith INSTALLED on this machine
# (~/.agent-framework and ~/.git_templates/hooks, as install-ai-stack.sh
# writes them).
#
#   usage: build.sh <stack> <target-dir>
#          stack = ts-react | go | python-fastapi
#
# A scratch tenant is a pure OUTPUT: everything in it is either a verbatim copy
# of .github/scratch-tenants/apps/<stack>/ or produced by the post-checkout
# hook. So the build empties the target (keeping .git and its history), copies
# the app in, and fires the installed hook exactly as a checkout would. There
# is no list of "provisioned" vs "tenant-owned" paths to keep in step with the
# hook — the app source is the whole of what the tenant owns.
#
# <target-dir> may be an existing clone of the scratch repo (the workflow) or
# any directory (local use: it is git-initialised if needed).
#
# Fails (exit 1) when:
#   - the target's last commit was not made by the scratch-tenants workflow:
#     the repo was edited directly, and this build would silently discard that.
#     Move the change into apps/<stack>/ instead, or set
#     SCRATCH_TENANTS_ALLOW_MANUAL_HEAD=1 to overwrite it deliberately.
#   - the installed hook prints any column-0 warning (⚠️/❌): a tenant onboarded
#     from this install would be broken the same way.
#   - the hook changes the app's .gitignore: it could not confirm the repo is
#     private (is gh authenticated?), and the next commit would stop tracking
#     CLAUDE.md and friends.

set -euo pipefail

STACK="${1:?usage: build.sh <stack> <target-dir>}"
TARGET="${2:?usage: build.sh <stack> <target-dir>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/apps/$STACK"
HOOK="$HOME/.git_templates/hooks/post-checkout"
WORKFLOW_AUTHOR="AgentSmith scratch-tenants"

[ -d "$APP" ] || { echo "::error::no app source for stack '$STACK' at $APP" >&2; exit 2; }
[ -f "$HOOK" ] || { echo "::error::no installed hook at $HOOK — run install-ai-stack.sh first" >&2; exit 1; }

mkdir -p "$TARGET"
cd "$TARGET"
[ -d .git ] || git init -q -b main --template=

# ── 1. Refuse to overwrite a hand edit ───────────────────────────────────────
if git rev-parse --verify -q HEAD >/dev/null; then
  author="$(git log -1 --format=%an)"
  if [ "$author" != "$WORKFLOW_AUTHOR" ] && [ "${SCRATCH_TENANTS_ALLOW_MANUAL_HEAD:-0}" != "1" ]; then
    echo "::error::the last commit in $TARGET is by '$author', not '$WORKFLOW_AUTHOR' — the scratch repo was edited directly. Move that change into .github/scratch-tenants/apps/$STACK/ (or set SCRATCH_TENANTS_ALLOW_MANUAL_HEAD=1 to discard it)."
    exit 1
  fi
fi

# ── 2. Empty the tree, copy the app in ───────────────────────────────────────
find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "$APP/." .
cp "$HERE/SCRATCH_TENANT.md" SCRATCH_TENANT.md
mkdir -p .agenticframework
touch .agenticframework/enabled

# ── 3. Fire the installed hook, as `git checkout` would ──────────────────────
LOG="$(mktemp)"
bash "$HOOK" 2>&1 | tee "$LOG"

# ── 4. Verify ────────────────────────────────────────────────────────────────
# Every hook warning starts in column 0 with ⚠️ or ❌. The one benign note, the
# security pack's "These are PLACEHOLDERS" reminder, is indented. Matching the
# prefix, not a list of messages, covers warnings added to the hook later.
if grep -E "^(⚠️|❌)" "$LOG"; then
  echo "::error::the installed hook could not fully provision the $STACK tenant (see the lines above)"
  exit 1
fi
# Both directions: an app with no .gitignore (the go tenant) must not come out
# with one either — the hook creates the file when it appends.
if { [ -f "$APP/.gitignore" ] && ! cmp -s "$APP/.gitignore" .gitignore; } \
   || { [ ! -f "$APP/.gitignore" ] && [ -f .gitignore ]; }; then
  echo "::error::the hook changed .gitignore — it treated this repo as public. Is gh authenticated (GH_TOKEN)?"
  diff "${APP}/.gitignore" .gitignore 2>/dev/null || cat .gitignore
  exit 1
fi
find . -name __pycache__ -type d -not -path './node_modules/*' -prune -exec rm -rf {} +
echo "built $STACK tenant at $TARGET"
