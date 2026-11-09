#!/usr/bin/env bash
# scripts/check_tenant_upgrade.sh [previous-tag] [candidate-tree] — a tenant on the
# last release moves to this commit, as it would for real
# (.agent-rfc/designs/tenant-upgrade-test.md).
#
# Scratch tenants are rebuilt from HEAD, so they cannot see what breaks a tenant that
# already exists. Both trees come from `git archive`, so nothing untracked in this
# checkout answers for them. The environment is the one agentsmith-sync.yml builds.
set -uo pipefail

fail() { echo "❌ tenant upgrade: $*" >&2; exit 1; }
step() { echo "── $*"; }

repo="$(git rev-parse --show-toplevel)" || fail "not in a git repository"
candidate="${2:-HEAD}"
previous="${1:-}"
if [ -z "$previous" ]; then
  # The newest release that is not this commit: a release's own build compares to the one before.
  head_sha="$(git -C "$repo" rev-parse HEAD)"
  while IFS= read -r tag; do
    if [ "$(git -C "$repo" rev-parse "$tag^{commit}")" != "$head_sha" ]; then previous="$tag"; break; fi
  done < <(git -C "$repo" tag --merged HEAD --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$')
fi
[ -n "$previous" ] || fail "no earlier release tag: this check needs the tags (fetch-depth: 0)"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/old" "$work/new" "$work/home"
git -C "$repo" archive "$previous" | tar -x -C "$work/old" || fail "could not export $previous"
git -C "$repo" archive "$candidate" | tar -x -C "$work/new" || fail "could not export $candidate"

step "the environment agentsmith-sync.yml builds"
python3 -m venv "$work/env" || fail "could not make a virtual environment"
"$work/env/bin/pip" install -q -r "$work/new/scripts/requirements-gate.txt" pyyaml > "$work/pip.log" 2>&1 \
  || { cat "$work/pip.log" >&2; fail "could not install the gate's requirements"; }
# Only the system's tools, git and this environment: an `agentsmith` already installed on the
# machine running the check must not answer for either release.
git_dir="$(dirname "$(command -v git)")"
export PATH="$work/env/bin:$git_dir:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="$work/home"
unset AGENTSMITH_DIR PYTHONPATH CLAUDE_PROJECT_DIR GITHUB_STEP_SUMMARY AGENTSMITH_PYTHON
git config --global user.name "upgrade check"
git config --global user.email "upgrade-check@example.com"
git config --global init.defaultBranch main

# Each release answers as `agentsmith`, which is what a tenant's hooks call, as the
# setup action installs it in CI.
for tree in old new; do
  mkdir -p "$work/bin-$tree"
  printf '#!/bin/sh\nexec python3 -P -m agentsmith.cli "$@"\n' > "$work/bin-$tree/agentsmith"
  chmod +x "$work/bin-$tree/agentsmith"
done
with_old() { PATH="$work/bin-old:$PATH" AGENTSMITH_DIR="$work/old" PYTHONPATH="$work/old" "$@"; }
with_new() { PATH="$work/bin-new:$PATH" AGENTSMITH_DIR="$work/new" PYTHONPATH="$work/new" "$@"; }
printed_commit() { grep -E '^ *git add ' "$1" | tail -1; }
released="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$work/new/pyproject.toml" | head -n 1)"

# A port that answers "no" is fine on an untouched scaffold. One that cannot answer is not.
answers() { # <port label> <log>
  if grep -q "Traceback" "$2"; then cat "$2" >&2; fail "$1 crashed"; fi
}

upgrade() { # <name> <init|adopt>
  local name="$1" how="$2" dir="$work/$1"
  mkdir "$dir" && cd "$dir" && git init -q || fail "$name: git init"
  mkdir app && echo 'print("hello")' > app/main.py && echo 'fastapi==0.115.0' > requirements.txt
  git add -A && git commit -q -m "feat: an app" || fail "$name: the app's own commit"

  step "$name: scaffolded by $previous"
  if [ "$how" = init ]; then
    with_old python3 -P -m agentsmith.cli tenant init my-app --stack python-fastapi </dev/null > "$work/$name.init" 2>&1
  else
    with_old python3 -P -m agentsmith.cli tenant adopt my-app --yes </dev/null > "$work/$name.init" 2>&1
  fi || { cat "$work/$name.init" >&2; fail "$name: $previous could not scaffold it"; }
  local first; first="$(printed_commit "$work/$name.init")"
  [ -n "$first" ] || { cat "$work/$name.init" >&2; fail "$name: nothing printed to commit"; }
  with_old bash -c "$first" > "$work/$name.first" 2>&1 \
    || { cat "$work/$name.first" >&2; fail "$name: its first commit was refused"; }

  step "$name: synced to this commit"
  with_new python3 -P -m agentsmith.cli sync --yes </dev/null > "$work/$name.sync" 2>&1 \
    || { cat "$work/$name.sync" >&2; fail "$name: sync failed"; }
  grep -q "setup-agentsmith@v$released\"" .agenticframework/providers.json \
    || { grep setup .agenticframework/providers.json >&2; fail "$name: the pin is not v$released"; }
  if [ "$how" = init ]; then
    python3 - <<'PY' || fail "$name: sync dropped what tenant init declared"
import json
providers = json.load(open(".agenticframework/providers.json"))["providers"]
assert providers["evals"].get("not_gradable"), "the warnings for a suite with no data"
assert providers["evals"].get("no_verdict"), "the warnings for a suite with no judge"
assert providers["security"].get("emitter") == "none", "the telemetry emitter"
PY
  fi

  step "$name: the sync commit goes through its gates, as the workflow makes it"
  git add -A
  with_new git commit -q -m "chore(framework): sync AgentSmith candidate" \
    -m "Design: .agent-rfc/designs/adoption.md" -m "Review: n/a: framework sync candidate" > "$work/$name.commit" 2>&1 \
    || { cat "$work/$name.commit" >&2; fail "$name: the sync commit was refused"; }
  with_new bash .githooks/process-gate ci --base HEAD~1 --head HEAD </dev/null > "$work/$name.ci" 2>&1 \
    || { cat "$work/$name.ci" >&2; fail "$name: the gate refused it in CI"; }

  step "$name: its ports still answer"
  with_new bash .githooks/process-gate rules check </dev/null > "$work/$name.rules" 2>&1 \
    || { cat "$work/$name.rules" >&2; fail "$name: rule files are not current after a sync"; }
  with_new bash .githooks/process-gate kg check </dev/null > "$work/$name.kg" 2>&1 \
    || { cat "$work/$name.kg" >&2; fail "$name: the knowledge graph is stale after a sync"; }
  git checkout -q -- . 2>/dev/null
  with_new bash .githooks/process-gate security check </dev/null > "$work/$name.security" 2>&1
  grep -q "SEC-RISK-001" "$work/$name.security" || { cat "$work/$name.security" >&2; fail "$name: the security port gave no answer"; }
  answers "$name: the security port" "$work/$name.security"
  with_new bash .githooks/process-gate evals run --suite golden </dev/null > "$work/$name.evals" 2>&1
  local evals=$?
  answers "$name: the evals port" "$work/$name.evals"
  if [ "$how" = init ] && [ "$evals" -ne 0 ]; then
    cat "$work/$name.evals" >&2; fail "$name: a new repository's evals went red after a sync"
  fi
  git checkout -q -- . 2>/dev/null

  step "$name: nothing else moved, and the profile stayed out"
  with_new python3 -P -m agentsmith.cli sync --yes </dev/null > "$work/$name.sync2" 2>&1 \
    || { cat "$work/$name.sync2" >&2; fail "$name: a second sync failed"; }
  [ -z "$(git status --porcelain)" ] || { git status --short >&2; fail "$name: a second sync changed something"; }
  [ ! -e .agenticframework/compliance.json ] || fail "$name: a tenant that did not ask got the compliance profile"
  grep -q '"compliance"' .agenticframework/process-gates.json .agenticframework/providers.json \
    && fail "$name: a tenant that did not ask is declared on the profile"

  step "$name: it can still go on the profile"
  with_new python3 -P -m agentsmith.cli compliance enable --profile dubai-gov </dev/null > "$work/$name.enable" 2>&1 \
    || { cat "$work/$name.enable" >&2; fail "$name: compliance enable failed"; }
  with_new bash .githooks/process-gate compliance check </dev/null > "$work/$name.compliance" 2>&1
  grep -q "obligation" "$work/$name.compliance" || { cat "$work/$name.compliance" >&2; fail "$name: the compliance port gave no answer"; }
  answers "$name: the compliance port" "$work/$name.compliance"
}

upgrade created init
cd "$repo" || exit 1
upgrade adopted adopt

echo "✅ tenant upgrade: $previous moves to $candidate, by init and by adopt"
