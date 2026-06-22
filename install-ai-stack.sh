#!/usr/bin/env bash
# =============================================================================
#  AgenticFramework Installer — v1.0.0
#  https://github.com/<org>/AgenticFramework
#
#  Installs once per machine. Safe to re-run (idempotent).
#  Supports macOS, Linux, and Windows (via WSL/Git Bash).
#
#  Usage:
#    curl -fsSL https://raw.githubusercontent.com/<org>/AgenticFramework/main/install-ai-stack.sh | bash
#    # or, from a cloned repo:
#    chmod +x install-ai-stack.sh && ./install-ai-stack.sh
# =============================================================================

set -uo pipefail

# ── Constants ─────────────────────────────────────────────────────────────────

FRAMEWORK_VERSION="1.0.0"
FRAMEWORK_REPO="https://github.com/<org>/AgenticFramework"
FRAMEWORK_DIR="$HOME/.agent-framework"
TEMPLATE_DIR="$HOME/.git_templates"
SCRIPTS_DIR="$FRAMEWORK_DIR/scripts"
SHARED_DIR="$FRAMEWORK_DIR/shared"
WORKFLOW_TEMPLATES_DIR="$FRAMEWORK_DIR/workflow-templates"

# Detect shell profile file
if [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "${SHELL:-}")" = "zsh" ]; then
  SHELL_RC="$HOME/.zshrc"
elif [ -n "${BASH_VERSION:-}" ]; then
  SHELL_RC="$HOME/.bashrc"
else
  SHELL_RC="$HOME/.profile"
fi

# ── Colours ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}ℹ${RESET}  $*"; }
success() { echo -e "${GREEN}✅${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠️ ${RESET} $*"; }
error()   { echo -e "${RED}❌${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}${CYAN}$*${RESET}"; echo "────────────────────────────────────────────────"; }

# ── Helpers ───────────────────────────────────────────────────────────────────

command_exists() { command -v "$1" &>/dev/null; }

# Detect OS
detect_os() {
  case "$(uname -s)" in
    Darwin) echo "macos"  ;;
    Linux)  echo "linux"  ;;
    CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
    *) echo "unknown" ;;
  esac
}

OS=$(detect_os)

# ── Banner ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}"
echo "   ___                  _   _     ___                                  _   "
echo "  / _ \                | | (_)   / __)                                | |  "
echo " / /_\ \ __ _  ___ _ __| |_ _  | |__ _ __ __ _ _ __ ___   _____      ___ ___ _ __| | __"
echo " |  _  |/ _\` |/ _ \ '_ \  _| | |  __| '__/ _\` | '_ \` _ \ / _ \ \ /\ / / / __| '__| |/ /"
echo " | | | | (_| |  __/ | | | |_| | | |  | | | (_| | | | | | |  __/\ V  V /| \__ \ |  |   < "
echo " \_| |_/\__, |\___|_| |_|\__|_| |_|  |_|  \__,_|_| |_| |_|\___| \_/\_/ |_|___/_|  |_|\_\\"
echo "         __/ |"
echo "        |___/    v${FRAMEWORK_VERSION} — One install. Every agent. Every project."
echo -e "${RESET}"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — PREREQUISITE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 1: Checking Prerequisites"

PREREQ_FAILED=0

# Python 3.11+
if command_exists python3; then
  PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
  if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
    success "Python $PY_VERSION"
  else
    error "Python 3.11+ required (found $PY_VERSION)"
    PREREQ_FAILED=1
  fi
else
  error "Python 3 not found. Install from https://python.org"
  PREREQ_FAILED=1
fi

# Git
if command_exists git; then
  GIT_VERSION=$(git --version | awk '{print $3}')
  success "Git $GIT_VERSION"
else
  error "Git not found. Install from https://git-scm.com"
  PREREQ_FAILED=1
fi

# pip
if command_exists pip3 || python3 -m pip --version &>/dev/null; then
  success "pip available"
else
  error "pip not found. Install pip: https://pip.pypa.io"
  PREREQ_FAILED=1
fi

# Ollama (optional — warn only)
if command_exists ollama; then
  success "Ollama $(ollama --version 2>/dev/null | head -1)"
else
  warn "Ollama not found — required for local offline mode. Install from https://ollama.com"
fi

# Docker (optional — warn only)
if command_exists docker; then
  success "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
else
  warn "Docker not found — required for team-shared Phoenix. Install from https://docker.com"
fi

if [ "$PREREQ_FAILED" -eq 1 ]; then
  error "Fix the errors above and re-run the installer."
  exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — DIRECTORY SETUP
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 2: Creating Framework Directories"

mkdir -p "$FRAMEWORK_DIR"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$SHARED_DIR"
mkdir -p "$WORKFLOW_TEMPLATES_DIR"
mkdir -p "$TEMPLATE_DIR/hooks"
success "~/.agent-framework/ structure created"

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PYTHON DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 3: Installing Python Dependencies"

info "Installing packages (this may take a few minutes)..."

PACKAGES=(
  "arize-phoenix>=4.0"
  "opentelemetry-sdk"
  "opentelemetry-exporter-otlp-proto-http"
  "openinference-instrumentation-openai"
  "openinference-instrumentation-anthropic"
  "openinference-instrumentation-langchain"
  "langgraph>=0.2"
  "langchain-core"
  "langchain-openai"
  "langchain-anthropic"
  "langchain-community"
  "networkx>=3.0"
  "tiktoken"
  "httpx"
  "plyer"
  "tenacity"
  "prophet"
  "pyyaml"
  "psycopg2-binary"
)

# Build pip install command
PIP_ARGS=("${PACKAGES[@]}")

if python3 -m pip install "${PIP_ARGS[@]}" --quiet 2>&1; then
  success "All Python dependencies installed"
else
  # Retry with --break-system-packages for system Python environments
  warn "Retrying with --break-system-packages..."
  if python3 -m pip install "${PIP_ARGS[@]}" --break-system-packages --quiet 2>&1; then
    success "All Python dependencies installed (system Python)"
  else
    error "Failed to install Python dependencies. Check pip output above."
    exit 1
  fi
fi

# Pin installed versions to requirements.lock
python3 -m pip freeze > "$FRAMEWORK_DIR/requirements.lock"
success "Pinned versions saved to ~/.agent-framework/requirements.lock"

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SCRIPTS INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 4: Installing Agent Scripts"

# Determine installer location
INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/scripts" ]; then
  # Running from cloned repo — copy local scripts
  cp -r "$INSTALLER_DIR/scripts/." "$SCRIPTS_DIR/"
  success "Scripts copied from local repo"
elif [ -d "$SCRIPTS_DIR" ] && [ "$(ls -A "$SCRIPTS_DIR" 2>/dev/null)" ]; then
  success "Scripts already present in ~/.agent-framework/scripts/"
else
  # Download from GitHub releases
  info "Downloading scripts from GitHub..."
  SCRIPTS_URL="${FRAMEWORK_REPO}/releases/latest/download/scripts.tar.gz"
  if command_exists curl; then
    if curl -fsSL "$SCRIPTS_URL" | tar -xz -C "$SCRIPTS_DIR" 2>/dev/null; then
      success "Scripts downloaded from GitHub"
    else
      warn "Could not download scripts from GitHub. Manual copy may be needed."
      warn "Clone the repo and re-run: git clone ${FRAMEWORK_REPO} && ./AgenticFramework/install-ai-stack.sh"
    fi
  fi
fi

if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/workflow-templates" ]; then
  cp -r "$INSTALLER_DIR/workflow-templates/." "$WORKFLOW_TEMPLATES_DIR/"
  success "Workflow templates copied from local repo"
elif [ -d "$WORKFLOW_TEMPLATES_DIR" ] && [ "$(ls -A "$WORKFLOW_TEMPLATES_DIR" 2>/dev/null)" ]; then
  success "Workflow templates already present in ~/.agent-framework/workflow-templates/"
else
  info "Downloading workflow-templates from GitHub..."
  WORKFLOW_TEMPLATES_URL="${FRAMEWORK_REPO}/releases/latest/download/workflow-templates.tar.gz"
  if command_exists curl && curl -fsSL "$WORKFLOW_TEMPLATES_URL" | tar -xz -C "$WORKFLOW_TEMPLATES_DIR" 2>/dev/null; then
    success "Workflow templates downloaded from GitHub"
  else
    warn "No workflow-templates found to install — ai-tenant-init will fail until they're added to ~/.agent-framework/workflow-templates/"
  fi
fi

# agent-rules.yaml — single source of truth for .cursorrules/CLAUDE.md/Antigravity
# skill generation (SPECS.md §4, §13, §22 Phase 5). The post-checkout hook reads
# it from here via scripts/generate-ide-config.py.
mkdir -p "$FRAMEWORK_DIR/templates"
if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/templates/agent-rules.yaml" ]; then
  cp "$INSTALLER_DIR/templates/agent-rules.yaml" "$FRAMEWORK_DIR/templates/agent-rules.yaml"
  success "agent-rules.yaml copied from local repo"
elif [ -f "$FRAMEWORK_DIR/templates/agent-rules.yaml" ]; then
  success "agent-rules.yaml already present in ~/.agent-framework/templates/"
else
  info "Downloading agent-rules.yaml from GitHub..."
  AGENT_RULES_URL="${FRAMEWORK_REPO}/releases/latest/download/templates.tar.gz"
  if command_exists curl && curl -fsSL "$AGENT_RULES_URL" | tar -xz -C "$FRAMEWORK_DIR/templates" 2>/dev/null; then
    success "agent-rules.yaml downloaded from GitHub"
  else
    warn "No agent-rules.yaml found — post-checkout hook will fail to generate IDE config until it's added to ~/.agent-framework/templates/"
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — BASELINE FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 5: Installing Baseline Fixtures"

# Golden dataset base — generic agent correctness cases
if [ ! -f "$SHARED_DIR/golden_evals_base.json" ]; then
  if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/fixtures/golden_evals_base.json" ]; then
    cp "$INSTALLER_DIR/fixtures/golden_evals_base.json" "$SHARED_DIR/"
  else
    cat > "$SHARED_DIR/golden_evals_base.json" << 'FIXTURES_EOF'
[
  {
    "id": "base_001",
    "input": "Write a function that validates an email address.",
    "expected_tool": "code_generation",
    "reference_output": "A function using regex or a validation library that checks format, domain, and TLD. Must handle edge cases and raise a typed exception on failure — not return None or swallow the error."
  },
  {
    "id": "base_002",
    "input": "Refactor this module to remove the database call from the constructor.",
    "expected_tool": "code_refactor",
    "reference_output": "Constructor takes a pre-built connection object as a parameter (dependency injection). No network calls in __init__. All database operations moved to explicit methods."
  },
  {
    "id": "base_003",
    "input": "Add retry logic to this API call.",
    "expected_tool": "code_generation",
    "reference_output": "Uses a standard retry library (tenacity, retry, or platform-native). Exponential backoff with jitter. Maximum retry count defined. All exceptions are logged — none swallowed."
  }
]
FIXTURES_EOF
  fi
  success "Baseline golden dataset written to ~/.agent-framework/shared/"
else
  success "Baseline golden dataset already present"
fi

# Custom judge criteria base
if [ ! -f "$SHARED_DIR/custom_judge_criteria_base.json" ]; then
  if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/fixtures/custom_judge_criteria_base.json" ]; then
    cp "$INSTALLER_DIR/fixtures/custom_judge_criteria_base.json" "$SHARED_DIR/"
  else
    cat > "$SHARED_DIR/custom_judge_criteria_base.json" << 'CRITERIA_EOF'
{
  "name": "AgenticFramework_Base_Scorecard",
  "instructions": "You are a senior principal systems architect auditing autonomous agent code. Grade each submission on a strict binary score (1 = pass, 0 = fail) against three immutable rules:\n\n1. PONYTAIL COMPLIANCE: Uses native platform or standard library capabilities only. Fails if it installs unapproved third-party dependencies or builds over-engineered custom abstractions.\n2. CAVEMAN COMPRESSION: Output is direct code or data. Fails if the agent added pleasantries, summaries, or explanatory meta-commentary around the code.\n3. MARCH OF NINES: No empty catch/except blocks, no loose timeouts, no unhandled None returns on error paths. Must display defensive, explicit error handling.\n\n=== HISTORICAL LEARNINGS ===\nFail any submission that violates the rules below:",
  "historical_learnings": []
}
CRITERIA_EOF
  fi
  success "Baseline judge criteria written to ~/.agent-framework/shared/"
else
  success "Baseline judge criteria already present"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — GIT HOOK: pre-commit
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 6: Writing Git Hook Templates"

# Hooks live as standalone files in hooks/ (repo root) — never edit them as
# inline heredocs here (SPECS.md §22 Phase 5). Copy from the local repo if
# available, else fall back to downloading from GitHub releases, same
# pattern as the scripts/ and workflow-templates/ installation steps above.
if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/hooks" ]; then
  cp "$INSTALLER_DIR/hooks/pre-commit" "$TEMPLATE_DIR/hooks/pre-commit"
  cp "$INSTALLER_DIR/hooks/commit-msg" "$TEMPLATE_DIR/hooks/commit-msg"
  cp "$INSTALLER_DIR/hooks/post-commit" "$TEMPLATE_DIR/hooks/post-commit"
  cp "$INSTALLER_DIR/hooks/post-checkout" "$TEMPLATE_DIR/hooks/post-checkout"
  success "Git hook templates copied from local repo"
elif [ -x "$TEMPLATE_DIR/hooks/pre-commit" ] && [ -x "$TEMPLATE_DIR/hooks/post-checkout" ]; then
  success "Git hook templates already present in $TEMPLATE_DIR/hooks/"
else
  info "Downloading hooks from GitHub..."
  HOOKS_URL="${FRAMEWORK_REPO}/releases/latest/download/hooks.tar.gz"
  if command_exists curl && curl -fsSL "$HOOKS_URL" | tar -xz -C "$TEMPLATE_DIR/hooks" 2>/dev/null; then
    success "Hooks downloaded from GitHub"
  else
    error "Could not install git hooks — clone the repo and re-run: git clone ${FRAMEWORK_REPO} && ./AgenticFramework/install-ai-stack.sh"
  fi
fi

# ── Set permissions ────────────────────────────────────────────────────────────
chmod +x \
  "$TEMPLATE_DIR/hooks/pre-commit" \
  "$TEMPLATE_DIR/hooks/commit-msg" \
  "$TEMPLATE_DIR/hooks/post-commit" \
  "$TEMPLATE_DIR/hooks/post-checkout"

success "All four git hook templates written and made executable"

# ── Link global git template dir ───────────────────────────────────────────────
# Capture the pre-install value (if any) so ai-stack-uninstall can restore it
# exactly, rather than just unsetting (SPECS.md §22 Phase 5).
if [ ! -f "$FRAMEWORK_DIR/previous_template_dir" ]; then
  git config --global init.templateDir 2>/dev/null > "$FRAMEWORK_DIR/previous_template_dir" || true
fi
git config --global init.templateDir "$TEMPLATE_DIR"
success "Global git template directory set to $TEMPLATE_DIR"

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — SHELL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 7: Installing Shell Functions → $SHELL_RC"

if grep -q "AI AGENT FRAMEWORK CONTROLLER" "$SHELL_RC" 2>/dev/null; then
  info "Shell functions already present in $SHELL_RC — skipping (re-run with --force to overwrite)"
else

cat >> "$SHELL_RC" << 'SHELL_EOF'

# >>> AgenticFramework managed block — DO NOT EDIT, removed by ai-stack-uninstall >>>
# ══════════════════════════════════════════════════════════════════════════════
# AI AGENT FRAMEWORK CONTROLLER — AgenticFramework v1.0.0
# ══════════════════════════════════════════════════════════════════════════════

# ── Environment defaults ──────────────────────────────────────────────────────
export AGENT_PHOENIX_ENDPOINT="${AGENT_PHOENIX_ENDPOINT:-http://localhost:6006}"
export AGENT_PHOENIX_PORT="${AGENT_PHOENIX_PORT:-6006}"
export AGENT_JUDGE_MODEL="${AGENT_JUDGE_MODEL:-claude-3-5-sonnet-20241022}"
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
notification.notify(title='AgenticFramework', message='Local offline mode active', timeout=4)
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
notification.notify(title='AgenticFramework', message='Hybrid cloud mode active', timeout=4)
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
# valid token (FIXES_AND_CLEANUP.md 1.5 — the control was a UI speed bump,
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

# ── Health check ──────────────────────────────────────────────────────────────
function ai-stack-check() {
  echo "🩺 AgenticFramework Health Check — Mode: [${AI_STACK_MODE:-not set}]"
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
      local models
      models=$(curl -s http://localhost:11434/api/tags 2>/dev/null)
      for m in llama3 mistral gemma2; do
        if echo "$models" | grep -q "$m"; then
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
  echo "  Judge:     ${AGENT_JUDGE_MODEL}"
  echo "  Owner:     ${AGENT_OWNER_ID:-not set}"
  if ping -c 1 -W 1 1.1.1.1 > /dev/null 2>&1; then
    echo "  Network:   🌐 ONLINE"
  else
    echo "  Network:   ❌ OFFLINE (local fallback armed)"
  fi
  echo "────────────────────────────────────────────────"
}

# ── Dashboard ─────────────────────────────────────────────────────────────────
function ai-dashboard-start() {
  echo "📊 Starting Arize Phoenix at ${AGENT_PHOENIX_ENDPOINT}..."
  local db_arg=""
  [ -n "${AGENT_PHOENIX_DB_URL:-}" ] && db_arg="--database-url ${AGENT_PHOENIX_DB_URL}"
  python3 -m phoenix.server.main launch \
    --port "${AGENT_PHOENIX_PORT:-6006}" \
    ${db_arg} &
  export OTEL_EXPORTER_OTLP_ENDPOINT="${AGENT_PHOENIX_ENDPOINT}/v1/traces"
  sleep 1
  echo "🚀 Dashboard live → open ${AGENT_PHOENIX_ENDPOINT}"
}

function ai-dashboard-stop() {
  echo "🔒 Stopping Phoenix..."
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
  # the event with zero error and zero record anywhere (FIXES_AND_CLEANUP.md
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
  local tenant_id="${1:-}"
  local stack="python-fastapi"
  local isolation="shared"
  [ $# -gt 0 ] && shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --stack)     stack="${2:-python-fastapi}"; shift 2 ;;
      --isolation) isolation="${2:-shared}"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [ -z "$tenant_id" ]; then
    echo "❌ Usage: ai-tenant-init <id> [--stack STACK] [--isolation shared|dedicated]"
    echo "   STACK options: python-fastapi (default), go, ts-react"
    return 1
  fi
  if [ "$isolation" != "shared" ] && [ "$isolation" != "dedicated" ]; then
    echo "❌ --isolation must be 'shared' (default) or 'dedicated'"
    return 1
  fi
  # tenant_id is interpolated into a sed replacement string below with no
  # escaping — an id containing '/', '&', or other sed-significant
  # characters would corrupt the substitution (FIXES_AND_CLEANUP.md 4.12).
  # Same pattern Kubernetes namespace naming already requires, so this also
  # keeps shared- and dedicated-isolation tenant ids consistent.
  if ! [[ "$tenant_id" =~ ^[a-z0-9-]+$ ]]; then
    echo "❌ <id> must match ^[a-z0-9-]+$ : got '$tenant_id'"
    return 1
  fi

  if [ ! -d ".git" ]; then
    echo "❌ Not a git repository — run inside the tenant repo root"
    return 1
  fi

  local tmpl_dir="$HOME/.agent-framework/workflow-templates"
  local ci_template="$tmpl_dir/ci-${stack}.yml"
  if [ ! -f "$ci_template" ]; then
    echo "❌ Unknown stack '$stack' — no template at $ci_template"
    return 1
  fi

  echo "🏗  Scaffolding tenant '$tenant_id' (stack: $stack)..."

  mkdir -p ".agenticframework"
  if [ -f ".agenticframework/tenant.yaml" ]; then
    echo "⚠️  .agenticframework/tenant.yaml already exists — leaving untouched"
  else
    cat > ".agenticframework/tenant.yaml" << TENANT_EOF
tenant:
  id: ${tenant_id}
  name: ${tenant_id}
  isolation: ${isolation}

framework:
  version: "${FRAMEWORK_VERSION}"
  mode: developer

environments:
  development:
    phoenix_namespace: ${tenant_id}-dev
  staging:
    phoenix_namespace: ${tenant_id}-staging
    eval_fail_below: 0.75
  production:
    phoenix_namespace: ${tenant_id}-prod
    eval_fail_below: 0.80
    redaction_profile: production
TENANT_EOF
    echo "✅ Wrote .agenticframework/tenant.yaml"
  fi

  mkdir -p ".github/workflows"
  local wrote_any=0
  for wf in "ci-${stack}.yml" "cd-staging.yml" "cd-production.yml" "eval-scorecard.yml"; do
    local src="$tmpl_dir/$wf"
    local dest=".github/workflows/$wf"
    if [ ! -f "$src" ]; then
      echo "⚠️  Template missing, skipping: $src"
      continue
    fi
    if [ -f "$dest" ]; then
      echo "⚠️  $dest already exists — leaving untouched"
      continue
    fi
    sed "s/{{TENANT_ID}}/${tenant_id}/g" "$src" > "$dest"
    echo "✅ Wrote $dest"
    wrote_any=1
  done

  _ai_audit_log_event "tenant_created" "${AGENT_OWNER_ID:-unknown}" "$tenant_id" \
    "{\"stack\":\"${stack}\",\"isolation\":\"${isolation}\"}"

  echo ""
  echo "🎯 Tenant '$tenant_id' scaffolded (isolation: ${isolation})."
  echo "   Next: configure GitHub Environments 'staging' and 'production'"
  echo "   with required reviewers and per-environment secrets (see SPECS.md §17, §24)."
  if [ "$isolation" = "dedicated" ]; then
    echo ""
    echo "   Dedicated isolation: provision this tenant's own worker pool with:"
    echo "   runtime/k8s/dedicated-tenant/render.sh ${tenant_id} <your-worker-image> --apply"
    echo "   (see runtime/k8s/dedicated-tenant/README.md — separate namespace,"
    echo "   separate budget-store Secret, separate Phoenix project per SPECS.md §30)"
  fi
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
  # share a prefix (FIXES_AND_CLEANUP.md 1.4). Same field-parsing approach as
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
  # .cursorrules/CLAUDE.md/.agents/ underneath it (FIXES_AND_CLEANUP.md
  # 4.11). Note: .agent-history.log was listed in the old warning text but
  # never actually matched/removed by any command below — that mismatch is
  # dropped here rather than carried forward or silently "fixed" by adding
  # a deletion nobody asked to verify the blast radius of.
  local matches
  matches="$(
    {
      find "$target_dir" -maxdepth 3 -name ".cursorrules"
      find "$target_dir" -maxdepth 3 -name "CLAUDE.md"
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
  echo "🗑  AgenticFramework: Enterprise-safe machine-level uninstall"
  echo "   This will:"
  echo "   - Remove the AgenticFramework block from ~/.zshrc (or ~/.bashrc / ~/.profile)"
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
  if [ -f "$shell_rc" ] && grep -q ">>> AgenticFramework managed block" "$shell_rc" 2>/dev/null; then
    sed -i.af-uninstall-bak '/>>> AgenticFramework managed block/,/<<< AgenticFramework managed block <<</d' "$shell_rc"
    rm -f "${shell_rc}.af-uninstall-bak"
    echo "✅ Removed AgenticFramework block from $shell_rc"
  else
    echo "⚠️  No AgenticFramework managed block found in $shell_rc — skipping"
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
  local target_version="${FRAMEWORK_VERSION:-1.0.0}"
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

  local vendor_src="$HOME/.agent-framework/scripts"
  if [ ! -d "$vendor_src" ] || [ -z "$(ls -A "$vendor_src" 2>/dev/null)" ]; then
    echo "❌ No vendored scripts found at $vendor_src — run install-ai-stack.sh on this machine first"
    return 1
  fi

  echo "📦 Upgrading vendored scripts to v${target_version}..."
  mkdir -p "scripts"
  cp -r "$vendor_src/." "scripts/"
  find "scripts" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
  echo "✅ Copied vendored scripts from $vendor_src"

  sed -i.af-upgrade-bak "s/^  version: .*/  version: \"${target_version}\"/" ".agenticframework/tenant.yaml"
  rm -f ".agenticframework/tenant.yaml.af-upgrade-bak"
  echo "✅ Updated .agenticframework/tenant.yaml -> framework.version: \"${target_version}\""

  if git diff --quiet -- scripts .agenticframework/tenant.yaml && git diff --cached --quiet -- scripts .agenticframework/tenant.yaml; then
    echo "ℹ️  No changes — scripts/ and tenant.yaml already match v${target_version}"
    return 0
  fi

  git add scripts .agenticframework/tenant.yaml
  if ! git commit -m "chore(framework): upgrade AgenticFramework to v${target_version}"; then
    echo "❌ git commit failed (blocked by a hook, GPG-sign required and unavailable, etc.) —"
    echo "   scripts/ and tenant.yaml were updated and staged but NOT committed. Fix the issue and re-run:"
    echo "   git commit -m \"chore(framework): upgrade AgenticFramework to v${target_version}\""
    return 1
  fi
  echo "✅ Committed: chore(framework): upgrade AgenticFramework to v${target_version}"

  local tenant_id
  tenant_id="$(grep '^  id:' .agenticframework/tenant.yaml | head -1 | sed 's/^  id:[[:space:]]*//')"
  _ai_audit_log_event "config_change" "${AGENT_OWNER_ID:-unknown}" "$tenant_id" \
    "{\"action\":\"framework_upgrade\",\"version\":\"${target_version}\"}"

  echo ""
  echo "🎯 Upgrade complete. Push and open a PR per your branch protection rules (no direct push to main)."
}

# ══════════════════════════════════════════════════════════════════════════════
# <<< AgenticFramework managed block <<<
SHELL_EOF

  success "Shell functions written to $SHELL_RC"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — IDENTITY PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 8: Configuring Identity"

IDENTITY_SET=0

# Check if already set in shell profile
if grep -q "AGENT_OWNER_ID" "$SHELL_RC" 2>/dev/null; then
  info "AGENT_OWNER_ID already configured in $SHELL_RC"
  IDENTITY_SET=1
fi

if [ "$IDENTITY_SET" -eq 0 ] && [ -t 1 ]; then
  echo ""
  echo "All traces, logs, and HITL records are attributed to you as the owner."
  echo "This is set once and applies to all projects on this machine."
  echo ""
  read -r -p "  Your email (AGENT_OWNER_ID): " OWNER_EMAIL
  read -r -p "  Your name  (AGENT_OWNER_NAME): " OWNER_NAME

  if [ -n "$OWNER_EMAIL" ] && [ -n "$OWNER_NAME" ]; then
    cat >> "$SHELL_RC" << IDENTITY_EOF

# AgenticFramework — Owner identity
export AGENT_OWNER_ID="${OWNER_EMAIL}"
export AGENT_OWNER_NAME="${OWNER_NAME}"
IDENTITY_EOF
    success "Identity saved: $OWNER_NAME <$OWNER_EMAIL>"
  else
    warn "Identity not set — add AGENT_OWNER_ID and AGENT_OWNER_NAME to $SHELL_RC manually"
  fi
else
  info "Running non-interactively — set AGENT_OWNER_ID and AGENT_OWNER_NAME in $SHELL_RC"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — FINAL VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 9: Verifying Installation"

VERIFY_PASSED=1

# Git template dir
TMPL=$(git config --global init.templateDir 2>/dev/null || echo "")
if [ "$TMPL" = "$TEMPLATE_DIR" ]; then
  success "git init.templateDir → $TEMPLATE_DIR"
else
  error "git init.templateDir not set correctly (got: $TMPL)"
  VERIFY_PASSED=0
fi

# Hooks present and executable
for hook in pre-commit commit-msg post-commit post-checkout; do
  if [ -x "$TEMPLATE_DIR/hooks/$hook" ]; then
    success "Hook: $hook ✓"
  else
    error "Hook missing or not executable: $hook"
    VERIFY_PASSED=0
  fi
done

# Shell functions present
if grep -q "AI AGENT FRAMEWORK CONTROLLER" "$SHELL_RC" 2>/dev/null; then
  success "Shell functions present in $SHELL_RC"
else
  error "Shell functions not found in $SHELL_RC"
  VERIFY_PASSED=0
fi

# Python: arize-phoenix importable
if python3 -c "import phoenix" 2>/dev/null; then
  success "arize-phoenix importable"
else
  error "arize-phoenix not importable — check pip install output"
  VERIFY_PASSED=0
fi

# ═══════════════════════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "════════════════════════════════════════════════════════════════════"
if [ "$VERIFY_PASSED" -eq 1 ]; then
  echo -e "${GREEN}${BOLD}  🎉 AgenticFramework v${FRAMEWORK_VERSION} installed successfully!${RESET}"
else
  echo -e "${YELLOW}${BOLD}  ⚠️  Installation completed with warnings — review errors above.${RESET}"
fi
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Reload your shell:"
echo "     source $SHELL_RC"
echo ""
echo "  2. Set your identity (if not prompted above):"
echo "     export AGENT_OWNER_ID=\"you@example.com\""
echo "     export AGENT_OWNER_NAME=\"Your Name\""
echo ""
echo "  3. Choose a mode and start the dashboard:"
echo "     ai-mode-local      # offline (Ollama)"
echo "     ai-mode-hybrid     # cloud (set ANTHROPIC_API_KEY / OPENAI_API_KEY first)"
echo "     ai-dashboard-start # http://localhost:6006"
echo ""
echo "  4. Apply to a project:"
echo "     cd /path/to/your-project && git init"
echo ""
echo "  Full documentation:"
echo "     Readme:     ./Readme.md"
echo "     User guide: ./UserManual.md"
echo "     Spec:       ./SPECS.md"
echo "════════════════════════════════════════════════════════════════════"
echo ""
