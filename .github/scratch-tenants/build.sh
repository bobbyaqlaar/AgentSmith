#!/usr/bin/env bash
# .github/scratch-tenants/build.sh — build one scratch tenant from its app
# source in this repository, using the AgentSmith INSTALLED on this machine
# (~/.agent-framework and ~/.git_templates/hooks, as install-ai-stack.sh
# writes them).
#
#   usage: build.sh <app> <target-dir>
#          app = a directory under apps/ (ts-react, ts-react-pnpm, go,
#                python-fastapi, python-uv). One stack can have several apps,
#                one per scenario; the hook detects the stack from the files.
#
# A scratch tenant is a pure OUTPUT: everything in it is a verbatim copy of
# .github/scratch-tenants/apps/<app>/, of the shared security-pack/ and
# SCRATCH_TENANT.md beside this script, or produced by the post-checkout hook.
# So the build empties the target (keeping .git and its history), copies those
# in, and fires the installed hook exactly as a checkout would. There is no
# list of "provisioned" vs "tenant-owned" paths to keep in step with the hook.
#
# <target-dir> may be an existing clone of the scratch repo (the workflow) or
# any directory (local use: it is git-initialised if needed).
#
# Fails (exit 1) when:
#   - the target's last commit was not made by the scratch-tenants workflow:
#     the repo was edited directly, and this build would silently discard that.
#     Move the change into apps/<app>/ instead, or set
#     SCRATCH_TENANTS_ALLOW_MANUAL_HEAD=1 to overwrite it deliberately.
#   - the installed hook prints any column-0 warning (⚠️/❌): a tenant onboarded
#     from this install would be broken the same way.
#   - the hook changes the app's .gitignore: it did not honour the declared
#     AGENTSMITH_TENANT_VISIBILITY=private, and the next commit would stop
#     tracking CLAUDE.md and friends.

set -euo pipefail

APP_NAME="${1:?usage: build.sh <app> <target-dir>}"
TARGET="${2:?usage: build.sh <app> <target-dir>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/apps/$APP_NAME"
HOOK="$HOME/.git_templates/hooks/post-checkout"
WORKFLOW_AUTHOR="AgentSmith scratch-tenants"

[ -d "$APP" ] || { echo "::error::no app source '$APP_NAME' at $APP" >&2; exit 2; }
[ -f "$HOOK" ] || { echo "::error::no installed hook at $HOOK — run install-ai-stack.sh first" >&2; exit 1; }

mkdir -p "$TARGET"
cd "$TARGET"
[ -d .git ] || git init -q -b main --template=

# ── 1. Refuse to overwrite a hand edit ───────────────────────────────────────
if git rev-parse --verify -q HEAD >/dev/null; then
  author="$(git log -1 --format=%an)"
  if [ "$author" != "$WORKFLOW_AUTHOR" ] && [ "${SCRATCH_TENANTS_ALLOW_MANUAL_HEAD:-0}" != "1" ]; then
    echo "::error::the last commit in $TARGET is by '$author', not '$WORKFLOW_AUTHOR' — the scratch repo was edited directly. Move that change into .github/scratch-tenants/apps/$APP_NAME/ (or set SCRATCH_TENANTS_ALLOW_MANUAL_HEAD=1 to discard it)."
    exit 1
  fi
fi

# ── 2. Empty the tree, copy the app in ───────────────────────────────────────
find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
# Files git would publish (tracked, or new and not ignored), not the raw
# directory: `cp -R` also copied a local node_modules/ or .ruff_cache/, so a
# build on a developer machine differed from the workflow's clean checkout.
git -C "$APP" ls-files -z --cached --others --exclude-standard . |
  while IFS= read -r -d '' f; do
    [ -f "$APP/$f" ] || continue   # deleted in the working tree, not yet committed
    mkdir -p "$(dirname "$f")"
    cp -p "$APP/$f" "$f"
  done
cp "$HERE/SCRATCH_TENANT.md" SCRATCH_TENANT.md
# The authored security pack, one copy for every app — every stack's CI runs
# the strict harness, which fails on the shipped placeholders. Copied BEFORE
# the hook, so the hook's never-overwrite rule for the pack stays exercised.
mkdir -p .agent-rfc/security
cp "$HERE/security-pack/"*.yaml .agent-rfc/security/
mkdir -p .agenticframework
touch .agenticframework/enabled

# ── 3. Fire the installed hook, as `git checkout` would ──────────────────────
# A real tenant is private and TRACKS its IDE config files. These fixture repos
# are public — so their CI runs on free standard-runner minutes — and the hook
# would therefore gitignore CLAUDE.md, .cursorrules and friends, leaving a
# fixture on the opposite branch of the visibility decision from every tenant
# it stands in for. Declaring the intent keeps the fixture faithful without
# making it depend on where it happens to be hosted
# (.agent-rfc/designs/tenant-visibility-override.md). The .gitignore check in
# step 4 is what proves this reached the hook.
export AGENTSMITH_TENANT_VISIBILITY=private
LOG="$(mktemp)"
bash "$HOOK" 2>&1 | tee "$LOG"

# ── 4. Verify ────────────────────────────────────────────────────────────────
# Every hook warning starts in column 0 with ⚠️ or ❌. The one benign note, the
# security pack's "These are PLACEHOLDERS" reminder, is indented. Matching the
# prefix, not a list of messages, covers warnings added to the hook later.
if grep -E "^(⚠️|❌)" "$LOG"; then
  echo "::error::the installed hook could not fully provision the $APP_NAME tenant (see the lines above)"
  exit 1
fi
# Both directions: an app with no .gitignore (the go tenant) must not come out
# with one either — the hook creates the file when it appends.
if { [ -f "$APP/.gitignore" ] && ! cmp -s "$APP/.gitignore" .gitignore; } \
   || { [ ! -f "$APP/.gitignore" ] && [ -f .gitignore ]; }; then
  echo "::error::the hook changed .gitignore — it did not honour AGENTSMITH_TENANT_VISIBILITY=private, so this fixture would stop tracking the IDE config files a real tenant tracks"
  diff "${APP}/.gitignore" .gitignore 2>/dev/null || cat .gitignore
  exit 1
fi
find . -name __pycache__ -type d -not -path './node_modules/*' -prune -exec rm -rf {} +
echo "built $APP_NAME tenant at $TARGET"
