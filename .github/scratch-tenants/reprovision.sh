#!/usr/bin/env bash
# .github/scratch-tenants/reprovision.sh — re-provision one scratch tenant from
# the AgentSmith that is INSTALLED on this machine (~/.agent-framework and
# ~/.git_templates/hooks, as written by install-ai-stack.sh).
#
#   usage: reprovision.sh <stack> <tenant-checkout>
#          stack = ts-react | go | python-fastapi
#
# The scratch tenants (docs/scratch-tenants.md) exist to exercise onboarding
# for real: each is a small app provisioned by the hook, whose own CI then runs
# on GitHub. The hook is seed-once and never overwrites, so re-running it over
# an already-provisioned repo proves nothing about the current framework.
# This script therefore first removes everything provisioning OWNS, keeps what
# the tenant owns, and then fires the installed hook exactly as a checkout would.
#
# What the tenant owns and is kept:
#   - its application files (anything not listed in PROVISIONED below)
#   - .agent-rfc/security/  — the authored security pack. Seeded once, then the
#     tenant's own document; the python-fastapi tenant's is filled in so its
#     strict harness is expected green.
#   - TENANT_OWNED_SCRIPTS  — per stack, files the tenant keeps in its own
#     scripts/ (the ts-react tenant keeps release.mjs precisely so the hook's
#     handling of a pre-existing scripts/ stays under test).
#
# Fails (exit 1) if the hook reports anything it could not provision: a warning
# there means every tenant onboarded from this install is broken the same way.

set -euo pipefail

STACK="${1:?usage: reprovision.sh <stack> <tenant-checkout>}"
TENANT="${2:?usage: reprovision.sh <stack> <tenant-checkout>}"
HOOK="$HOME/.git_templates/hooks/post-checkout"

case "$STACK" in
  ts-react)       TENANT_OWNED_SCRIPTS=(release.mjs) ;;
  go|python-fastapi) TENANT_OWNED_SCRIPTS=() ;;
  *) echo "unknown stack: $STACK" >&2; exit 2 ;;
esac

[ -f "$HOOK" ] || { echo "::error::no installed hook at $HOOK — run install-ai-stack.sh first" >&2; exit 1; }
[ -d "$TENANT/.git" ] || { echo "::error::$TENANT is not a git checkout" >&2; exit 1; }
cd "$TENANT"

# ── 1. Remove what provisioning owns ─────────────────────────────────────────
PROVISIONED=(.github runtime fixtures .agents .cursorrules CLAUDE.md AGENTS.md GEMINI.md .agent-history.log)
rm -rf "${PROVISIONED[@]}"
# .agent-rfc/ minus the authored security pack.
if [ -d .agent-rfc ]; then
  find .agent-rfc -mindepth 1 -maxdepth 1 ! -name security -exec rm -rf {} +
fi
if [ -d scripts ]; then
  KEEP_ARGS=()
  for f in "${TENANT_OWNED_SCRIPTS[@]+"${TENANT_OWNED_SCRIPTS[@]}"}"; do KEEP_ARGS+=(! -name "$f"); done
  find scripts -mindepth 1 -maxdepth 1 "${KEEP_ARGS[@]+"${KEEP_ARGS[@]}"}" -exec rm -rf {} +
  [ -n "$(ls -A scripts)" ] || rmdir scripts
fi
# The opt-in marker. Removed with nothing above, but a fresh checkout of a
# repo that lost it would be skipped by the hook's opt-in gate.
mkdir -p .agenticframework
touch .agenticframework/enabled

# ── 2. Fire the installed hook, as `git checkout` would ──────────────────────
LOG="$(mktemp)"
bash "$HOOK" 2>&1 | tee "$LOG"

# ── 3. Anything the hook could not provision is a framework failure ──────────
# Every hook warning starts in column 0 with ⚠️ (a missing install directory,
# a name clash in scripts/, a foreign runtime/, failed IDE config generation,
# a public-repo .gitignore rewrite). The one benign note — the security pack's
# "These are PLACEHOLDERS" reminder — is indented. Matching the prefix rather
# than a list of messages means a warning added to the hook later is covered.
if grep -E "^(⚠️|❌)" "$LOG"; then
  echo "::error::the installed hook could not fully provision the $STACK tenant (see the lines above)"
  exit 1
fi
# Non-interactively, a repo the hook cannot confirm is private (gh missing or
# unauthenticated) gets IDE config appended to .gitignore WITHOUT any message.
# The scratch repos are private; if this fires, gh auth is broken in the job,
# and the next commit would stop tracking CLAUDE.md and friends.
if [ -f .gitignore ] && ! git diff --quiet -- .gitignore && git diff -- .gitignore | grep -q "AgentSmith — IDE configs"; then
  echo "::error::the hook treated this private repo as public and rewrote .gitignore — is gh authenticated (GH_TOKEN)?"
  exit 1
fi
find . -name __pycache__ -type d -not -path './node_modules/*' -prune -exec rm -rf {} +
echo "re-provisioned $STACK tenant at $TENANT"
