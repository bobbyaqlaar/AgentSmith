#!/usr/bin/env bash
# scripts/check_release_install.sh <release-url> — a stranger's first ten minutes,
# run for real against a release: <release-url> is a directory of published assets,
# https://… or file://… . Nothing of this checkout is used: an empty HOME, an empty
# working directory, and only what the release serves
# (.agent-rfc/designs/release-install-path.md).
#
# Passes only if the README's Quick Start works: the checksum verifies, the install
# succeeds, `tenant init` and `tenant adopt` each take the commit they print, and
# every port answers. Self-Test runs it on built assets, release.yml on the real URL.
set -uo pipefail

base="${1:?usage: check_release_install.sh <release-url>}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/dl" "$work/home" "$work/elsewhere"

fail() { echo "❌ release install: $*" >&2; exit 1; }
step() { echo "── $*"; }

step "fetch the installer and verify its checksum"
(cd "$work/dl" \
  && curl -fsSL -o install-ai-stack.sh "$base/install-ai-stack.sh" \
  && curl -fsSL -o install-ai-stack.sh.sha256 "$base/install-ai-stack.sh.sha256" \
  && shasum -a 256 --check install-ai-stack.sh.sha256) || fail "could not fetch or verify the installer at $base"

export HOME="$work/home"
unset AGENTSMITH_DIR PYTHONPATH CLAUDE_PROJECT_DIR GITHUB_STEP_SUMMARY
export PATH="$HOME/.local/bin:$PATH"
git config --global user.name "release check"
git config --global user.email "release-check@example.com"
git config --global init.defaultBranch main

step "install, from an unrelated directory"
(cd "$work/elsewhere" && AI_STACK_RELEASE_BASE="$base" bash "$work/dl/install-ai-stack.sh" </dev/null) \
  > "$work/install.log" 2>&1 || { tail -30 "$work/install.log" >&2; fail "the installer failed"; }
agentsmith version >/dev/null || fail "no agentsmith command after the install"
if grep -q "Not running from a local checkout" "$work/install.log"; then
  fail "the installer reports a partial install"
fi

# The commit a command prints is the one a user runs: `git add -- … && git commit …`.
printed_commit() { grep -E '^ *git add ' "$1" | tail -1; }

step "a new repository: tenant init, then the commit it prints"
mkdir "$work/new" && cd "$work/new" && git init -q || fail "git init"
agentsmith tenant init my-project --stack python-fastapi </dev/null > "$work/init.log" 2>&1 \
  || { cat "$work/init.log" >&2; fail "tenant init failed"; }
command="$(printed_commit "$work/init.log")"
[ -n "$command" ] || { cat "$work/init.log" >&2; fail "tenant init printed no commit"; }
bash -c "$command" > "$work/commit.log" 2>&1 || { cat "$work/commit.log" >&2; fail "the commit tenant init printed was refused"; }

step "its ports answer"
# An untouched scaffold fails on its placeholders, by design. What must not happen
# is a provider that cannot answer at all.
bash .githooks/process-gate security check </dev/null > "$work/security.log" 2>&1
grep -q "SEC-RISK-001" "$work/security.log" || { cat "$work/security.log" >&2; fail "the security port gave no answer"; }
if grep -q "Traceback" "$work/security.log"; then cat "$work/security.log" >&2; fail "the security port crashed"; fi
bash .githooks/process-gate evals run --suite golden </dev/null > "$work/evals.log" 2>&1 \
  || { cat "$work/evals.log" >&2; fail "the evals port failed on a new repository"; }
bash .githooks/process-gate rules check </dev/null > "$work/rules.log" 2>&1 \
  || { cat "$work/rules.log" >&2; fail "the rules port failed"; }
bash .githooks/process-gate kg check </dev/null > "$work/kg.log" 2>&1 \
  || { cat "$work/kg.log" >&2; fail "kg check failed"; }

step "an existing repository: tenant adopt, then the commit it prints"
mkdir "$work/old" && cd "$work/old" && git init -q || fail "git init"
mkdir app && echo 'print("hello")' > app/main.py && echo 'fastapi' > requirements.txt
git add -A && git commit -q -m "feat: an app that predates AgentSmith" || fail "the app's own commit"
agentsmith tenant adopt my-app --yes </dev/null > "$work/adopt.log" 2>&1 \
  || { cat "$work/adopt.log" >&2; fail "tenant adopt failed"; }
command="$(printed_commit "$work/adopt.log")"
[ -n "$command" ] || { cat "$work/adopt.log" >&2; fail "tenant adopt printed no commit"; }
bash -c "$command" > "$work/commit.log" 2>&1 || { cat "$work/commit.log" >&2; fail "the commit tenant adopt printed was refused"; }

echo "✅ release install: the Quick Start works from $base"
