"""
verify_system.py — AgenticFramework installation health checker.

Validates:
  1. Python version (≥3.11)
  2. Required packages importable
  3. Git hooks installed and executable
  4. Phoenix connectivity
  5. Network / Ollama status
  6. Agent identity configured
  7. Unresolved MAJOR/CRITICAL log entries in current project

Used by:
  - ai-stack-check shell function
  - GitHub Actions CI (optional smoke-test step)

Exit codes:
  0 = all checks passed
  1 = one or more checks failed
"""

from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

REQUIRED_PACKAGES = [
    "phoenix",          # arize-phoenix
    "opentelemetry",    # opentelemetry-sdk
    "networkx",         # networkx>=3.0
    "langgraph",        # langgraph>=0.2 (soft)
    "tiktoken",         # cost router token counting
    "httpx",            # LLM API calls
    "plyer",            # notifications
    "tenacity",         # retry logic
]

SOFT_PACKAGES = {"langgraph"}    # warn-only; not hard requirement


def _repo_root() -> Path:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            return parent
    return cwd


def _check(label: str, ok: bool, detail: str = "", warn_only: bool = False) -> bool:
    if ok:
        print(f"  ✅  {label}")
    elif warn_only:
        print(f"  ⚠️   {label}" + (f" — {detail}" if detail else ""))
    else:
        print(f"  ❌  {label}" + (f" — {detail}" if detail else ""))
    return ok or warn_only


def run_checks() -> bool:
    failures = 0

    print("═══════════════════════════════════════════════════")
    print("  AgenticFramework System Verification")
    print("═══════════════════════════════════════════════════\n")

    # ── 1. Python version ─────────────────────────────────────────────────────
    print("Python environment:")
    major, minor = sys.version_info.major, sys.version_info.minor
    ok = major >= 3 and minor >= 11
    if not _check(f"Python {major}.{minor}", ok, "Requires ≥3.11"):
        failures += 1
    print()

    # ── 2. Required packages ──────────────────────────────────────────────────
    print("Required packages:")
    for pkg in REQUIRED_PACKAGES:
        is_soft = pkg in SOFT_PACKAGES
        try:
            mod = importlib.import_module(pkg)
            version = getattr(mod, "__version__", "?")
            _check(f"{pkg} ({version})", True, warn_only=is_soft)
        except ImportError:
            msg = f"pip install {pkg}"
            if not _check(pkg, False, msg, warn_only=is_soft):
                failures += 1
    print()

    # ── 3. Git hooks ──────────────────────────────────────────────────────────
    print("Git hooks:")
    template_dir = Path.home() / ".git_templates" / "hooks"
    for hook in ["pre-commit", "commit-msg", "post-commit", "post-checkout"]:
        hook_path = template_dir / hook
        ok = hook_path.exists() and os.access(hook_path, os.X_OK)
        if not _check(f"hook: {hook}", ok, f"Expected at {hook_path}"):
            failures += 1
    # templateDir global config
    try:
        configured_dir = subprocess.check_output(
            ["git", "config", "--global", "init.templateDir"],
            capture_output=True, text=True
        ).stdout.strip()
        ok = str(template_dir) in configured_dir or configured_dir.endswith(".git_templates")
        if not _check("git init.templateDir set", ok, f"Got: {configured_dir!r}"):
            failures += 1
    except subprocess.CalledProcessError:
        if not _check("git init.templateDir set", False, "Not configured"):
            failures += 1
    print()

    # ── 4. Phoenix connectivity ───────────────────────────────────────────────
    print("Observability:")
    phoenix_endpoint = os.environ.get("AGENT_PHOENIX_ENDPOINT", "http://localhost:6006")
    try:
        import httpx
        resp = httpx.get(phoenix_endpoint, timeout=3.0)
        phoenix_ok = resp.status_code in (200, 301, 302, 404)  # 404 = server up, unknown path
    except Exception:
        phoenix_ok = False
    if not _check(f"Phoenix @ {phoenix_endpoint}", phoenix_ok, "Run: ai-dashboard-start", warn_only=True):
        pass   # warn-only: offline phoenix is allowed
    print()

    # ── 5. Network / Ollama ───────────────────────────────────────────────────
    print("Network & local models:")
    try:
        s = socket.create_connection(("1.1.1.1", 53), timeout=2)
        s.close()
        _check("Internet connectivity", True)
    except OSError:
        _check("Internet connectivity", False, "Offline — local mode only", warn_only=True)

    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        ollama_ok = resp.status_code == 200
        models = [m["name"] for m in resp.json().get("models", [])] if ollama_ok else []
        _check("Ollama daemon", ollama_ok, "Run: ollama serve" if not ollama_ok else "", warn_only=True)
        for required_model in ["llama3", "mistral", "gemma2"]:
            present = any(required_model in m for m in models)
            _check(f"  model: {required_model}", present, f"ollama pull {required_model}", warn_only=True)
    except Exception:
        _check("Ollama daemon", False, "Run: ollama serve", warn_only=True)
    print()

    # ── 6. Agent identity ─────────────────────────────────────────────────────
    print("Identity:")
    owner_id   = os.environ.get("AGENT_OWNER_ID", "")
    owner_name = os.environ.get("AGENT_OWNER_NAME", "")
    if not _check("AGENT_OWNER_ID set",   bool(owner_id),   "export AGENT_OWNER_ID=you@example.com"):
        failures += 1
    if not _check("AGENT_OWNER_NAME set", bool(owner_name), "export AGENT_OWNER_NAME='Your Name'"):
        failures += 1
    judge = os.environ.get("AGENT_JUDGE_MODEL", "claude-3-5-sonnet-20241022")
    _check(f"AGENT_JUDGE_MODEL: {judge}", True)
    print()

    # ── 7. Unresolved MAJOR/CRITICAL in current project ───────────────────────
    print("Project log:")
    root = _repo_root()
    log_file = root / ".agent-history.log"
    if not log_file.exists():
        _check("No .agent-history.log (new project)", True)
    else:
        unresolved = []
        with log_file.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if (
                        entry.get("level") in ("MAJOR", "CRITICAL")
                        and not entry.get("hitl_resolved", True)
                    ):
                        unresolved.append(entry)
                except Exception:
                    pass

        if unresolved:
            _check(
                f"{len(unresolved)} unresolved MAJOR/CRITICAL issue(s)",
                False,
                "Run 'ai-stack-promote' or resolve in Phoenix UI",
            )
            for entry in unresolved[:5]:
                print(f"       [{entry['level']}] {entry.get('timestamp','')}  {entry.get('event','')}")
            failures += 1
        else:
            _check(".agent-history.log clean (no unresolved issues)", True)
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("═══════════════════════════════════════════════════")
    if failures == 0:
        print("  🎉  All checks passed — environment ready")
    else:
        print(f"  🛑  {failures} check(s) failed — resolve issues above")
    print("═══════════════════════════════════════════════════")

    return failures == 0


def check_redaction() -> bool:
    """
    CI validation for §27 trace redaction. Runs the active redaction profile
    (from $ENVIRONMENT) against fixture payloads containing known secret/PII
    patterns and fails if any raw pattern survives scrubbing.

    Used by cd-staging.yml / cd-production.yml:
        python3 scripts/verify_system.py --check-redaction
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))
    from trace_redactor import TraceRedactor  # type: ignore

    redactor = TraceRedactor()
    fixtures = [
        "Authorization: Bearer sk-ant-abcdefghijklmnopqrstuvwxyz0123456789",
        "contact support at someone@example.com about order 4111-1111-1111-1111",
        "raw key sk-abcdefghijklmnopqrstuvwxyz0123456789",
    ]

    print("═══════════════════════════════════════════════════")
    print(f"  Redaction Compliance Check (profile: {redactor.profile})")
    print("═══════════════════════════════════════════════════\n")

    if redactor.profile == "none":
        _check("ENVIRONMENT is development/testing — redaction check skipped", True, warn_only=True)
        print("═══════════════════════════════════════════════════")
        return True

    failures = 0
    for fixture in fixtures:
        scrubbed = redactor._scrub(fixture, hash_identifiers=(redactor.profile == "staging"))
        if redactor.profile == "production":
            scrubbed = redactor._truncate(scrubbed)
        leaked = ("sk-" in scrubbed) or ("@example.com" in scrubbed) or ("4111" in scrubbed)
        if not _check(f"fixture scrubbed: {fixture[:40]}...", not leaked, f"leaked → {scrubbed!r}"):
            failures += 1

    print()
    print("═══════════════════════════════════════════════════")
    if failures == 0:
        print("  🎉  Redaction compliance passed")
    else:
        print(f"  🛑  {failures} fixture(s) leaked raw secret/PII patterns")
    print("═══════════════════════════════════════════════════")
    return failures == 0


if __name__ == "__main__":
    if "--check-redaction" in sys.argv:
        sys.exit(0 if check_redaction() else 1)
    ok = run_checks()
    sys.exit(0 if ok else 1)
