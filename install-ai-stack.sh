#!/usr/bin/env bash
# =============================================================================
#  AgentSmith Installer — v1.1.0
#  https://github.com/bobbyaqlaar/AgentSmith  (override AI_STACK_FRAMEWORK_REPO for forks)
#
#  Installs once per machine. Safe to re-run (idempotent).
#  Supports macOS, Linux, and Windows (via WSL/Git Bash).
#
#  Usage:
#    curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/latest/download/install-ai-stack.sh | bash
#    # or, from a cloned repo:
#    chmod +x install-ai-stack.sh && ./install-ai-stack.sh
#
#  Self-hosted mirror / fork: set AI_STACK_FRAMEWORK_REPO before running, e.g.
#    AI_STACK_FRAMEWORK_REPO=https://github.com/acme-corp/AgentSmith ./install-ai-stack.sh
#
#  Enterprise mode (skips mutating git's GLOBAL init.templateDir — see
#  docs/UserManual.md › Enterprise Pack for the MDM-distributed hooks path instead):
#    ./install-ai-stack.sh --mode enterprise
#    # piped form needs `-s --` to forward args through stdin:
#    curl -fsSL .../install-ai-stack.sh | bash -s -- --mode enterprise
# =============================================================================

set -uo pipefail

# ── Mode flag ─────────────────────────────────────────────────────────────────
# --mode developer (default): sets git's GLOBAL init.templateDir, so every
#   `git init`/`git clone` on this machine picks up the hook templates
#   (gated per-repo by the opt-in check inside each hook — see hooks/pre-commit).
# --mode enterprise: skips the global init.templateDir mutation entirely.
#   Intended for shared/managed machines where IT distributes hooks via the
#   signed MDM bundle instead (enterprise/package-hook-bundle.sh +
#   mdm-deploy-hooks.sh, see docs/UserManual.md › Enterprise Pack) — this installer still
#   vendors scripts/templates and installs the `agentsmith` command, just without taking over
#   every user's global git config on a machine it doesn't fully own.
INSTALL_MODE="developer"
FORCE_FLAG_GIVEN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      # Replaced the shell-function block in the profile. There is no block any
      # more (Step 7), so it does nothing; accepted so existing scripts and docs
      # that pass it keep working.
      FORCE_FLAG_GIVEN=1
      shift
      ;;
    --mode)
      INSTALL_MODE="${2:-developer}"
      shift 2
      ;;
    --mode=*)
      INSTALL_MODE="${1#--mode=}"
      shift
      ;;
    *)
      shift
      ;;
  esac
done
if [ "$INSTALL_MODE" != "developer" ] && [ "$INSTALL_MODE" != "enterprise" ]; then
  echo "❌ --mode must be 'developer' (default) or 'enterprise', got '$INSTALL_MODE'" >&2
  exit 1
fi

# ── Constants ─────────────────────────────────────────────────────────────────

FRAMEWORK_VERSION="2.3.0"
# Overridable for forks/self-hosted mirrors: AI_STACK_FRAMEWORK_REPO=https://github.com/your-org/AgentSmith ./install-ai-stack.sh
# The literal "<org>" previously here was not a placeholder convention this
# script substituted anywhere — it was used verbatim as a URL component in
# release-download fallback paths (SCRIPTS_URL etc. below), which would
# fail outright the moment any of those fallback paths actually executed
# (docs/PRODUCT_ARCHIVE.md 5.10).
FRAMEWORK_REPO="${AI_STACK_FRAMEWORK_REPO:-https://github.com/bobbyaqlaar/AgentSmith}"
FRAMEWORK_DIR="$HOME/.agent-framework"
TEMPLATE_DIR="$HOME/.git_templates"
SCRIPTS_DIR="$FRAMEWORK_DIR/scripts"
SHARED_DIR="$FRAMEWORK_DIR/shared"
WORKFLOW_TEMPLATES_DIR="$FRAMEWORK_DIR/workflow-templates"
# Standing, machine-wide Phoenix + Postgres + Ops Portal stack — shared
# across every repo on this machine, not
# scoped to any one project checkout. Managed via `agentsmith dashboard start|stop`.
OBSERVABILITY_DIR="$FRAMEWORK_DIR/observability"

# The user's shell profile — read, never written: the installer no longer adds
# anything to it (Step 7 removes what older installs added). Named in hints.
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

# Python: the framework runs in its own environment (Step 3), never in the
# system interpreter. uv builds it at the version in .python-version, fetching a
# managed CPython if the machine has none that matches; without uv, a stock
# `python3 -m venv` at 3.11+ is the fallback.
if command_exists uv; then
  success "uv $(uv --version 2>/dev/null | awk '{print $2}') — builds the framework environment"
elif command_exists python3; then
  PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
  if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ] && python3 -c 'import venv, ensurepip' 2>/dev/null; then
    warn "uv not found — falling back to python3 -m venv (Python $PY_VERSION). Same pinned"
    warn "  packages, but the interpreter is this machine's, not .python-version's."
    warn "  Install uv for the pinned interpreter: brew install uv  (or https://docs.astral.sh/uv/)"
  else
    error "uv not found, and python3 ($PY_VERSION) is not a 3.11+ interpreter with venv/ensurepip."
    error "Install uv: brew install uv  (or https://docs.astral.sh/uv/getting-started/installation/)"
    PREREQ_FAILED=1
  fi
else
  error "Neither uv nor python3 found."
  error "Install uv: brew install uv  (or https://docs.astral.sh/uv/getting-started/installation/)"
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
success "$HOME/.agent-framework/ structure created"

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PYTHON DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════════

# Where the installer runs from: a checkout (copy from it) or a piped download
# (fetch release assets). Steps 3-6 all branch on it.
#
# Piped (`curl … | bash`), BASH_SOURCE is empty and $0 is "bash", so the
# dirname is "." — the CURRENT directory. Run from inside a tenant repo, every
# `[ -d "$INSTALLER_DIR/scripts" ]` below matched the tenant's own scripts/ and
# copied them over the framework's. A checkout is recognised by its own
# installer and hooks, not by whatever directory the user happened to be in.
INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
if [ -n "$INSTALLER_DIR" ] && { [ ! -f "$INSTALLER_DIR/install-ai-stack.sh" ] || [ ! -f "$INSTALLER_DIR/hooks/post-checkout" ]; }; then
  INSTALLER_DIR=""
fi

header "Step 3: Building the Framework Python Environment"

# The framework's Python dependencies live in ONE environment it owns,
# ~/.agent-framework/.venv — never in the system interpreter. This step used to
# `pip install` a hand-kept package list into whatever python3 was first on
# PATH: on Homebrew's externally-managed Python that only worked through
# --break-system-packages, a `brew upgrade python` silently dropped every
# package, and the list had drifted from requirements.txt (it still installed
# prophet, missed jsonschema, and left arize-phoenix uncapped).
#
# What is installed is requirements.lock: compiled from requirements.txt,
# pinned and hashed, and the same file Self-Test installs — so a machine and CI
# resolve identical versions. The Python version it was compiled for is read
# from its own header, so the lock and the interpreter cannot disagree.
VENV_DIR="$FRAMEWORK_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
LOCK_FILE="$FRAMEWORK_DIR/requirements.lock"

# The Python version a lock was compiled for, or nothing — which is also how an
# older install's `pip freeze` output at the same path is told apart.
lock_python_version() {
  sed -n 's/.*uv pip compile .*--python-version \([0-9][0-9.]*\).*/\1/p' "$1" 2>/dev/null | head -1
}

if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/requirements.lock" ]; then
  cp "$INSTALLER_DIR/requirements.lock" "$LOCK_FILE"
  success "requirements.lock copied from local repo"
elif command_exists curl && curl -fsSL "${FRAMEWORK_REPO}/releases/latest/download/requirements.lock" -o "$LOCK_FILE.download" 2>/dev/null \
     && [ -n "$(lock_python_version "$LOCK_FILE.download")" ]; then
  mv "$LOCK_FILE.download" "$LOCK_FILE"
  success "requirements.lock downloaded from GitHub"
elif [ -n "$(lock_python_version "$LOCK_FILE")" ]; then
  rm -f "$LOCK_FILE.download"
  warn "Could not fetch requirements.lock — reusing the one from the previous install."
else
  rm -f "$LOCK_FILE.download"
  error "No requirements.lock: not running from a checkout, and the release download failed."
  error "Clone the repo and re-run: git clone ${FRAMEWORK_REPO} && ./AgentSmith/install-ai-stack.sh"
  exit 1
fi
PY_PIN="$(lock_python_version "$LOCK_FILE")"
if [ -z "$PY_PIN" ]; then
  error "$LOCK_FILE has no \`uv pip compile … --python-version\` header — not a lock this installer can use."
  exit 1
fi

if command_exists uv; then
  # An environment on a different minor version is rebuilt, not patched: the
  # lock's markers were resolved for $PY_PIN.
  if [ -x "$VENV_PYTHON" ]; then
    VENV_VERSION="$("$VENV_PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "")"
    if [ "$VENV_VERSION" != "$PY_PIN" ]; then
      info "Rebuilding $VENV_DIR: Python ${VENV_VERSION:-unknown} → $PY_PIN"
      rm -rf "$VENV_DIR"
    fi
  fi
  info "Installing the pinned packages with uv (Python $PY_PIN)..."
  if uv venv --quiet --allow-existing --python "$PY_PIN" "$VENV_DIR" \
     && uv pip sync --quiet --require-hashes --python "$VENV_PYTHON" "$LOCK_FILE"; then
    success "Framework environment ready: $VENV_DIR (Python $PY_PIN, uv)"
  else
    error "uv could not build $VENV_DIR from requirements.lock — see the output above."
    exit 1
  fi
else
  info "Installing the pinned packages with python3 -m venv + pip (no uv)..."
  if { [ -x "$VENV_PYTHON" ] || python3 -m venv "$VENV_DIR"; } \
     && "$VENV_PYTHON" -m pip install --quiet --require-hashes -r "$LOCK_FILE"; then
    success "Framework environment ready: $VENV_DIR (Python $("$VENV_PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])'), pip — lock compiled for $PY_PIN)"
  else
    error "python3 -m venv / pip could not build $VENV_DIR from requirements.lock — see the output above."
    exit 1
  fi
fi
info "Nothing is installed into, or removed from, the system python3. Packages an"
info "  earlier install put there are left alone."

# The `agentsmith` command: the framework's own package, installed into that
# environment. --no-deps because requirements.lock already carries every
# dependency, pinned and hashed; resolving the package's ranges again could
# move a version the lock chose. After the sync, because `uv pip sync` removes
# anything the lock does not list — this package included.
if [ -n "$INSTALLER_DIR" ]; then
  AGENTSMITH_PACKAGE="$INSTALLER_DIR"
else
  AGENTSMITH_PACKAGE="agentsmith-runtime @ git+${FRAMEWORK_REPO}@v${FRAMEWORK_VERSION}"
fi
if command_exists uv; then
  uv pip install --quiet --no-deps --reinstall --python "$VENV_PYTHON" "$AGENTSMITH_PACKAGE"
else
  "$VENV_PYTHON" -m pip install --quiet --no-deps --force-reinstall "$AGENTSMITH_PACKAGE"
fi
if [ $? -ne 0 ] || [ ! -x "$VENV_DIR/bin/agentsmith" ]; then
  error "Could not install the agentsmith command from $AGENTSMITH_PACKAGE — see the output above."
  exit 1
fi
# Linked into ~/.local/bin — uv's own tool directory and the XDG convention.
# A link, not a copy, so a re-install updates it in place.
AGENTSMITH_BIN_DIR="$HOME/.local/bin"
mkdir -p "$AGENTSMITH_BIN_DIR"
ln -sfn "$VENV_DIR/bin/agentsmith" "$AGENTSMITH_BIN_DIR/agentsmith"
success "agentsmith command → $AGENTSMITH_BIN_DIR/agentsmith"
case ":$PATH:" in
  *":$AGENTSMITH_BIN_DIR:"*) ;;
  *)
    warn "$AGENTSMITH_BIN_DIR is not on your PATH. The installer does not edit shell profiles;"
    warn "  add this line to $SHELL_RC yourself:  export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SCRIPTS INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 4: Installing Agent Scripts"

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
      warn "Clone the repo and re-run: git clone ${FRAMEWORK_REPO} && ./AgentSmith/install-ai-stack.sh"
    fi
  fi
fi

# runtime/ (the production runtime library, `pip install agentsmith-runtime`
# nowhere actually resolves — confirmed against PyPI's own API: no such
# project exists there) and fixtures/security/ (the control registry
# run-security-checks.py's --mode ci/--strict needs — _install_root() only
# ever looks file-relative, never at $AGENTSMITH_DIR, so it crashed outright
# in any tenant). Found onboarding AqlaarTeleologyStudio. Vendored the same
# way scripts/ now is: no GitHub-release tarball for either yet, so this
# copies from a local checkout only and warns rather than downloads — same
# as the design/validation playbook docs step below.
RUNTIME_DIR="$FRAMEWORK_DIR/runtime"
if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/runtime" ]; then
  mkdir -p "$RUNTIME_DIR"
  cp -r "$INSTALLER_DIR/runtime/." "$RUNTIME_DIR/"
  find "$RUNTIME_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
  # Local HITL-gate test-run scratch data (gitignored in the framework's own
  # checkout, .gitignore:runtime/.hitl_blobs/) — a plain `cp -r` from a live
  # working tree doesn't know that. Committed once into a real tenant before
  # this exclusion existed; never again.
  rm -rf "$RUNTIME_DIR/.hitl_blobs"
  success "runtime/ copied from local repo"
elif [ -d "$RUNTIME_DIR" ] && [ "$(ls -A "$RUNTIME_DIR" 2>/dev/null)" ]; then
  success "runtime/ already present in ~/.agent-framework/runtime/"
else
  warn "Not running from a local checkout — runtime/ not vendored. Any tenant"
  warn "script that imports runtime.* (run-evals.py, verify_system.py"
  warn "--check-redaction) will fail with ModuleNotFoundError until this machine"
  warn "clones the repo and re-runs install-ai-stack.sh."
fi

FIXTURES_SECURITY_DIR="$FRAMEWORK_DIR/fixtures/security"
if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/fixtures/security" ]; then
  # `security/.`, not `security`: when the destination already exists — any
  # re-install — `cp -r src dest` nests the copy at dest/security/ and leaves
  # the real one stale.
  mkdir -p "$FIXTURES_SECURITY_DIR"
  cp -r "$INSTALLER_DIR/fixtures/security/." "$FIXTURES_SECURITY_DIR/"
  # The base eval fixtures run-evals.py falls back to (file-relative) — the
  # hook vendors these into tenants per file; see hooks/post-checkout.
  cp "$INSTALLER_DIR"/fixtures/*_base.json "$FRAMEWORK_DIR/fixtures/" 2>/dev/null || true
  success "fixtures/security/ copied from local repo"
elif [ -d "$FIXTURES_SECURITY_DIR" ] && [ "$(ls -A "$FIXTURES_SECURITY_DIR" 2>/dev/null)" ]; then
  success "fixtures/security/ already present in ~/.agent-framework/fixtures/security/"
else
  warn "Not running from a local checkout — fixtures/security/ not vendored."
  warn "run-security-checks.py --mode ci/--strict will crash on a missing"
  warn "control_registry.json in any tenant until this machine clones the repo"
  warn "and re-runs install-ai-stack.sh."
fi

# The gate's own hooks. `agentsmith tenant init` / `tenant adopt` copy these
# into a tenant and arm core.hooksPath at them; a machine without them provisions
# a tenant with NO hooks at all, since a hooks path overrides .git/hooks
# (.agent-rfc/designs/installed-architectures.md). Kept beside the framework's
# own copy, not in ~/.git_templates, which is for the four machine hooks.
GITHOOKS_DIR="$FRAMEWORK_DIR/.githooks"
mkdir -p "$GITHOOKS_DIR"
if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/.githooks" ]; then
  cp -r "$INSTALLER_DIR/.githooks/." "$GITHOOKS_DIR/"
  chmod +x "$GITHOOKS_DIR"/* 2>/dev/null || true
  success "Process-gate hooks copied from local repo"
elif [ -n "$(ls -A "$GITHOOKS_DIR" 2>/dev/null)" ]; then
  success "Process-gate hooks already present in ~/.agent-framework/.githooks/"
else
  info "Downloading process-gate hooks from GitHub..."
  GITHOOKS_URL="${FRAMEWORK_REPO}/releases/latest/download/githooks.tar.gz"
  if command_exists curl && curl -fsSL "$GITHOOKS_URL" | tar -xz -C "$GITHOOKS_DIR" 2>/dev/null; then
    chmod +x "$GITHOOKS_DIR"/* 2>/dev/null || true
    success "Process-gate hooks downloaded from GitHub"
  else
    warn "No .githooks found — agentsmith tenant init/adopt will refuse to arm the gates until they're added to ~/.agent-framework/.githooks/"
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
    warn "No workflow-templates found to install — agentsmith tenant init will fail until they're added to ~/.agent-framework/workflow-templates/"
  fi
fi

# Composite GitHub Actions (.github/actions/) — the ci-*/cd-* workflow
# templates reference these as `uses: ./.github/actions/<name>`, which
# resolves inside the TENANT repo, so post-checkout/`agentsmith tenant init` must copy
# them into each tenant repo alongside the workflows. Vendored here the same
# way workflow-templates are.
GITHUB_ACTIONS_DIR="$FRAMEWORK_DIR/github-actions"
mkdir -p "$GITHUB_ACTIONS_DIR"
if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/.github/actions" ]; then
  cp -r "$INSTALLER_DIR/.github/actions/." "$GITHUB_ACTIONS_DIR/"
  success "Composite GitHub Actions copied from local repo"
elif [ "$(ls -A "$GITHUB_ACTIONS_DIR" 2>/dev/null)" ]; then
  success "Composite GitHub Actions already present in ~/.agent-framework/github-actions/"
else
  info "Downloading github-actions from GitHub..."
  GITHUB_ACTIONS_URL="${FRAMEWORK_REPO}/releases/latest/download/github-actions.tar.gz"
  if command_exists curl && curl -fsSL "$GITHUB_ACTIONS_URL" | tar -xz -C "$GITHUB_ACTIONS_DIR" 2>/dev/null; then
    success "Composite GitHub Actions downloaded from GitHub"
  else
    warn "No composite GitHub Actions found — tenant cd-staging/cd-production will fail on 'uses: ./.github/actions/*' until ~/.agent-framework/github-actions/ is populated"
  fi
fi

# agent-rules.yaml — single source of truth for .cursorrules/CLAUDE.md/Antigravity
# skill generation (docs/DESIGN.md › Ten Operational Pillars, Antigravity Integration). The post-checkout hook reads
# it from here via scripts/generate-ide-config.py.
mkdir -p "$FRAMEWORK_DIR/templates"
if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/templates/agent-rules.yaml" ]; then
  cp "$INSTALLER_DIR/templates/agent-rules.yaml" "$FRAMEWORK_DIR/templates/agent-rules.yaml"
  # governance.json is agent-rules.yaml compiled for the process gate, which
  # runs without pyyaml. Copied together: a machine with one and not the other
  # has rule files and a gate that disagree.
  [ -f "$INSTALLER_DIR/templates/governance.json" ] && \
    cp "$INSTALLER_DIR/templates/governance.json" "$FRAMEWORK_DIR/templates/governance.json"
  # architectures.yaml is the catalogue `agentsmith tenant init/adopt
  # --architecture` renders. Read by name like the two above, so it ships with
  # them: without it, --architecture fails anywhere but a checkout
  # (scripts/test/test_installer_templates.py).
  [ -f "$INSTALLER_DIR/templates/architectures.yaml" ] && \
    cp "$INSTALLER_DIR/templates/architectures.yaml" "$FRAMEWORK_DIR/templates/architectures.yaml"
  success "agent-rules.yaml + governance.json + architectures.yaml copied from local repo"
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

# Design/validation playbook docs — agent-rules.yaml's design_review and
# validation_review skill entries point every generated IDE-rule file
# (.cursorrules, CLAUDE.md, AGENTS.md, GEMINI.md, copilot-instructions.md,
# Antigravity skill files) at these two. docs/ is not vendored wholesale —
# only these two files are, the same narrow-copy pattern already used above
# for agent-rules.yaml itself rather than all of templates/. Without this
# step the pointer resolves against $AGENTSMITH_DIR only, which is unset for
# any tenant running on the installed package rather than a live checkout —
# `declared-vs-enforced`, applied to this framework's own installer.
mkdir -p "$FRAMEWORK_DIR/docs"
if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/docs/design-review-checklist.md" ]; then
  # review-levers.md too: the process gates (scripts/process_gate.py) validate a
  # design's cited levers against it, and an installed-mode tenant (KYC
  # Sentinel) has no copy of its own — its config points at @framework/.
  cp "$INSTALLER_DIR/docs/design-review-checklist.md" "$INSTALLER_DIR/docs/validation-checklist.md" \
     "$INSTALLER_DIR/docs/review-levers.md" "$FRAMEWORK_DIR/docs/"
  success "design/validation playbook docs and review levers copied from local repo"
elif [ -f "$FRAMEWORK_DIR/docs/design-review-checklist.md" ]; then
  success "design/validation playbook docs already present in ~/.agent-framework/docs/"
else
  warn "No design-review-checklist.md/validation-checklist.md found locally — generated IDE rules will point at \$AGENTSMITH_DIR only. Set AGENTSMITH_DIR to a live framework checkout, or copy these two files into ~/.agent-framework/docs/ yourself."
fi

# On-prem/air-gapped deployment template (Docker Compose + Traefik/Envoy
# canary+shadow routing, Helm chart for K8s) — opt-in, vendored like
# agent-rules.yaml above but only ever copied into a tenant repo on
# explicit request via `agentsmith tenant onprem-scaffold` (docs/PRODUCT_ARCHIVE.md P4
# on-prem follow-up), never written automatically the way the CI/CD
# workflow templates are by `agentsmith tenant init`/post-checkout.
if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/templates/onprem-deploy" ]; then
  rm -rf "$FRAMEWORK_DIR/templates/onprem-deploy"
  cp -r "$INSTALLER_DIR/templates/onprem-deploy" "$FRAMEWORK_DIR/templates/onprem-deploy"
  success "onprem-deploy template copied from local repo"
elif [ -d "$FRAMEWORK_DIR/templates/onprem-deploy" ]; then
  success "onprem-deploy template already present in ~/.agent-framework/templates/"
else
  info "Downloading onprem-deploy template from GitHub..."
  ONPREM_TEMPLATE_URL="${FRAMEWORK_REPO}/releases/latest/download/templates.tar.gz"
  if command_exists curl && curl -fsSL "$ONPREM_TEMPLATE_URL" | tar -xz -C "$FRAMEWORK_DIR/templates" 2>/dev/null; then
    success "onprem-deploy template downloaded from GitHub"
  else
    warn "No onprem-deploy template found — agentsmith tenant onprem-scaffold will fail until it's added to ~/.agent-framework/templates/onprem-deploy/"
  fi
fi

# Standing observability stack: docker-compose.yml + init-db/ (Phoenix +
# Postgres) and the Ops Portal source (built into a container image by
# `agentsmith dashboard start`, not run via npm directly on the host). Vendored the
# same way scripts/workflow-templates/templates are above — see
# runtime/machine/ops.py (dashboard_start/dashboard_stop) for what actually
# starts/stops it. Docker itself is optional: if it's not installed,
# `agentsmith dashboard start` falls back to a standalone Phoenix (uvx)
# launch and this vendoring step is simply skipped (no error).
if command_exists docker; then
  mkdir -p "$OBSERVABILITY_DIR"
  if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/docker-compose.yml" ]; then
    cp "$INSTALLER_DIR/docker-compose.yml" "$OBSERVABILITY_DIR/docker-compose.yml"
    cp -r "$INSTALLER_DIR/init-db" "$OBSERVABILITY_DIR/init-db"
    mkdir -p "$OBSERVABILITY_DIR/portal"
    # Exclude node_modules/.next/.env*: the container build runs its own
    # `npm ci` and `npm run build` (portal/Dockerfile) — copying these
    # would bloat the vendor step with build artifacts the image rebuilds
    # anyway, and .env* could leak local dev secrets into the vendored copy.
    (cd "$INSTALLER_DIR/portal" && tar -cf - --exclude=node_modules --exclude=.next --exclude='.env*' .) \
      | (cd "$OBSERVABILITY_DIR/portal" && tar -xf -)
    success "Observability stack (Phoenix + Postgres + Ops Portal) vendored to $OBSERVABILITY_DIR"
  elif [ -f "$OBSERVABILITY_DIR/docker-compose.yml" ]; then
    success "Observability stack already present in $OBSERVABILITY_DIR"
  else
    warn "Not running from a local checkout — observability stack not vendored."
    warn "agentsmith dashboard start will fall back to a standalone Phoenix until"
    warn "you clone the repo and re-run install-ai-stack.sh, or manually copy"
    warn "docker-compose.yml + init-db/ + portal/ into $OBSERVABILITY_DIR."
  fi
else
  info "Docker not found — skipping standing observability stack (agentsmith dashboard start"
  info "will use a standalone Phoenix instead). Install Docker to get the"
  info "full Phoenix + Postgres + Ops Portal stack shared across all repos on this machine."
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
  "name": "AgentSmith_Base_Scorecard",
  "instructions": "You are a senior principal systems architect auditing autonomous agent code. Grade each submission on a strict binary score (1 = pass, 0 = fail) against three immutable rules:\n\n1. PONYTAIL COMPLIANCE: Uses native platform or standard library capabilities only. Fails if it installs unapproved third-party dependencies or builds over-engineered custom abstractions.\n2. CAVEMAN COMPRESSION: Output is direct code or data. Fails if the agent added pleasantries, summaries, or explanatory meta-commentary around the code.\n3. MARCH OF NINES: No empty catch/except blocks, no loose timeouts, no unhandled None returns on error paths. Must display defensive, explicit error handling.\n\n=== HISTORICAL LEARNINGS ===\nFail any submission that violates the rules below:",
  "historical_learnings": []
}
CRITERIA_EOF
  fi
  success "Baseline judge criteria written to ~/.agent-framework/shared/"
else
  success "Baseline judge criteria already present"
fi

# Fairness eval suite base (paired bias audits — UAE / ISO theme)
if [ ! -f "$SHARED_DIR/fairness_evals_base.json" ]; then
  if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/fixtures/fairness_evals_base.json" ]; then
    cp "$INSTALLER_DIR/fixtures/fairness_evals_base.json" "$SHARED_DIR/"
    success "Baseline fairness evals written to ~/.agent-framework/shared/"
  else
    info "fairness_evals_base.json not found in installer — skip (optional suite)"
  fi
else
  success "Baseline fairness evals already present"
fi
if [ ! -f "$SHARED_DIR/fairness_judge_criteria_base.json" ]; then
  if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/fixtures/fairness_judge_criteria_base.json" ]; then
    cp "$INSTALLER_DIR/fixtures/fairness_judge_criteria_base.json" "$SHARED_DIR/"
    success "Baseline fairness judge criteria written to ~/.agent-framework/shared/"
  fi
fi

# Security pack templates (SEC-* harness artifacts) — vendored here so
# hooks/post-checkout can seed them into each opted-in repo's
# .agent-rfc/security/. The harness has always LOOKED for these four files in
# tenant repos; until this step nothing ever PUT them there, so every new
# tenant started with those controls skipping/failing and had to find
# fixtures/security/templates/ by reading the framework tree
# (TestbedFeedback-2026-07-21 G5). Refreshed on every install (unlike the
# eval fixtures) because these are pristine templates, never the tenant's
# edited copies — post-checkout is what refuses to overwrite those.
if [ -n "$INSTALLER_DIR" ] && [ -d "$INSTALLER_DIR/fixtures/security/templates" ]; then
  mkdir -p "$SHARED_DIR/security"
  cp "$INSTALLER_DIR"/fixtures/security/templates/*.yaml "$SHARED_DIR/security/" 2>/dev/null || true
  success "Security pack templates written to ~/.agent-framework/shared/security/"
else
  info "security templates not found in installer — tenant .agent-rfc/security/ will not be seeded"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — GIT HOOK: pre-commit
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 6: Writing Git Hook Templates"

# Hooks live as standalone files in hooks/ (repo root) — never edit them as
# inline heredocs here. Copy from the local repo if
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
    error "Could not install git hooks — clone the repo and re-run: git clone ${FRAMEWORK_REPO} && ./AgentSmith/install-ai-stack.sh"
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
# Capture the pre-install value (if any) so `agentsmith uninstall` can restore it
# exactly, rather than just unsetting.
if [ "$INSTALL_MODE" = "enterprise" ]; then
  info "Enterprise mode (--mode enterprise): skipping global git init.templateDir."
  info "Hooks are vendored to $TEMPLATE_DIR but not linked machine-wide — distribute"
  info "via enterprise/package-hook-bundle.sh + mdm-deploy-hooks.sh instead (docs/UserManual.md › Enterprise Pack)."
else
  if [ ! -f "$FRAMEWORK_DIR/previous_template_dir" ]; then
    git config --global init.templateDir 2>/dev/null > "$FRAMEWORK_DIR/previous_template_dir" || true
  fi
  git config --global init.templateDir "$TEMPLATE_DIR"
  success "Global git template directory set to $TEMPLATE_DIR"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — MACHINE STATE, AND NO SHELL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 7: Recording Machine State"

# Every operator command is `agentsmith <command>` (runtime/cli.py). This step
# used to append 18 shell functions to the profile, which reached interactive
# shells only — a git GUI, an IDE, CI and Claude Code's hooks never had them,
# and a mode "set" by one was an export in one terminal. Machine state is now
# files under ~/.agent-framework/state/ that every process reads.
STATE_DIR="$FRAMEWORK_DIR/state"
mkdir -p "$STATE_DIR"
printf '%s\n' "$INSTALL_MODE" > "$STATE_DIR/install-mode"
success "Install mode recorded: $STATE_DIR/install-mode ($INSTALL_MODE)"

# Remove what older installs appended — one implementation, in Python, which
# `agentsmith uninstall` uses too. It keeps a *.agentsmith-bak of any profile it
# edits and never edits a block it cannot bound.
# The old block exported AI_STACK_MODE, which outranks the machine's mode file,
# so a block left behind is not harmless: every shell that loads it pins the mode.
if "$VENV_DIR/bin/agentsmith" uninstall --legacy-profile-only; then
  success "No AgentSmith shell functions left in ~/.zshrc, ~/.bashrc or ~/.profile"
  info "Terminals opened before this install still carry the old block's AI_STACK_MODE export"
  info "  until they are closed; \`agentsmith mode\` warns when it sees one."
else
  warn "AgentSmith shell functions remain in a shell profile (see above). They export"
  warn "  AI_STACK_MODE, which outranks \`agentsmith mode\` in every shell that loads them —"
  warn "  remove them by hand."
fi
if [ "$FORCE_FLAG_GIVEN" -eq 1 ]; then
  info "--force is no longer needed: nothing is written to a shell profile."
fi

# Optional muscle memory: ai-* names as one-line wrappers. Never sourced here.
mkdir -p "$FRAMEWORK_DIR/shell"
if [ -n "$INSTALLER_DIR" ] && [ -f "$INSTALLER_DIR/templates/shell/ai-compat.sh" ]; then
  cp "$INSTALLER_DIR/templates/shell/ai-compat.sh" "$FRAMEWORK_DIR/shell/ai-compat.sh"
  info "Old ai-* names, if you want them: source ~/.agent-framework/shell/ai-compat.sh"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — IDENTITY PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

header "Step 8: Configuring Identity"

# Owner identity is NO LONGER written to the shell profile, and no longer
# prompted for.
#
# It used to be, and "applies to all projects on this machine" was the selling
# point — which is exactly the problem. An exported variable looks like a
# deliberate per-deploy override and outranks a tenant's declared `tenant.owner`
# under the standard precedence, so every repo on the machine reported the
# installer's answer whatever each tenant declared. One developer with one
# address never notices; a second person, or a second tenant, does. And CI has
# no shell profile at all, so the same code attributed nothing there.
#
# Resolution order now (scripts/agent_logger.py:_owner):
#
#   .agenticframework/tenant.yaml `tenant.owner`
#     → AGENT_OWNER_ID
#       → git config user.email
#
# Inside a tenant the declaration wins; outside one, git already knows and needs
# no configuration at all. AGENT_OWNER_ID still works as a deliberate override —
# a container, a CI job — it is simply not ambient any more.
if grep -q "^export AGENT_OWNER_ID" "$SHELL_RC" 2>/dev/null; then
  warn "AGENT_OWNER_ID is exported in $SHELL_RC — it now silently outranks every"
  warn "  tenant's declared tenant.owner on this machine. Safe to delete that line;"
  warn "  identity resolves from tenant.yaml, then git config user.email."
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

# The command runs, through the link a user's PATH resolves.
if AGENTSMITH_VERSION="$("$AGENTSMITH_BIN_DIR/agentsmith" version 2>/dev/null)"; then
  success "agentsmith $AGENTSMITH_VERSION ($AGENTSMITH_BIN_DIR/agentsmith)"
else
  error "agentsmith did not run from $AGENTSMITH_BIN_DIR/agentsmith — re-run the installer"
  VERIFY_PASSED=0
fi

# Python: the framework environment imports what the hooks and scripts need —
# checked with the interpreter the hooks resolve, not the system python3.
if "$VENV_PYTHON" -c "import yaml, networkx, httpx, opentelemetry.sdk" 2>/dev/null; then
  success "Framework environment imports yaml, networkx, httpx, opentelemetry ($VENV_PYTHON)"
else
  error "Framework environment at $VENV_DIR cannot import yaml/networkx/httpx/opentelemetry — re-run the installer"
  VERIFY_PASSED=0
fi

# ═══════════════════════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "════════════════════════════════════════════════════════════════════"
if [ "$VERIFY_PASSED" -eq 1 ]; then
  echo -e "${GREEN}${BOLD}  🎉 AgentSmith v${FRAMEWORK_VERSION} installed successfully!${RESET}"
else
  echo -e "${YELLOW}${BOLD}  ⚠️  Installation completed with warnings — review errors above.${RESET}"
fi
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Owner identity resolves automatically:"
echo "     inside a tenant  — .agenticframework/tenant.yaml  tenant.owner"
echo "     anywhere else    — git config user.email"
echo "     override         — export AGENT_OWNER_ID=\"you@example.com\""
echo ""
echo "  2. Choose a mode and start the dashboard (every process on this machine sees it):"
echo "     agentsmith mode local        # offline (Ollama)"
echo "     agentsmith mode hybrid       # cloud (set ANTHROPIC_API_KEY / OPENAI_API_KEY first)"
echo "     agentsmith dashboard start   # http://localhost:6006"
echo ""
echo "  3. Apply to a project:"
echo "     cd /path/to/your-project && git init"
echo ""
echo "  Full documentation:"
DOCS_AT="${INSTALLER_DIR:-https://github.com/bobbyaqlaar/AgentSmith/blob/main}"
echo "     Readme:     $DOCS_AT/README.md"
echo "     User guide: $DOCS_AT/docs/UserManual.md"
echo "     Design:     $DOCS_AT/docs/DESIGN.md"
echo "════════════════════════════════════════════════════════════════════"
echo ""
