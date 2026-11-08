#!/usr/bin/env bash
# .github/scratch-tenants/build.sh — build one scratch tenant from its app
# source in this repository, with `agentsmith tenant init` from the AgentSmith
# INSTALLED on this machine (install-ai-stack.sh), its CI taking the provider
# from <framework-ref> — the commit under test.
#
#   usage: build.sh <app> <target-dir> <stack> <framework-ref> [profile]
#          app   = a directory under apps/ (ts-react, ts-react-pnpm, go,
#                  python-fastapi, python-uv). One stack can have several apps,
#                  one per scenario.
#          stack = python-fastapi | ts-react | go
#
# A scratch tenant is a pure OUTPUT: everything in it is a verbatim copy of
# .github/scratch-tenants/apps/<app>/, of the shared security-pack/ and
# SCRATCH_TENANT.md beside this script, or written by `tenant init`. So each
# build starts a fresh orphan history: the app is committed first, as a
# repository before AgentSmith, then scaffolded and committed with the command
# `tenant init` prints — through the tenant's own gate, which its CI then runs
# too. The workflow force-pushes the result (the repository is pure output). Until 3.0.0 the installed post-checkout hook did the scaffolding
# and vendored AgentSmith's code; 3.0.0 retired both
# (.agent-rfc/designs/vendoring-retired.md).
#
# <target-dir> may be an existing clone of the scratch repo (the workflow) or
# any directory (local use: it is git-initialised if needed).
#
# Fails (exit 1) when:
#   - the target's last commit was not made by the scratch-tenants workflow:
#     the repo was edited directly, and this build would silently discard that.
#     Move the change into apps/<app>/ instead, or set
#     SCRATCH_TENANTS_ALLOW_MANUAL_HEAD=1 to overwrite it deliberately.
#   - `tenant init` fails, or prints a warning (a line starting `  !`): a tenant
#     scaffolded from this install would be broken the same way.
#   - the scaffold changes the app's .gitignore, or leaves AgentSmith's code in
#     the tenant (`verify_system --governed`'s framework copies).

set -euo pipefail

USAGE="usage: build.sh <app> <target-dir> <stack> <framework-ref>"
APP_NAME="${1:?$USAGE}"
TARGET="${2:?$USAGE}"
STACK="${3:?$USAGE}"
REF="${4:?$USAGE}"
PROFILE="${5:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/apps/$APP_NAME"
WORKFLOW_AUTHOR="AgentSmith scratch-tenants"

[ -d "$APP" ] || { echo "::error::no app source '$APP_NAME' at $APP" >&2; exit 2; }
command -v agentsmith >/dev/null || { echo "::error::agentsmith is not on PATH — run install-ai-stack.sh first" >&2; exit 1; }

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

# ── 2. A fresh history: the app, before AgentSmith ───────────────────────────
git config user.name "$WORKFLOW_AUTHOR"
git config user.email "scratch-tenants@users.noreply.github.com"
# An earlier build armed .githooks; the app commit is made before the gates.
git config --unset core.hooksPath 2>/dev/null || true
git checkout -q --orphan scratch-rebuild
git rm -rq --cached . 2>/dev/null || true
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
# the security port, which fails on the shipped placeholders. Copied BEFORE the
# scaffold, so `tenant init`'s never-overwrite rule for the pack stays exercised.
mkdir -p .agent-rfc/security
cp "$HERE/security-pack/"*.yaml .agent-rfc/security/
# A profile's declaration, what a tenant writes when it goes on the profile.
if [ -n "$PROFILE" ]; then
  mkdir -p .agenticframework
  cp -R "$HERE/profiles/$PROFILE/agenticframework/." .agenticframework/
fi
find . -name __pycache__ -type d -not -path './node_modules/*' -prune -exec rm -rf {} +
git add -A
git commit -q -m "feat: the $APP_NAME app, before AgentSmith"
git branch -M main

# ── 3. Scaffold it ───────────────────────────────────────────────────────────
LOG="$(mktemp)"
if ! agentsmith tenant init "scratch-$APP_NAME" --stack "$STACK" --framework-ref "$REF" --root . ${PROFILE:+--profile "$PROFILE"} >"$LOG" 2>&1; then
  cat "$LOG"
  echo "::error::agentsmith tenant init failed for the $APP_NAME tenant"
  exit 1
fi
cat "$LOG"

# ── 4. Verify ────────────────────────────────────────────────────────────────
if grep -E "^  ! " "$LOG"; then
  echo "::error::tenant init could not fully scaffold the $APP_NAME tenant (see the lines above)"
  exit 1
fi
# Both directions: an app with no .gitignore (the go tenant) must not come out
# with one either.
if { [ -f "$APP/.gitignore" ] && ! cmp -s "$APP/.gitignore" .gitignore; } \
   || { [ ! -f "$APP/.gitignore" ] && [ -f .gitignore ]; }; then
  echo "::error::the scaffold changed .gitignore — the next commit would stop tracking files a real tenant tracks"
  diff "${APP}/.gitignore" .gitignore 2>/dev/null || cat .gitignore
  exit 1
fi
for dir in scripts agentsmith runtime fixtures/security .github/actions; do
  if [ -e "$dir" ] && [ ! -e "$APP/$dir" ]; then
    echo "::error::the scaffold wrote $dir/ — 3.0.0 vendors nothing into a tenant"
    exit 1
  fi
done

# ── 5. Commit the scaffold through the tenant's own gate ─────────────────────
commit="$(sed -n 's/^  \(git add -A && git commit .*\)$/\1/p' "$LOG" | head -n 1)"
if [ -z "$commit" ]; then
  echo "::error::tenant init printed no commit command for the $APP_NAME tenant"
  exit 1
fi
eval "$commit"
# ── 6. On a compliance profile: a conforming app passes, a broken one does not ──
if [ -n "$PROFILE" ]; then
  verdict() { agentsmith compliance check --stage production </dev/null | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["verdict"]); [print(x["id"], x["message"], file=sys.stderr) for x in r["rows"] if x["result"]=="fail"]'; }
  if [ "$(verdict)" != "pass" ]; then
    echo "::error::the $APP_NAME tenant does not meet the $PROFILE profile (see above)"
    exit 1
  fi
  BROKEN="$(mktemp -d)"
  cp -R . "$BROKEN/tenant"
  sed -i.bak 's/compliance=True/compliance=False/' "$BROKEN/tenant/app/workflows.py"
  if [ "$(cd "$BROKEN/tenant" && verdict 2>/dev/null)" != "fail" ]; then
    echo "::error::a tenant with its human gate removed still passes the $PROFILE profile"
    exit 1
  fi
  rm -rf "$BROKEN"
  echo "profile $PROFILE: the app passes, and passes no longer with its gate removed"
fi
echo "built $APP_NAME tenant at $TARGET: $(git log --oneline | wc -l | tr -d ' ') commits, head $(git log -1 --format=%s)"
