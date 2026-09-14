
# >>> AgentSmith managed block — DO NOT EDIT, removed by ai-stack-uninstall >>>
# ══════════════════════════════════════════════════════════════════════════════
# AI AGENT FRAMEWORK CONTROLLER — AgentSmith v1.1.0
# ══════════════════════════════════════════════════════════════════════════════

# ── Environment defaults ──────────────────────────────────────────────────────
export AGENT_PHOENIX_ENDPOINT="${AGENT_PHOENIX_ENDPOINT:-http://localhost:6006}"
export AGENT_PHOENIX_PORT="${AGENT_PHOENIX_PORT:-6006}"
# AGENT_JUDGE_MODEL is deliberately NOT defaulted here. It is an *override*:
# scripts/_shared.py:judge_model() checks it first, then falls back to the
# `judge` role in models.yaml. Exporting a default from the shell profile
# would silently win over every tenant's declared judge route, machine-wide —
# which is what the old hardcoded `claude-3-5-sonnet-20241022` here did (a
# model id already stale against the framework registry). Set it by hand for a
# one-off run; change the `judge` role in models.yaml for a lasting choice.
export AI_STACK_MODE="${AI_STACK_MODE:-local}"
export DISABLE_AI_STACK="${DISABLE_AI_STACK:-false}"

# ── Mode: Local offline (Ollama) ──────────────────────────────────────────────
function ai-mode-local() {
  export AI_STACK_MODE="local"
  export DISABLE_AI_STACK="false"
  export OS_LLM_BASE_URL="http://localhost:11434/v1"
  export OS_LLM_API_KEY="ollama"
  git config --global init.templateDir "$HOME/.git_templates"
  echo "🍃 AI Stack: LOCAL OFFLINE mode activated (Ollama)"
  ai-stack-check
  if [ $? -eq 0 ]; then
    python3 -c "
from plyer import notification
notification.notify(title='AgentSmith', message='Local offline mode active', timeout=4)
" 2>/dev/null || true
  fi
}

# ── Mode: Hybrid cloud ────────────────────────────────────────────────────────
function ai-mode-hybrid() {
  export AI_STACK_MODE="hybrid"
  export DISABLE_AI_STACK="false"
  export OS_LLM_BASE_URL="${OS_LLM_BASE_URL:-https://api.groq.com/openai/v1}"
  git config --global init.templateDir "$HOME/.git_templates"
  echo "💎 AI Stack: HYBRID CLOUD mode activated (Claude + cost routing)"
  ai-stack-check
  if [ $? -eq 0 ]; then
    python3 -c "
from plyer import notification
notification.notify(title='AgentSmith', message='Hybrid cloud mode active', timeout=4)
" 2>/dev/null || true
  fi
}

# ── Mode: Off ─────────────────────────────────────────────────────────────────

# Minimal "key: value" reader for the small, flat org policy schema (no
# nested-list parsing needed) — same pragmatic approach as agent_logger.py's
# regex YAML fallback when pyyaml isn't available. $1 is the key (e.g.
# "bypass_policy"); searches only within the "hooks:" block.
function _ai_org_policy_get() {
  local key="$1"
  local policy_file="$HOME/.agent-framework/agenticframework-org.yaml"
  [ -f "$policy_file" ] || return 1
  awk -v key="$key" '
    /^hooks:/ { in_hooks=1; next }
    /^[a-zA-Z]/ && !/^hooks:/ { in_hooks=0 }
    in_hooks && $0 ~ "^[[:space:]]+"key":" {
      sub("^[[:space:]]+"key":[[:space:]]*", "");
      gsub(/^\[|\]$/, "");           # strip YAML inline-list brackets, e.g. ["a","b"] -> "a","b"
      gsub(/"/, "");                 # strip quotes
      gsub(/,[[:space:]]*/, ", ");   # normalise list separators for display
      print;
      exit
    }
  ' "$policy_file"
}

# Validates a break-glass token's HMAC signature and expiry — same
# HMAC-over-shared-secret pattern already used for widget tokens (hashed,
# portal/lib/widgetTokens.ts) and the audit log's tamper-evident signatures
# (portal/lib/auditLog.ts), instead of accepting any non-empty string as a
# valid token (Product_Archive.md 1.5 — the control was a UI speed bump,
# not a real gate). Token format: "<actor>:<expires_epoch>.<hex_hmac_sha256>",
# issued by IT and signed with BREAK_GLASS_HMAC_KEY (a secret IT controls,
# distributed out-of-band — never the same value as AI_BREAK_GLASS_TOKEN
# itself, which is the per-use token, not the signing key).
function _ai_validate_break_glass_token() {
  local token="$1"
  local key="${BREAK_GLASS_HMAC_KEY:-}"
  if [ -z "$key" ]; then
    echo "🛑 Break-glass tokens cannot be validated on this machine (BREAK_GLASS_HMAC_KEY not configured)."
    echo "   Contact IT to provision this machine before break-glass bypass can be used."
    return 1
  fi
  if [ "${token%.*}" = "$token" ] || [ -z "${token##*.}" ]; then
    echo "🛑 Malformed break-glass token (expected <actor>:<expires_epoch>.<signature>)."
    return 1
  fi
  local payload="${token%.*}" sig="${token##*.}"
  local expected
  expected="$(printf '%s' "$payload" | openssl dgst -sha256 -hmac "$key" 2>/dev/null | sed 's/^.* //')"
  if [ -z "$expected" ] || [ "$expected" != "$sig" ]; then
    echo "🛑 Break-glass token signature is invalid — this is not a token IT issued."
    return 1
  fi
  local expiry="${payload##*:}"
  if ! [[ "$expiry" =~ ^[0-9]+$ ]] || [ "$(date +%s)" -gt "$expiry" ]; then
    echo "🛑 Break-glass token has expired. Request a new one from IT."
    return 1
  fi
  return 0
}

function ai-stack-off() {
  local bypass_policy
  bypass_policy="$(_ai_org_policy_get bypass_policy)"

  if [ "$bypass_policy" = "disabled" ]; then
    local approvers
    approvers="$(_ai_org_policy_get break_glass_approvers)"
    echo "🛑 Enterprise policy: hook bypass is DISABLED (bypass_policy: disabled)."
    echo "   Contact IT for a break-glass procedure: ${approvers:-it-sec@example.com}"
    _ai_audit_log_event "hook_bypass" "${AGENT_OWNER_ID:-unknown}" "" \
      "{\"result\":\"denied\",\"policy\":\"disabled\"}"
    return 1
  fi

  if [ "$bypass_policy" = "break-glass" ]; then
    if [ -z "${AI_BREAK_GLASS_TOKEN:-}" ]; then
      local approvers
      approvers="$(_ai_org_policy_get break_glass_approvers)"
      echo "🛑 Enterprise policy: hook bypass requires a break-glass token."
      echo "   Request one from: ${approvers:-it-sec@example.com}, then re-run with:"
      echo "   AI_BREAK_GLASS_TOKEN=<token> ai-stack-off"
      _ai_audit_log_event "hook_bypass" "${AGENT_OWNER_ID:-unknown}" "" \
        "{\"result\":\"denied\",\"policy\":\"break-glass\",\"reason\":\"no_token\"}"
      return 1
    fi
    if ! _ai_validate_break_glass_token "${AI_BREAK_GLASS_TOKEN}"; then
      _ai_audit_log_event "hook_bypass" "${AGENT_OWNER_ID:-unknown}" "" \
        "{\"result\":\"denied\",\"policy\":\"break-glass\",\"reason\":\"invalid_token\"}"
      return 1
    fi
    echo "⚠️  Break-glass bypass used — this is logged to the enterprise audit log."
    _ai_audit_log_event "hook_bypass" "${AGENT_OWNER_ID:-unknown}" "" \
      "{\"result\":\"approved\",\"policy\":\"break-glass\"}"
  fi

  export DISABLE_AI_STACK="true"
  export AI_STACK_MODE="disabled"
  git config --global --unset init.templateDir 2>/dev/null || true
  echo "🔒 AI Stack: DISABLED — hooks muted, templates unlinked"
}

# ── Model registry lookup ─────────────────────────────────────────────────────
# The Ollama model ids models.yaml routes to, whitespace-separated. Single
# source: scripts/_shared.py:provider_models() performs the same framework ←
# tenant ← routing_overrides merge the gateway does, so this shell function and
# the Python side can never name different models.
#
# Prints nothing on any failure (no python3, no runtime/, unreadable YAML); the
# caller falls back to its own literal list, so a health check never becomes a
# hard dependency on the runtime being installed.
function ai-stack-judge-model() {
  # Resolve the judge the way the code does, rather than echoing
  # AGENT_JUDGE_MODEL. The registry now wins over that variable, so printing
  # the raw value showed an empty judge on a machine where one is perfectly
  # well configured — and before the precedence changed it showed a judge that
  # silently overrode every repo's declared role. cwd-aware: inside a tenant
  # repo this reports that tenant's judge.
  local shared="$HOME/.agent-framework/scripts/_shared.py"
  [ -f "$shared" ] || shared="${AGENTSMITH_DIR:-$HOME/.agent-framework}/scripts/_shared.py"
  [ -f "$shared" ] || return 0
  python3 -c "
import sys
sys.path.insert(0, '$(dirname "$shared")')
try:
    from _shared import judge_model
    print(judge_model())
except Exception:
    pass
" 2>/dev/null
}

function ai-stack-required-models() {
  local shared="$HOME/.agent-framework/scripts/_shared.py"
  [ -f "$shared" ] || shared="${AGENTSMITH_DIR:-$HOME/.agent-framework}/scripts/_shared.py"
  [ -f "$shared" ] || return 0
  python3 -c "
import sys
sys.path.insert(0, '$(dirname "$shared")')
try:
    from _shared import provider_models
    print(' '.join(provider_models('ollama')))
except Exception:
    pass
" 2>/dev/null
}

# ── Health check ──────────────────────────────────────────────────────────────
function ai-stack-check() {
  echo "🩺 AgentSmith Health Check — Mode: [${AI_STACK_MODE:-not set}]"
  local failed=0

  # Phoenix connectivity
  if curl -s -o /dev/null -w "%{http_code}" "${AGENT_PHOENIX_ENDPOINT}" 2>/dev/null | grep -qE "^(200|301|302)"; then
    echo "   ✅ [TRACER]  Phoenix is live at ${AGENT_PHOENIX_ENDPOINT}"
  else
    echo "   ⚠️  [TRACER]  Phoenix is offline. Run: ai-dashboard-start"
    failed=1
  fi

  # Mode-specific checks
  if [ "${AI_STACK_MODE:-local}" = "local" ]; then
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
      echo "   ✅ [ENGINE]  Ollama daemon responding"
      local models required
      models=$(curl -s http://localhost:11434/api/tags 2>/dev/null)
      # Read the required models FROM models.yaml rather than listing them
      # here. A hand-maintained copy drifts: this one still said
      # llama3/mistral/gemma2 long after the registry moved on, so it told
      # users to pull models nothing routes to while the ones the gateway
      # needs went unchecked. `ai-stack-check` runs from the user's shell in
      # any directory, so the lookup is cwd-aware — inside a tenant repo it
      # picks up that tenant's own models.yaml overrides too.
      required=$(ai-stack-required-models)
      # Literal fallback only when the registry can't be read at all. Keep it
      # equal to models.yaml's ollama roles — it is a safety net, not a second
      # source of truth.
      [ -n "$required" ] || required="qwen2.5 llama3.2:3b falcon3:3b smollm2"
      for m in $required; do
        # Exact id, or the same id with an implicit ":latest" tag — not a
        # substring match, which is why "llama3" used to report present just
        # because llama3.2:latest happened to be installed.
        if echo "$models" | grep -qE "\"name\":\"${m}(:latest)?\""; then
          echo "   ✅ [MODEL]   $m loaded"
        else
          echo "   ⚠️  [MODEL]   $m not found — run: ollama pull $m"
          failed=1
        fi
      done
    else
      echo "   ❌ [ENGINE]  Ollama is offline — run: ollama serve"
      failed=1
    fi

  elif [ "${AI_STACK_MODE:-local}" = "hybrid" ]; then
    [ -z "${ANTHROPIC_API_KEY:-}" ] && { echo "   ⚠️  [CLOUD]   ANTHROPIC_API_KEY not set"; failed=1; } || echo "   ✅ [CLOUD]   Anthropic key present"
    [ -z "${OPENAI_API_KEY:-}" ]    && { echo "   ⚠️  [CLOUD]   OPENAI_API_KEY not set";    failed=1; } || echo "   ✅ [CLOUD]   OpenAI key present"
  fi

  # Unresolved MAJOR/CRITICAL log entries in current project
  if [ -f ".agent-history.log" ]; then
    local unresolved
    unresolved=$(python3 -c "
import json, sys
count = 0
entries = []
with open('.agent-history.log') as f:
    for line in f:
        try:
            e = json.loads(line.strip())
            if e.get('level') in ('MAJOR','CRITICAL') and not e.get('hitl_resolved', True):
                count += 1
                entries.append(f\"   [{e['level']}] {e.get('timestamp','')}  {e.get('event','')}  ({e.get('agent','')} / {e.get('project','')})\" )
        except (json.JSONDecodeError, KeyError): pass
if count:
    print(f'   🔴 Unresolved MAJOR/CRITICAL issues: {count}')
    for e in entries: print(e)
    print(\"   → Run 'ai-stack-promote' or resolve via Phoenix UI.\")
    sys.exit(1)
" 2>/dev/null)
    if [ $? -ne 0 ]; then
      echo "$unresolved"
      failed=1
    fi
  fi

  if [ -n "${OPS_PORTAL_URL:-}" ]; then
    python3 scripts/sync-portal-history.py 2>/dev/null || \
      python3 "$HOME/.agent-framework/scripts/sync-portal-history.py" 2>/dev/null || true
  fi

  if [ "$failed" -eq 0 ]; then
    echo "   🎉 All checks passed — environment ready"
    return 0
  else
    echo "   🛑 Health check failed — resolve issues above before running agents"
    return 1
  fi
}

# ── Status ────────────────────────────────────────────────────────────────────
function ai-stack-status() {
  echo "────────────────────────────────────────────────"
  echo "  Mode:      ${AI_STACK_MODE:-not set}"
  echo "  Hooks:     ${DISABLE_AI_STACK:-false} (muted=true means off)"
  echo "  Phoenix:   ${AGENT_PHOENIX_ENDPOINT}"
  echo "  Judge:     $(ai-stack-judge-model)   (from models.yaml, not the environment)"
  echo "  Owner:     ${AGENT_OWNER_ID:-not set}"
  if ping -c 1 -W 1 1.1.1.1 > /dev/null 2>&1; then
    echo "  Network:   🌐 ONLINE"
  else
    echo "  Network:   ❌ OFFLINE (local fallback armed)"
  fi
  echo "────────────────────────────────────────────────"
}

# ── Dashboard ─────────────────────────────────────────────────────────────────
# Per-repo opt-out (Product_Archive.md P0.5c): a repo with this marker is
# treated as fully standalone — ai-dashboard-start falls back to the plain-
# process Phoenix launch even when the shared stack is available, so this
# repo's traces/work never touch the machine-wide stack at all.
function _ai_repo_opts_out_of_shared_infra() {
  [ -f ".agenticframework/no-shared-infra" ]
}

function ai-dashboard-start() {
  local observability_compose="$HOME/.agent-framework/observability/docker-compose.yml"

  if _ai_repo_opts_out_of_shared_infra; then
    info "This repo has .agenticframework/no-shared-infra — using a standalone Phoenix instance, not the shared stack."
  fi

  if command_exists docker && [ -f "$observability_compose" ] && ! _ai_repo_opts_out_of_shared_infra; then
    echo "📊 Starting the standing stack (Phoenix + Postgres + Ops Portal)..."
    ( cd "$(dirname "$observability_compose")" && docker compose up -d )
    export OTEL_EXPORTER_OTLP_ENDPOINT="${AGENT_PHOENIX_ENDPOINT}/v1/traces"
    echo "🚀 Phoenix    → open ${AGENT_PHOENIX_ENDPOINT}"
    echo "🚀 Ops Portal → open http://localhost:${OPS_PORTAL_PORT:-3000}"
    echo "   (shared across every repo on this machine — opt out per-repo with:"
    echo "    touch .agenticframework/no-shared-infra)"
    return 0
  fi

  # Fallback: no Docker, stack not vendored yet, or this repo opted out —
  # the original plain-process launch. No Postgres, no Ops Portal, not
  # shared with other repos.
  # Phoenix is a server, not a library the framework imports, so it is not in
  # the framework environment: uvx runs it in its own cached one — the same
  # "latest" the Docker stack's image tracks. The old `python3 -m
  # phoenix.server.main launch` needed Phoenix in the system interpreter, and
  # current Phoenix has no `launch` subcommand at all.
  if ! command -v uvx >/dev/null 2>&1; then
    echo "❌ Standalone Phoenix needs uv (uvx): brew install uv — or install Docker for the shared stack."
    return 1
  fi
  echo "📊 Starting Arize Phoenix at ${AGENT_PHOENIX_ENDPOINT} (standalone — no Docker stack)..."
  local db_arg=""
  [ -n "${AGENT_PHOENIX_DB_URL:-}" ] && db_arg="--database-url ${AGENT_PHOENIX_DB_URL}"
  uvx --from arize-phoenix phoenix serve \
    --port "${AGENT_PHOENIX_PORT:-6006}" \
    ${db_arg} &
  export OTEL_EXPORTER_OTLP_ENDPOINT="${AGENT_PHOENIX_ENDPOINT}/v1/traces"
  sleep 1
  echo "🚀 Dashboard live → open ${AGENT_PHOENIX_ENDPOINT}"
}

function ai-dashboard-stop() {
  local observability_compose="$HOME/.agent-framework/observability/docker-compose.yml"

  if command_exists docker && [ -f "$observability_compose" ]; then
    echo "🔒 Stopping the standing stack (Phoenix + Postgres + Ops Portal)..."
    # No -v: named volumes (traces, portal data) persist — this is meant to
    # survive being stopped and restarted, not be reset every time.
    ( cd "$(dirname "$observability_compose")" && docker compose down )
    unset OTEL_EXPORTER_OTLP_ENDPOINT
    echo "✅ Stack offline (data preserved — 'docker compose down -v' there to wipe it)"
    return 0
  fi

  echo "🔒 Stopping Phoenix..."
  # Either launch: `phoenix serve` (uvx) or an older install's phoenix.server.main.
  pkill -f "phoenix serve" 2>/dev/null || true
  pkill -f "phoenix.server.main" 2>/dev/null || true
  unset OTEL_EXPORTER_OTLP_ENDPOINT
  echo "✅ Dashboard offline"
}

# ── Evaluations & self-improvement ────────────────────────────────────────────
function ai-test-evals() {
  if ! curl -s "${AGENT_PHOENIX_ENDPOINT}" > /dev/null 2>&1; then
    echo "🔄 Phoenix offline — starting dashboard first..."
    ai-dashboard-start
    sleep 2
  fi
  echo "🔄 Syncing HITL feedback from Phoenix UI..."
  python3 scripts/sync-ui-feedback.py 2>/dev/null || \
    python3 "$HOME/.agent-framework/scripts/sync-ui-feedback.py" 2>/dev/null || true
  echo "🎯 Running eval scorecard..."
  python3 scripts/run-evals.py 2>/dev/null || \
    python3 "$HOME/.agent-framework/scripts/run-evals.py"
}

function ai-stack-promote() {
  if [ -z "${3:-}" ]; then
    echo "❌ Usage: ai-stack-promote <case-id> '<input query>' '<correct output>'"
    return 1
  fi
  python3 scripts/promote-learning.py "$1" "$2" "$3" 2>/dev/null || \
    python3 "$HOME/.agent-framework/scripts/promote-learning.py" "$1" "$2" "$3"
  echo "🔄 Re-running evals to validate fix..."
  ai-test-evals
}

# ── Tenant lifecycle (§6, §23, §24) ──────────────────────────────────────────
# Best-effort audit log write (SPECS.md §30, enterprise pack). No-op unless
# OPS_PORTAL_URL and AUDIT_LOG_WRITE_TOKEN are set — never blocks or fails
# the calling command if the portal is unreachable or unconfigured.
function _ai_audit_log_event() {
  local event_type="$1" actor_id="$2" tenant_id="$3" details_json="$4"
  local local_log="$HOME/.agent-framework/local-audit-fallback.log"

  # SPECS.md §30 promises "all bypass events are written to the immutable
  # audit log" — unconditionally, not "when the Ops Portal happens to be
  # configured and reachable". Previously a missing OPS_PORTAL_URL/
  # AUDIT_LOG_WRITE_TOKEN, or `|| true` swallowing a curl failure, dropped
  # the event with zero error and zero record anywhere (Product_Archive.md
  # 1.6). This keeps the "never block the calling command" design (the
  # bypass/promotion/etc. still proceeds either way) but now always leaves a
  # local trace when the remote write didn't happen, so a hook_bypass under
  # break-glass can be reconciled against this file later instead of vanishing.
  if [ -z "${OPS_PORTAL_URL:-}" ] || [ -z "${AUDIT_LOG_WRITE_TOKEN:-}" ]; then
    mkdir -p "$(dirname "$local_log")" 2>/dev/null
    printf '{"timestamp":"%s","eventType":"%s","actorId":"%s","tenantId":"%s","details":%s,"reason":"ops_portal_not_configured"}\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$event_type" "$actor_id" "$tenant_id" "$details_json" >> "$local_log" 2>/dev/null
    return 0
  fi

  if ! curl -s -m 5 -o /dev/null -w "%{http_code}" -X POST "${OPS_PORTAL_URL%/}/api/audit/append" \
    -H "Authorization: Bearer ${AUDIT_LOG_WRITE_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"eventType\":\"${event_type}\",\"actorId\":\"${actor_id}\",\"tenantId\":\"${tenant_id}\",\"details\":${details_json}}" \
    2>/dev/null | grep -q "^2"; then
    mkdir -p "$(dirname "$local_log")" 2>/dev/null
    printf '{"timestamp":"%s","eventType":"%s","actorId":"%s","tenantId":"%s","details":%s,"reason":"ops_portal_write_failed"}\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$event_type" "$actor_id" "$tenant_id" "$details_json" >> "$local_log" 2>/dev/null
  fi
  return 0
}

function ai-tenant-init() {
  # DELEGATES to the CLI. This was ~130 lines of shell that also lived in the
  # installer, so editing the repo left every machine writing the previous
  # scaffold — observed twice in one day. The logic is now in runtime/cli.py
  # where a test can reach it, and this stays only so muscle memory keeps
  # working. Prefer `agentsmith tenant init` directly.
  if command -v agentsmith >/dev/null 2>&1; then
    agentsmith tenant init "$@"
  elif python3 -c "import runtime.cli" >/dev/null 2>&1; then
    python3 -m runtime.cli tenant init "$@"
  else
    echo "❌ agentsmith CLI not found. Install the runtime package:" >&2
    echo "     pip install agentsmith-runtime" >&2
    echo "   or run from a checkout with AGENTSMITH_DIR on PYTHONPATH." >&2
    return 1
  fi
}

# Opt-in — copies the stack-agnostic on-prem/air-gapped deployment template
# (Docker Compose + Traefik/Envoy canary+shadow routing, Helm chart for
# K8s) into THIS repo's deploy/onprem/ — never run automatically by
# ai-tenant-init, since not every tenant has an on-prem customer. See
# templates/onprem-deploy/README.md for the app contract this template
# assumes (single image, GET /healthz, env-var-only config, stdout logs).
function ai-onprem-deploy-scaffold() {
  if [ ! -d ".git" ]; then
    echo "❌ Not a git repository — run inside the tenant repo root"
    return 1
  fi

  local src="$HOME/.agent-framework/templates/onprem-deploy"
  if [ ! -d "$src" ]; then
    echo "❌ No onprem-deploy template at $src — run install-ai-stack.sh first"
    return 1
  fi

  local dest="deploy/onprem"
  if [ -d "$dest" ]; then
    echo "⚠️  $dest already exists — leaving untouched. Delete it first to re-scaffold."
    return 1
  fi

  mkdir -p "deploy"
  cp -r "$src" "$dest"

  _ai_audit_log_event "onprem_deploy_scaffolded" "${AGENT_OWNER_ID:-unknown}" "$(basename "$(pwd)")" "{}"

  echo "🏗  Scaffolded on-prem deployment template at $dest/"
  echo "   Next: cp $dest/.env.example $dest/.env, set APP_IMAGE_PROD, then"
  echo "   $dest/scripts/up.sh — see $dest/README.md for the canary/shadow/"
  echo "   air-gapped bundling workflow and $dest/kubernetes/README.md for Helm."
}

function ai-tenant-promote() {
  local tenant_id="${1:-}"
  local from_env="" to_env=""
  [ $# -gt 0 ] && shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --from) from_env="${2:-}"; shift 2 ;;
      --to)   to_env="${2:-}"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [ -z "$tenant_id" ] || [ -z "$from_env" ] || [ -z "$to_env" ]; then
    echo "❌ Usage: ai-tenant-promote <id> --from <env> --to <env>"
    return 1
  fi
  if [ "$from_env" != "staging" ] || [ "$to_env" != "production" ]; then
    echo "❌ Only staging → production promotion is supported (no cross-tenant or cross-stage jumps)"
    return 1
  fi

  if [ ! -f ".agenticframework/tenant.yaml" ]; then
    echo "❌ No .agenticframework/tenant.yaml in current repo — run from the tenant repo root"
    return 1
  fi
  # Exact match on the parsed field, not a substring grep: "id: acme" would
  # previously also match "id: acme-sandbox" or "id: acme2", letting
  # ai-tenant-promote run against the wrong tenant's repo if it happened to
  # share a prefix (Product_Archive.md 1.4). Same field-parsing approach as
  # ai-stack-upgrade's tenant_id extraction further down this file.
  local actual_tenant_id
  actual_tenant_id="$(grep '^  id:' .agenticframework/tenant.yaml | head -1 | sed 's/^  id:[[:space:]]*//')"
  if [ "$actual_tenant_id" != "$tenant_id" ]; then
    echo "❌ tenant.yaml id ('${actual_tenant_id}') does not match '${tenant_id}' — promotion is always within the same tenant repo"
    return 1
  fi

  echo "🔎 Verifying staging eval gate..."
  AGENT_PHOENIX_ENDPOINT="${AGENT_PHOENIX_ENDPOINT:-http://localhost:6006}" \
    python3 scripts/run-evals.py --fail-below 0.75 2>/dev/null || \
    python3 "$HOME/.agent-framework/scripts/run-evals.py" --fail-below 0.75
  if [ $? -ne 0 ]; then
    echo "🛑 Staging eval gate failed — promotion blocked"
    return 1
  fi
  echo "✅ Staging eval gate passed"

  if ! command -v gh > /dev/null 2>&1; then
    echo "❌ gh CLI required to open the develop → main promotion PR"
    return 1
  fi

  echo "🚀 Opening promotion PR: develop → main for tenant '$tenant_id'..."
  gh pr create \
    --title "promote(${tenant_id}): staging → production" \
    --body "Auto-generated by ai-tenant-promote. Staging eval gate passed. Requires review approval before merge (see SPECS.md §24)." \
    --base main \
    --head develop

  _ai_audit_log_event "hitl_promotion" "${AGENT_OWNER_ID:-unknown}" "$tenant_id" \
    "{\"from\":\"${from_env}\",\"to\":\"${to_env}\"}"
}

# ── Maintenance ───────────────────────────────────────────────────────────────
function ai-stack-scrub() {
  local target_dir="${1:-$PWD}"
  if [ ! -d "$target_dir" ]; then
    echo "❌ Directory not found: $target_dir"
    return 1
  fi

  # Find every match FIRST and show the exact paths before asking — a
  # confirmation that only names the top-level directory (e.g. "$HOME")
  # gives no idea that -maxdepth 3 reaches across every sibling project's
  # .cursorrules/CLAUDE.md/AGENTS.md/GEMINI.md/.agents/ underneath it (Product_Archive.md
  # 4.11). Note: .agent-history.log was listed in the old warning text but
  # never actually matched/removed by any command below — that mismatch is
  # dropped here rather than carried forward or silently "fixed" by adding
  # a deletion nobody asked to verify the blast radius of.
  local matches
  matches="$(
    {
      find "$target_dir" -maxdepth 3 -name ".cursorrules"
      find "$target_dir" -maxdepth 3 -name "CLAUDE.md"
      find "$target_dir" -maxdepth 3 -name "AGENTS.md"
      find "$target_dir" -maxdepth 3 -name "GEMINI.md"
      # The FILE only, never the .github directory around it — that holds
      # workflows this command has no business touching.
      find "$target_dir" -maxdepth 4 -path "*/.github/copilot-instructions.md"
      find "$target_dir" -maxdepth 3 -type d -name ".agents"
    } 2>/dev/null
  )"

  if [ -z "$matches" ]; then
    echo "✨ Nothing to scrub under $target_dir"
    return 0
  fi

  local match_count
  match_count="$(echo "$matches" | wc -l | tr -d ' ')"
  echo "🧹 WARNING: This will permanently delete the following paths:"
  echo "$matches" | sed 's/^/   /'
  read -r -p "   Confirm deletion of the ${match_count} path(s) above? (y/n): " CHOICE
  if [[ "${CHOICE:-n}" =~ ^[Yy]$ ]]; then
    echo "$matches" | while IFS= read -r path; do
      [ -n "$path" ] && rm -rf "$path" && echo "   removed: $path"
    done
    echo "✨ Scrub complete — framework re-provisions on next git init"
  else
    echo "❌ Cancelled"
  fi
}

function ai-stack-uninstall() {
  echo "🗑  AgentSmith: Enterprise-safe machine-level uninstall"
  echo "   This will:"
  echo "   - Remove the AgentSmith block from ~/.zshrc (or ~/.bashrc / ~/.profile)"
  echo "   - Restore git init.templateDir to its pre-install value (or unset it)"
  echo "   - Optionally remove ~/.agent-framework and ~/.git_templates"
  echo ""

  local framework_dir="$HOME/.agent-framework"
  local org_policy="$framework_dir/agenticframework-org.yaml"
  if [ -f "$org_policy" ] && grep -q "bypass_policy: disabled" "$org_policy" 2>/dev/null; then
    echo "⚠️  This machine has an enterprise org policy with bypass_policy: disabled."
    echo "   Uninstalling removes hook enforcement entirely — this is NOT a sanctioned"
    echo "   break-glass bypass and will not be silent: IT should be notified separately."
  fi

  read -r -p "   Confirm uninstall? (y/n): " CHOICE
  if [[ ! "${CHOICE:-n}" =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    return 1
  fi

  # ── Restore (not just unset) git init.templateDir ──────────────────────────
  local prev_template_dir=""
  [ -f "$framework_dir/previous_template_dir" ] && prev_template_dir="$(cat "$framework_dir/previous_template_dir")"
  if [ -n "$prev_template_dir" ]; then
    git config --global init.templateDir "$prev_template_dir"
    echo "✅ Restored git init.templateDir → $prev_template_dir"
  else
    git config --global --unset init.templateDir 2>/dev/null || true
    echo "✅ Unset git init.templateDir (no prior value was recorded)"
  fi

  # ── Remove the managed block from the shell rc file ────────────────────────
  local shell_rc="$HOME/.zshrc"
  [ -f "$shell_rc" ] || shell_rc="$HOME/.bashrc"
  [ -f "$shell_rc" ] || shell_rc="$HOME/.profile"
  if [ -f "$shell_rc" ] && grep -qE ">>> (AgentSmith|AgenticFramework) managed block" "$shell_rc" 2>/dev/null; then
    # Anchored to whole lines — this very line contains the marker text, and an
    # unanchored range stopped here, leaving the rest of the block installed.
    sed -i.af-uninstall-bak '/^# >>> AgentSmith managed block/,/^# <<< AgentSmith managed block <<<$/d' "$shell_rc"
    sed -i.af-uninstall-bak '/^# >>> AgenticFramework managed block/,/^# <<< AgenticFramework managed block <<<$/d' "$shell_rc"
    rm -f "${shell_rc}.af-uninstall-bak"
    echo "✅ Removed AgentSmith block from $shell_rc"
  else
    echo "⚠️  No AgentSmith managed block found in $shell_rc — skipping"
  fi

  # ── Optionally remove framework directories ────────────────────────────────
  read -r -p "   Also remove ~/.agent-framework and ~/.git_templates? (y/n): " CHOICE2
  if [[ "${CHOICE2:-n}" =~ ^[Yy]$ ]]; then
    rm -rf "$framework_dir" "$HOME/.git_templates"
    echo "✅ Removed ~/.agent-framework and ~/.git_templates"
  else
    echo "ℹ️  Left ~/.agent-framework and ~/.git_templates in place"
  fi

  echo ""
  echo "🎯 Uninstall complete. Restart your shell to clear the unloaded functions."
}

function ai-stack-upgrade() {
  local target_version="${FRAMEWORK_VERSION:-1.1.0}"
  while [ $# -gt 0 ]; do
    case "$1" in
      --to) target_version="${2:-$target_version}"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [ ! -f ".agenticframework/tenant.yaml" ]; then
    echo "❌ No .agenticframework/tenant.yaml in current repo — run from the tenant repo root"
    return 1
  fi
  if [ ! -d ".git" ]; then
    echo "❌ Not a git repository"
    return 1
  fi

  # Same guard as hooks/post-checkout's "installed mode": a tenant that depends
  # on agentsmith-runtime as a package upgrades by bumping that pin. Vendoring
  # runtime/ into its root would shadow the pinned package.
  # `find -exec`, not a `requirements*.txt` glob: unmatched, zsh aborts the function.
  if find . -maxdepth 1 \( -name 'requirements*.txt' -o -name pyproject.toml \) \
       -exec grep -qsE '^[[:space:]"'"'"']*agentsmith-runtime' {} \; -print 2>/dev/null | grep -q .; then
    echo "ℹ️  This repo depends on agentsmith-runtime as a package — nothing to vendor."
    echo "   Upgrade by bumping the agentsmith-runtime pin (and framework.version in tenant.yaml) instead."
    return 0
  fi

  local vendor_src="$HOME/.agent-framework/scripts"
  if [ ! -d "$vendor_src" ] || [ -z "$(ls -A "$vendor_src" 2>/dev/null)" ]; then
    echo "❌ No vendored scripts found at $vendor_src — run install-ai-stack.sh on this machine first"
    return 1
  fi

  echo "📦 Upgrading vendored scripts to v${target_version}..."
  mkdir -p "scripts"
  # The framework's own test suite and fixtures (~2MB) — a tenant runs its
  # own tests, not AgentSmith's, and has no use for them. Same exclusion
  # hooks/post-checkout applies on first vendor, so the two paths agree.
  # Pruned in a staging copy, NOT after copying into scripts/: `rm -rf
  # scripts/test` there deleted a tenant's OWN scripts/test/ on every upgrade.
  local stage
  stage="$(mktemp -d)"
  cp -r "$vendor_src/." "$stage/"
  rm -rf "$stage/test"
  find "$stage" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
  cp -r "$stage/." "scripts/"
  local vendored_scripts
  vendored_scripts="$(cd "$stage" && find . -type f | sed 's|^\./||')"
  rm -rf "$stage"
  echo "✅ Copied vendored scripts from $vendor_src"

  # runtime/ and fixtures/security/. runtime/test/ is pruned to the suites the
  # security harness delegates to — the same list, and the same reason, as
  # TENANT_RUNTIME_TESTS in hooks/post-checkout; an upgrade also removes the
  # rest from a tenant that was vendored the whole directory. Optional — an
  # install predating this step should not block an otherwise-working scripts/
  # upgrade.
  local tenant_runtime_tests="conftest.py test_hitl_gate.py test_dead_letter.py test_llm_gateway_budget.py test_self_correction.py"
  local runtime_src="$HOME/.agent-framework/runtime"
  if [ -d "runtime" ] && [ ! -f "runtime/llm_gateway.py" ]; then
    # Same guard as hooks/post-checkout: a tenant's own `runtime` package is
    # never merged into.
    echo "⚠️  runtime/ exists and is not AgentSmith's — NOT upgraded. Rename yours, or install"
    echo "   AgentSmith's runtime as a package; scripts/ will import YOUR runtime.* meanwhile."
  elif [ -d "$runtime_src" ] && [ -n "$(ls -A "$runtime_src" 2>/dev/null)" ]; then
    mkdir -p "runtime"
    cp -r "$runtime_src/." "runtime/"
    find "runtime" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    rm -rf "runtime/.hitl_blobs"
    rm -rf "runtime/test"
    mkdir -p "runtime/test"
    local suite
    for suite in $(echo "$tenant_runtime_tests"); do
      [ -f "$runtime_src/test/$suite" ] && cp "$runtime_src/test/$suite" "runtime/test/$suite"
    done
    echo "✅ Copied vendored runtime/ from $runtime_src"
  else
    echo "⚠️  No vendored runtime/ found at $runtime_src — skipping. Re-run"
    echo "   install-ai-stack.sh from a live checkout to pick it up."
  fi

  # Regenerate the lint-isolation config hooks/post-checkout writes (see
  # write_vendored_ruff_config there), so newly vendored files are excluded
  # too. Only a file AgentSmith wrote, or none: a tenant's own directory
  # config is never touched.
  local af_dir af_list af_extend
  for af_dir in scripts runtime; do
    [ -d "$af_dir" ] || continue
    if [ "$af_dir" = "scripts" ]; then
      af_list="$vendored_scripts"
    else
      [ -f "runtime/llm_gateway.py" ] || continue
      af_list="$(cd runtime && find . -type f ! -name ruff.toml | sed 's|^\./||')"
    fi
    if [ -f "$af_dir/ruff.toml" ] && ! grep -q '^# Written by AgentSmith' "$af_dir/ruff.toml"; then continue; fi
    if [ -f "$af_dir/.ruff.toml" ] || [ -f "$af_dir/pyproject.toml" ]; then continue; fi
    af_extend=""
    if [ -f "ruff.toml" ]; then af_extend='extend = "../ruff.toml"'
    elif [ -f ".ruff.toml" ]; then af_extend='extend = "../.ruff.toml"'
    elif [ -f "pyproject.toml" ] && grep -q '^\[tool\.ruff' pyproject.toml; then af_extend='extend = "../pyproject.toml"'
    fi
    {
      echo "# Written by AgentSmith when it vendored $af_dir/ — see hooks/post-checkout."
      echo "# Excludes the vendored files from this repo's ruff check/format; your own"
      echo "# files here keep your rules. ai-stack-upgrade regenerates this file."
      [ -n "$af_extend" ] && echo "$af_extend"
      echo "extend-exclude = ["
      printf '%s\n' "$af_list" | grep -v '^$' | sort | sed 's/"/\\"/g; s/.*/  "&",/'
      echo "]"
    } > "$af_dir/ruff.toml"
  done

  local fixtures_security_src="$HOME/.agent-framework/fixtures/security"
  if [ -d "$fixtures_security_src" ] && [ -n "$(ls -A "$fixtures_security_src" 2>/dev/null)" ]; then
    mkdir -p "fixtures/security"
    cp -r "$fixtures_security_src/." "fixtures/security/"
    echo "✅ Copied vendored fixtures/security/ from $fixtures_security_src"
  else
    echo "⚠️  No vendored fixtures/security/ found at $fixtures_security_src — skipping."
  fi
  # `find`, not a glob: this function runs in the user's zsh, where an
  # unmatched glob in a `for` aborts the whole function — an install without
  # base fixtures would have stopped the upgrade before it committed.
  local base_fixture
  find "$HOME/.agent-framework/fixtures" -maxdepth 1 -type f -name '*_base.json' 2>/dev/null |
    while IFS= read -r base_fixture; do
      mkdir -p "fixtures"
      cp "$base_fixture" "fixtures/"
    done

  sed -i.af-upgrade-bak "s/^  version: .*/  version: \"${target_version}\"/" ".agenticframework/tenant.yaml"
  rm -f ".agenticframework/tenant.yaml.af-upgrade-bak"
  echo "✅ Updated .agenticframework/tenant.yaml -> framework.version: \"${target_version}\""

  # Built conditionally: `git add`/`git diff` on a pathspec that matched
  # nothing (runtime/ or fixtures/security/ skipped above, e.g. an install
  # predating this step) aborts the WHOLE command rather than just that path.
  local vendor_paths=(scripts .agenticframework/tenant.yaml)
  [ -f "runtime/llm_gateway.py" ] && vendor_paths+=(runtime)  # never a tenant's own runtime/
  [ -d "fixtures/security" ] && vendor_paths+=(fixtures/security)
  # A quoted glob is a git pathspec — the base fixtures only, never the rest of
  # a tenant's own fixtures/.
  [ -n "$(find fixtures -maxdepth 1 -type f -name '*_base.json' 2>/dev/null)" ] && vendor_paths+=("fixtures/*_base.json")

  # `git status --porcelain`, not `git diff --quiet`: diff ignores untracked
  # files, so a first-time vendor (runtime/ on an install that predated it, a
  # new base fixture) reported "No changes" and was never committed.
  if [ -z "$(git status --porcelain -- "${vendor_paths[@]}")" ]; then
    echo "ℹ️  No changes — ${vendor_paths[*]} already match v${target_version}"
    return 0
  fi

  git add "${vendor_paths[@]}"
  if ! git commit -m "chore(framework): upgrade AgentSmith to v${target_version}"; then
    echo "❌ git commit failed (blocked by a hook, GPG-sign required and unavailable, etc.) —"
    echo "   scripts/ and tenant.yaml were updated and staged but NOT committed. Fix the issue and re-run:"
    echo "   git commit -m \"chore(framework): upgrade AgentSmith to v${target_version}\""
    return 1
  fi
  echo "✅ Committed: chore(framework): upgrade AgentSmith to v${target_version}"

  local tenant_id
  tenant_id="$(grep '^  id:' .agenticframework/tenant.yaml | head -1 | sed 's/^  id:[[:space:]]*//')"
  _ai_audit_log_event "config_change" "${AGENT_OWNER_ID:-unknown}" "$tenant_id" \
    "{\"action\":\"framework_upgrade\",\"version\":\"${target_version}\"}"

  echo ""
  echo "🎯 Upgrade complete. Push and open a PR per your branch protection rules (no direct push to main)."
}

# ══════════════════════════════════════════════════════════════════════════════
# <<< AgentSmith managed block <<<
