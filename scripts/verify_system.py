"""
verify_system.py — AgentSmith installation health checker.

Validates:
  1. Python version (≥3.11)
  2. Required packages importable
  3. Git hooks installed and executable
  4. Phoenix connectivity
  5. Network / Ollama status
  6. Agent identity configured
  7. Unresolved MAJOR/CRITICAL log entries in current project

Used by:
  - `agentsmith check`
  - GitHub Actions CI (optional smoke-test step)

Exit codes:
  0 = all checks passed
  1 = one or more checks failed
"""

from __future__ import annotations

import importlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

REQUIRED_PACKAGES = [
    "phoenix",  # arize-phoenix
    "opentelemetry",  # opentelemetry-sdk
    "networkx",  # networkx>=3.0
    "langgraph",  # langgraph>=0.2 (soft)
    "tiktoken",  # cost router token counting
    "httpx",  # LLM API calls
    "plyer",  # notifications
    "tenacity",  # retry logic
]

SOFT_PACKAGES = {"langgraph"}  # warn-only; not hard requirement


from _shared import (  # noqa: E402
    _CREDENTIAL_NAME,
    _dotenv_pairs,
    _repo_root,
    _standalone_env_overrides,
    fixtures_path,
    judge_model as _resolve_judge_model,
)

# The environment this process was started with, before any check loads a
# repository's .env into it — what the shell actually exported.
_AMBIENT = dict(os.environ)
SHELL_PROFILES = (".zshrc", ".zprofile", ".zshenv", ".bashrc", ".bash_profile", ".profile")
_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=")


def exported_credentials(home: Path) -> list[str]:
    """`~/.zshrc:12 GEMINI_API_KEY` for each credential a shell profile sets —
    names and places only, never a value."""
    found = []
    for name in SHELL_PROFILES:
        try:
            lines = (home / name).read_text(errors="ignore").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            match = _ASSIGNMENT.match(line)
            if match and _CREDENTIAL_NAME.search(match.group(1)):
                found.append(f"~/{name}:{number} {match.group(1)}")
    return found


def shadowed_credentials(root: Path, ambient: dict) -> list[str]:
    """Credentials this repository's .env declares that the shell holds with a
    different value — the ones the loader replaces. Names only."""
    overrides = _standalone_env_overrides(root)
    return [key for key, value in _dotenv_pairs(root / ".env")
            if _CREDENTIAL_NAME.search(key) and key not in overrides
            and value and ambient.get(key) and ambient[key] != value]


def _required_ollama_models() -> list[str]:
    """Ollama model ids the merged registry actually routes to.

    Read from models.yaml rather than hardcoded, for the same reason the eval
    judge is (scripts/_shared.py:judge_model()): a second hand-maintained list
    of model names drifts silently, and this one had — it still named
    llama3/mistral/gemma2 long after the registry moved on, so the check told
    users to pull models nothing used while the ones the gateway needs went
    unverified. Falls back to that historical list only if runtime/ isn't
    importable (scripts-only install).
    """
    from _shared import provider_models

    # Same helper `agentsmith models --ollama` uses (runtime/machine/ops.py),
    # so the health check and this check can never disagree about what to pull.
    return provider_models("ollama") or ["qwen2.5", "llama3.2:3b", "falcon3:3b", "smollm2"]


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
    print("  AgentSmith System Verification")
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

    # ── 3. No machine-wide git hooks ──────────────────────────────────────────
    # 3.0.0 arms none (.agent-rfc/designs/vendoring-retired.md); a repository is
    # governed by its own .githooks. One left pointing at AgentSmith's old
    # templates is reported, so a re-install can put it back.
    print("Git hooks:")
    configured_dir = subprocess.run(["git", "config", "--global", "--get", "init.templateDir"],
                                    capture_output=True, text=True, check=False).stdout.strip()
    stale = configured_dir.rstrip("/").endswith(".git_templates") and any(
        (Path(configured_dir).expanduser() / "hooks" / hook).is_file()
        for hook in ("pre-commit", "commit-msg", "post-commit", "post-checkout"))
    if not _check("no machine-wide AgentSmith hooks", not stale,
                  f"init.templateDir={configured_dir!r} still holds them — re-run install-ai-stack.sh"):
        failures += 1
    print()

    # ── 4. Phoenix connectivity ───────────────────────────────────────────────
    print("Observability:")
    phoenix_endpoint = os.environ.get("AGENT_PHOENIX_ENDPOINT", "http://localhost:6006")
    try:
        import httpx

        resp = httpx.get(phoenix_endpoint, timeout=3.0)
        phoenix_ok = resp.status_code in (
            200,
            301,
            302,
            404,
        )  # 404 = server up, unknown path
    except Exception:
        phoenix_ok = False
    if not _check(
        f"Phoenix @ {phoenix_endpoint}",
        phoenix_ok,
        "Run: agentsmith dashboard start",
        warn_only=True,
    ):
        pass  # warn-only: offline phoenix is allowed
    print()

    # ── 5. Network / Ollama ───────────────────────────────────────────────────
    print("Network & local models:")
    try:
        s = socket.create_connection(("1.1.1.1", 53), timeout=2)
        s.close()
        _check("Internet connectivity", True)
    except OSError:
        _check(
            "Internet connectivity", False, "Offline — local mode only", warn_only=True
        )

    try:
        import httpx

        resp = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        ollama_ok = resp.status_code == 200
        models = [m["name"] for m in resp.json().get("models", [])] if ollama_ok else []
        _check(
            "Ollama daemon",
            ollama_ok,
            "Run: ollama serve" if not ollama_ok else "",
            warn_only=True,
        )
        for required_model in _required_ollama_models():
            # Exact id, or the same id with an implicit ":latest" tag — not a
            # substring match. The old hardcoded ["llama3", "mistral",
            # "gemma2"] list drifted from models.yaml AND matched loosely, so
            # "llama3" reported present because llama3.2:latest happened to be
            # installed, while the models the registry actually routes to went
            # unchecked.
            present = any(
                m == required_model or m.split(":")[0] == required_model.split(":")[0]
                if ":" not in required_model
                else m == required_model
                for m in models
            )
            _check(
                f"  model: {required_model}",
                present,
                f"ollama pull {required_model}",
                warn_only=True,
            )
    except Exception:
        _check("Ollama daemon", False, "Run: ollama serve", warn_only=True)
    print()

    # ── 6. Agent identity ─────────────────────────────────────────────────────
    print("Identity:")
    owner_id = os.environ.get("AGENT_OWNER_ID", "")
    owner_name = os.environ.get("AGENT_OWNER_NAME", "")
    if not _check(
        "AGENT_OWNER_ID set", bool(owner_id), "export AGENT_OWNER_ID=you@example.com"
    ):
        failures += 1
    if not _check(
        "AGENT_OWNER_NAME set", bool(owner_name), "export AGENT_OWNER_NAME='Your Name'"
    ):
        failures += 1
    judge = _resolve_judge_model()
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
                    if entry.get("level") in ("MAJOR", "CRITICAL") and not entry.get(
                        "hitl_resolved", True
                    ):
                        unresolved.append(entry)
                # fail-open: one malformed JSON-lines entry must not abort scanning the
                # rest of the log for unresolved issues
                except Exception:
                    pass

        if unresolved:
            _check(
                f"{len(unresolved)} unresolved MAJOR/CRITICAL issue(s)",
                False,
                "Run 'agentsmith promote' or resolve in Phoenix UI",
            )
            for entry in unresolved[:5]:
                print(
                    f"       [{entry['level']}] {entry.get('timestamp', '')}  {entry.get('event', '')}"
                )
            failures += 1
        else:
            _check(".agent-history.log clean (no unresolved issues)", True)
    print()

    # ── Credentials and the shell ────────────────────────────────────────────
    # Warnings, not failures: where a key lives is the operator's choice, and
    # the loader already makes a repository's .env win over the shell.
    print("Credentials:")
    exported = exported_credentials(Path.home())
    _check("no credential exported in a shell profile", not exported,
           "; ".join(exported) + " — keep keys in each repository's .env (gitignored), not in a profile",
           warn_only=True)
    shadowed = shadowed_credentials(root, _AMBIENT)
    _check("no shell credential differs from this repository's .env", not shadowed,
           ", ".join(shadowed) + " — the .env value is used; unset the export, or name it in tenant.yaml "
           "`env_overrides` to let the shell win", warn_only=True)
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("═══════════════════════════════════════════════════")
    if failures == 0:
        print("  🎉  All checks passed — environment ready")
    else:
        print(f"  🛑  {failures} check(s) failed — resolve issues above")
    print("═══════════════════════════════════════════════════")

    return failures == 0


def check_security() -> bool:
    """
    Smoke subset of the unified security harness (SEC-PII-001/002 + audit).

    Delegates to scripts/run-security-checks.py --mode smoke.
        python3 scripts/verify_system.py --check-security
    """
    root = Path(__file__).resolve().parent.parent
    script = root / "scripts" / "run-security-checks.py"

    print("═══════════════════════════════════════════════════")
    print("  Security Harness Smoke Check")
    print("═══════════════════════════════════════════════════\n")

    if not script.exists():
        _check("run-security-checks.py present", False, f"missing {script}")
        return False

    proc = subprocess.run(
        [sys.executable, str(script), "--mode", "smoke"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    detail = (proc.stderr or proc.stdout or "").strip()
    if len(detail) > 400:
        detail = detail[:400] + "…"
    ok = proc.returncode == 0
    _check("security harness smoke (--mode smoke)", ok, detail)
    print()
    print("═══════════════════════════════════════════════════")
    if ok:
        print("  🎉  Security smoke passed")
    else:
        print("  🛑  Security smoke failed")
    print("═══════════════════════════════════════════════════")
    return ok


def check_redaction() -> bool:
    """
    CI validation for §27 trace redaction. Runs the active redaction profile
    (from $ENVIRONMENT) against fixture payloads containing known secret/PII
    patterns and fails if any raw pattern survives scrubbing.

    TWO LEVELS, and the second is the one that matters. The fixture loop below
    calls `redactor._scrub(...)` with a string — it proves the PATTERN LIBRARY
    works, and it proved that happily throughout the period when the redactor
    was not redacting anything at all: `on_end` raised TypeError on every real
    span because a finished span's attributes are immutable, and this gate
    never called `on_end`. It also passed while every SEQUENCE-valued attribute
    exported unscrubbed, because it only ever handed the scrubber a `str`.

    So a span now goes through a real TracerProvider with the redactor attached
    and the assertions are made on what the EXPORTER received. A control is
    what reaches the wire, not what a helper returns.

    Used by cd-staging.yml / cd-production.yml:
        python3 scripts/verify_system.py --check-redaction
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from runtime.trace_redactor import TraceRedactor

    redactor = TraceRedactor()
    fixtures = [
        # not-a-secret: the string this test proves gets scrubbed
        "Authorization: Bearer sk-ant-abcdefghijklmnopqrstuvwxyz0123456789",
        "contact support at someone@example.com about order 4111-1111-1111-1111",
        # not-a-secret: the string this test proves gets scrubbed
        "raw key sk-abcdefghijklmnopqrstuvwxyz0123456789",
    ]

    print("═══════════════════════════════════════════════════")
    print(f"  Redaction Compliance Check (profile: {redactor.profile})")
    print("═══════════════════════════════════════════════════\n")

    if redactor.profile == "none":
        _check(
            "ENVIRONMENT is development/testing — redaction check skipped",
            True,
            warn_only=True,
        )
        print("═══════════════════════════════════════════════════")
        return True

    failures = 0
    for fixture in fixtures:
        scrubbed = redactor._scrub(
            fixture, hash_identifiers=(redactor.profile == "staging")
        )
        if redactor.profile == "production":
            scrubbed = redactor._truncate(scrubbed)
        leaked = (
            ("sk-" in scrubbed) or ("@example.com" in scrubbed) or ("4111" in scrubbed)
        )
        if not _check(
            f"fixture scrubbed: {fixture[:40]}...", not leaked, f"leaked → {scrubbed!r}"
        ):
            failures += 1

    # ── The control, not the helper ──────────────────────────────────────────
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
    except ImportError:
        _check(
            "opentelemetry not installed — the end-to-end span check cannot run "
            "(nothing is exporting spans on this host either)",
            True,
            warn_only=True,
        )
    else:
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(TraceRedactor())
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        try:
            with provider.get_tracer("verify_system").start_as_current_span("probe") as span:
                span.set_attribute("input.value", fixtures[1])
                # A SEQUENCE, because that is a first-class OTel attribute type
                # and the scrub loop used to skip it entirely.
                span.set_attribute("docs", [fixtures[0], fixtures[2]])
            spans = exporter.get_finished_spans()
        except Exception as exc:  # a redactor that raises out of span.end()
            _check(f"a real span survives export ({exc})", False)
            failures += 1
            spans = []

        if not _check("the redactor emitted a span at all", bool(spans)):
            failures += 1
        else:
            attrs = dict(spans[0].attributes)
            rendered = " ".join(
                part
                for value in attrs.values()
                for part in (value if isinstance(value, (list, tuple)) else [value])
                if isinstance(part, str)
            )
            for marker, what in (("sk-", "an API key"), ("@example.com", "an email"), ("4111", "a card number")):
                if not _check(
                    f"{what} does not survive to the exporter",
                    marker not in rendered,
                    f"leaked → {rendered[:120]!r}",
                ):
                    failures += 1

    print()
    print("═══════════════════════════════════════════════════")
    if failures == 0:
        print("  🎉  Redaction compliance passed")
    else:
        print(f"  🛑  {failures} fixture(s) leaked raw secret/PII patterns")
    print("═══════════════════════════════════════════════════")
    return failures == 0


def check_idempotency() -> bool:
    """
    CI validation for the idempotency store (runtime/idempotency.py) against
    a real Postgres — requires DATABASE_URL pointing at a throwaway database.

        DATABASE_URL=postgresql://test:test@localhost:5432/test \
            IDEMPOTENCY_BACKEND=postgres python3 scripts/verify_system.py --check-idempotency
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault("IDEMPOTENCY_BACKEND", "postgres")
    from runtime.idempotency import IdempotencyStore, make_key

    print("═══════════════════════════════════════════════════")
    print("  Idempotency Store Check")
    print("═══════════════════════════════════════════════════\n")

    failures = 0
    try:
        store = IdempotencyStore()
        key = make_key({"check": "verify_system", "nonce": time.time()})

        if not _check("cache miss before first write", store.get(key) is None):
            failures += 1

        store.set(key, {"ok": True}, ttl_seconds=60)
        if not _check("cache hit after write", store.get(key) == {"ok": True}):
            failures += 1

        store.set(key, {"ok": True}, ttl_seconds=0)
        time.sleep(1)
        if not _check("entry expired after ttl_seconds=0", store.get(key) is None):
            failures += 1
    except Exception as exc:
        _check("idempotency store reachable", False, str(exc))
        failures += 1

    print()
    print("═══════════════════════════════════════════════════")
    print(
        "  🎉  Idempotency check passed"
        if failures == 0
        else f"  🛑  {failures} check(s) failed"
    )
    print("═══════════════════════════════════════════════════")
    return failures == 0


def check_dlq() -> bool:
    """
    CI validation for the dead-letter queue (runtime/dead_letter.py) against
    a real Postgres — requires DATABASE_URL pointing at a throwaway database.

        DATABASE_URL=postgresql://test:test@localhost:5432/test \
            python3 scripts/verify_system.py --check-dlq
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from runtime.dead_letter import DeadLetterQueue

    print("═══════════════════════════════════════════════════")
    print("  Dead-Letter Queue Check")
    print("═══════════════════════════════════════════════════\n")

    failures = 0
    try:
        dlq = DeadLetterQueue()
        tenant_id = f"verify-system-{int(time.time())}"
        entry = dlq.enqueue(
            payload={"check": "verify_system"}, error="synthetic", tenant_id=tenant_id
        )

        pending = [e.task_id for e in dlq.list(tenant_id=tenant_id, status="pending")]
        if not _check(
            "enqueued entry appears in pending list", entry.task_id in pending
        ):
            failures += 1

        replay_calls = []
        dlq_with_handler = DeadLetterQueue(
            replay_handler=lambda e: replay_calls.append(e.task_id)
        )
        dlq_with_handler.replay(entry.task_id)
        if not _check(
            "replay_handler invoked with the right task_id",
            replay_calls == [entry.task_id],
        ):
            failures += 1

        replayed = [e.task_id for e in dlq.list(tenant_id=tenant_id, status="replayed")]
        if not _check("entry moved to replayed status", entry.task_id in replayed):
            failures += 1

        entry2 = dlq.enqueue(
            payload={"check": "discard"}, error="synthetic", tenant_id=tenant_id
        )
        dlq.discard(entry2.task_id)
        discarded = [
            e.task_id for e in dlq.list(tenant_id=tenant_id, status="discarded")
        ]
        if not _check(
            "discarded entry moved to discarded status", entry2.task_id in discarded
        ):
            failures += 1

        try:
            dlq.replay("nonexistent-task-id")
            _check(
                "replay() raises KeyError for unknown task_id", False, "did not raise"
            )
            failures += 1
        except KeyError:
            _check("replay() raises KeyError for unknown task_id", True)
    except Exception as exc:
        _check("DLQ reachable", False, str(exc))
        failures += 1

    print()
    print("═══════════════════════════════════════════════════")
    print(
        "  🎉  DLQ check passed"
        if failures == 0
        else f"  🛑  {failures} check(s) failed"
    )
    print("═══════════════════════════════════════════════════")
    return failures == 0


def check_hooks() -> bool:
    """
    CI validation for the commit guardrails and the enterprise RFC checks
    (docs/process-gates.md › commit_guardrails). Until 3.0.0 the machine-wide
    hooks/pre-commit and hooks/commit-msg made them; the gate does now
    (.agent-rfc/designs/vendoring-retired.md). Each scenario commits through
    this checkout's own .githooks in a throwaway repository, so a regression in
    the hook, the launcher or the gate fails CI rather than a tenant's commit.
    """
    import shutil
    import tempfile

    repo_root = Path(__file__).resolve().parent.parent
    hooks = ("commit-msg", "pre-commit", "pre-push", "process-gate")

    print("═══════════════════════════════════════════════════")
    print("  Commit Guardrails / Enterprise RFC Check")
    print("═══════════════════════════════════════════════════\n")

    failures = 0
    # Assembled, not written whole: a shipped file that spells a marker trips
    # the very check it exercises (.agent-rfc/designs/first-commit-guardrail.md).
    marker_line = "ponytail" + ": decide the schema\n"

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)

        def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
            return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                                  env=env, capture_output=True, text=True, check=False)

        def _repo(name: str, guardrails: Optional[str] = None) -> Path:
            repo = tmp / name
            (repo / ".githooks").mkdir(parents=True)
            for hook in hooks:
                shutil.copy(repo_root / ".githooks" / hook, repo / ".githooks" / hook)
                (repo / ".githooks" / hook).chmod(0o755)
            config: dict = {"gated": ["*.py", ".agenticframework/**", ".githooks/**"],
                            "not_gated": ["**.md", ".agent-rfc/**"],
                            "levers_doc": "@framework/docs/review-levers.md",
                            "design_checklist": "@framework/docs/design-review-checklist.md"}
            if guardrails is not None:
                config["commit_guardrails"] = guardrails
            (repo / ".agenticframework").mkdir()
            (repo / ".agenticframework" / "process-gates.json").write_text(json.dumps(config))
            subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
            _git(repo, "add", "-A")
            _git(repo, "commit", "-qm", "chore: base", "--no-verify")
            _git(repo, "config", "core.hooksPath", ".githooks")
            return repo

        def _commit(repo: Path, rel: str, text: str, message: str) -> subprocess.CompletedProcess:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(text)
            _git(repo, "add", "-A")
            return _git(repo, "commit", "-q", "-m", message)

        home = tmp / "home"
        home.mkdir()
        env = {**os.environ, "HOME": str(home), "AGENTSMITH_DIR": str(repo_root),
               "AGENTSMITH_PYTHON": sys.executable, "AGENTSMITH_STATE_DIR": str(tmp / "state")}
        for name in ("GITHUB_STEP_SUMMARY", "CLAUDE_PROJECT_DIR"):
            env.pop(name, None)

        # Scenario 1: the repository turns the guardrails off -> a marker goes in.
        done = _commit(_repo("off", "off"), "notes/plan.txt", marker_line, "docs: plan")
        if not _check("commit_guardrails off: a staged marker is not checked (exit 0)",
                      done.returncode == 0, done.stdout + done.stderr):
            failures += 1

        # Scenario 2: undeclared, so on -> the commit is refused, naming the line.
        done = _commit(_repo("on"), "notes/plan.txt", marker_line, "docs: plan")
        if not _check("commit_guardrails on (the default): a staged marker blocks (exit 1)",
                      done.returncode != 0 and "notes/plan.txt:1: an unresolved AI marker" in done.stderr,
                      done.stdout + done.stderr):
            failures += 1

        # Scenario 3: an org policy on the machine, no RFC-NNN in the message -> refused.
        (home / ".agent-framework").mkdir()
        (home / ".agent-framework" / "agenticframework-org.yaml").write_text("hooks:\n  bypass_policy: disabled\n")
        enterprise = _repo("enterprise")
        done = _commit(enterprise, ".agent-rfc/001-plan.md", "# RFC-001\n", "docs: plan")
        if not _check("enterprise, no RFC-NNN in the message: the commit blocks (exit 1)",
                      done.returncode != 0 and "RFC-NNN" in done.stderr, done.stdout + done.stderr):
            failures += 1

        # Scenario 4: the same, with RFC-001 in the message and the RFC present -> passes.
        done = _git(enterprise, "commit", "-q", "-m", "docs: plan (RFC-001)")
        if not _check("enterprise, RFC-001 in the message and an RFC present: the commit passes (exit 0)",
                      done.returncode == 0, done.stdout + done.stderr):
            failures += 1

    print()
    print("═══════════════════════════════════════════════════")
    print(
        "  🎉  Commit guardrail check passed"
        if failures == 0
        else f"  🛑  {failures} check(s) failed"
    )
    print("═══════════════════════════════════════════════════")
    return failures == 0


def _kg_shape(kg_path: Path) -> Optional[str]:
    """The graph's meaning, with the parts that legitimately churn removed.

    Compared instead of raw bytes for two reasons:

    * `last_modified` is a file mtime. `actions/checkout` stamps the working
      tree at checkout time, so on CI every node's mtime differs from the
      committed graph's and a byte compare would report drift on every run —
      a gate that always fails is as useless as one that never does.
    * Node and edge order is an artifact of a directory walk, not of content.

    What remains — which files exist, their language, their symbols, and the
    import edges between them — is exactly what goes stale when someone edits
    code and does not regenerate.

    KNOWN LIMIT: map_codebase skips files whose stored mtime still matches, at
    1-second granularity, so an edit made within the same second as the last
    regeneration is not re-parsed and this check passes. Irrelevant in CI —
    actions/checkout stamps every file fresh, so nothing is ever skipped — and
    self-correcting locally on the next run once the clock ticks.
    """
    if not kg_path.exists():
        return None
    try:
        data = json.loads(kg_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    tracked = _git_tracked_files()
    if tracked is None:
        return None

    # GIT-TRACKED NODES ONLY. The mapper maps what git holds
    # (kg-maps-what-git-tracks.md): tracked files, and untracked ones no ignore
    # rule covers. The second half still differs between a working tree and a
    # fresh runner, so this compares tracked paths alone. Two kinds of node
    # differed on every run before that filter existed:
    #
    #   portal/next-env.d.ts   written by `next build`, gitignored. Present on
    #                          any machine that had built the portal, absent on
    #                          a fresh runner.
    #   rfc:fixtures/…         Guardrail nodes from GENERATED, gitignored .agent-rfc
    #                          docs (delivery_evidence.md), each storing an
    #                          ABSOLUTE source_file path.
    #
    # Comparing those made the gate fail on every CI run — a false-positive
    # gate, which is worse than the weak one it replaced, because the fix is to
    # delete it.
    #
    # The remedy for the second one used to be excluding the whole Guardrail
    # NODE TYPE, which took the true positives with it: beeb838 committed a
    # graph missing rfc:reviews/design-tree-drift-is-a-pytest-test.md, this
    # function reported no drift, and all 11 checks passed over it — 7 of them
    # required for the merge. Of the 184
    # Guardrails in the graph, 184 were git-tracked and none was compared. The
    # filter is trackedness, the same test the files get — a Guardrail's
    # source_file is the repo-relative path of the rfc document it came from,
    # so a generated one is excluded by the rule rather than by its type, and an
    # absolute path is excluded because _git_tracked_files returns relative ones
    # and an absolute path is never a member.
    nodes = sorted(
        (
            n.get("id"),
            n.get("language"),
            tuple(sorted(n.get("symbols") or [])),
        )
        for n in data.get("nodes", [])
        if n.get("node_type") == "CodebaseFile" and n.get("id") in tracked
    )
    # id, title and pillar — NOT created_at. local_knowledge_graph.add_guardrail
    # preserves an existing node's created_at and stamps now() only for a node
    # that is new, and a new node already differs by its presence. Comparing the
    # timestamp would make the shape depend on a clock, which is what
    # last_modified is excluded for.
    guardrails = sorted(
        (n.get("id"), n.get("title"), n.get("pillar"))
        for n in data.get("nodes", [])
        if n.get("node_type") == "Guardrail" and n.get("source_file") in tracked
    )
    raw_edges = data.get("edges", data.get("links", []))
    edges = sorted(
        (e.get("source"), e.get("target"), e.get("edge_type") or e.get("type"))
        for e in raw_edges
        if e.get("source") in tracked and e.get("target") in tracked
    )
    return json.dumps(
        {"nodes": nodes, "guardrails": guardrails, "edges": edges},
        sort_keys=True,
        default=str,
    )


def _git_tracked_files() -> Optional[set[str]]:
    """Repo-relative paths git knows about, or None if git cannot answer.

    None makes the caller skip the drift comparison rather than guess. Treating
    "git unavailable" as "nothing is tracked" would compare two empty shapes
    and report the graph up to date having examined no nodes at all.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return set(proc.stdout.split())


# What replaces each kind of framework copy a tenant may still hold
# (.agent-rfc/designs/vendoring-retired.md).
_COPY_REPLACEMENT = (
    ("scripts/", "the provider's ports, through .githooks/process-gate (gate, rules, evals, security) "
                 "or `agentsmith ops settings`"),
    ("runtime/", "the agentsmith-runtime package, pinned in your requirements, if your code imports it"),
    ("fixtures/security/", "the security provider's own registry and templates"),
    ("fixtures/", "the evals provider's own base datasets"),
    (".github/actions/", "`uses: bobbyaqlaar/AgentSmith/.github/actions/<name>@<release>`"),
)


def framework_copies(root: Path, framework: Path) -> list[tuple[str, str]]:
    """Files this repository tracks at a path AgentSmith ships as code — a copy,
    stale or not — each with what replaces it. By path, not content: a copy
    that drifted is still a copy. Nothing in AgentSmith's own checkout."""
    if (root / "install-ai-stack.sh").is_file() and (root / "workflow-templates").is_dir():
        return []
    tracked = subprocess.run(["git", "ls-files", "-z", "--", "scripts", "runtime", "fixtures", ".github/actions"],
                             cwd=root, capture_output=True, text=True, check=False).stdout.split("\0")
    copies = []
    for rel in filter(None, tracked):
        if rel.startswith("fixtures/") and not (rel.startswith("fixtures/security/") or
                                                 (rel.count("/") == 1 and rel.endswith("_base.json"))):
            continue
        if (framework / rel).is_file():
            why = next(text for prefix, text in _COPY_REPLACEMENT if rel.startswith(prefix))
            copies.append((rel, why))
    return copies


def check_governed() -> bool:
    """Is this repo actually governed? Every gap at once, never just the first.

    A check that stops at the first missing piece turns provisioning into a
    guessing game: fix one thing, run again, find the next. This lists them
    (.agent-rfc/designs/governance-enforcement.md, G7).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gate_history  # type: ignore

    root = _repo_root()
    print("═══════════════════════════════════════════════════")
    print("  Governed repository check")
    print("═══════════════════════════════════════════════════\n")
    gaps: list[str] = []

    def want(rel: str, why: str) -> None:
        if not (root / rel).exists():
            gaps.append(f"{rel} is missing — {why}")

    want(".agenticframework/process-gates.json", "the gates cover nothing until a repo declares what they cover")
    for hook in ("process-gate", "commit-msg", "pre-commit", "pre-push"):
        want(f".githooks/{hook}", "the commit gate and the sweep run from here")
    want(".claude/settings.json", "the edit gate is an IDE hook")
    want(".cursor/hooks.json", "the edit gate is an IDE hook")
    want(".agent-rfc/fixtures/knowledge_graph.json", "a review's scope is computed from the graph")
    want("docs/REVIEW_LOG.md", "one review log per repo (`artifacts`)")
    want("docs/DESIGN.md", "one design artifact per repo (`artifacts`)")

    copies = framework_copies(root, Path(__file__).resolve().parent.parent)
    if copies:
        gaps.append(f"{len(copies)} file(s) are a copy of AgentSmith's code, which 3.0.0 neither refreshes nor "
                    "runs — remove them; what replaces each is named below")
        by_kind: dict = {}
        for rel, why in copies:
            by_kind.setdefault(why, []).append(rel)
        for why, rels in by_kind.items():
            shown = ", ".join(rels[:5]) + (f" and {len(rels) - 5} more" if len(rels) > 5 else "")
            gaps.append(f"  {shown} → {why}")

    armed = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=root,
                           capture_output=True, text=True, check=False).stdout.strip()
    if armed != ".githooks":
        gaps.append("git config core.hooksPath is "
                    + (f"{armed!r}" if armed else "unset")
                    + " — the hooks are present but nothing runs them")

    config_path = root / ".agenticframework" / "process-gates.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            gaps.append(f"process-gates.json is not valid JSON ({exc})")
            config = {}
        if not config.get("gated"):
            gaps.append("process-gates.json gates no paths")
        if not config.get("registry"):
            gaps.append("process-gates.json declares no `registry` — the design-time rules are not adopted")

    # Kept apart from the list above on purpose: "this control is not
    # installed" and "this control is installed but has not been run for this
    # commit" are different facts, and a freshly scaffolded repo is the second
    # one. Reporting them as one number tells a new tenant its provisioning
    # failed, which is the wrong thing to go and fix (`ambiguous-signals`).
    unproven: list[str] = []
    run = gate_history.last_gates_run(root)
    if run is None:
        unproven.append("`agentsmith gates run` has never run in this clone — run it before pushing")
    elif run.get("only"):
        unproven.append(f"the last `agentsmith gates run` was filtered to {run['only']!r} — "
                        f"{run.get('passed')} gate(s) is not the list; run it without --only")
    elif run.get("commit") != gate_history.head(root):
        unproven.append(f"the last `agentsmith gates run` was for a different commit "
                        f"({str(run.get('commit'))[:12]}) — run it again for this one")
    else:
        print(f"  ℹ️   last `agentsmith gates run`: {run.get('passed')} passed, {run.get('failed')} failed, "
              f"{run.get('skipped')} skipped")
        if run.get("failed"):
            unproven.append(f"the last `agentsmith gates run` had {run['failed']} failing gate(s)")

    for gap in gaps:
        print(f"  ❌  {gap}")
    if not gaps:
        print("  ✅  every control this repo declares is present and armed")
    for gap in unproven:
        print(f"  ⏳  {gap}")
    print()
    print("═══════════════════════════════════════════════════")
    if gaps:
        print(f"  🛑  {len(gaps)} gap(s) in provisioning"
              + (f", and {len(unproven)} not yet proven" if unproven else ""))
    elif unproven:
        print("  ⏳  Provisioned, not yet proven — the controls are in place and armed")
    else:
        print("  🎉  Governed")
    print("═══════════════════════════════════════════════════")
    return not gaps and not unproven


def check_kg_fresh() -> bool:
    """Is the repository's committed graph what its code maps to now? The
    staleness half of `--check-kg`, for any governed repository — answered by
    the gate provider as `kg check` (contract/gate/v3/protocol.md). A repository
    with no graph yet passes with a warning: `kg build` makes one. The graph is
    regenerated in place, so a stale one is fixed by committing it."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import map_codebase  # type: ignore

    kg_path = fixtures_path("knowledge_graph.json")
    before = _kg_shape(kg_path)
    if before is None:
        print("⚠️  no .agent-rfc/fixtures/knowledge_graph.json yet — `agentsmith gate kg build` writes one")
        return True
    map_codebase.run_map(force=True)
    if before != _kg_shape(kg_path):
        print("❌ knowledge_graph.json was stale — it has just been regenerated in place; COMMIT "
              ".agent-rfc/fixtures/knowledge_graph.json (re-running now passes without the commit)")
        return False
    # Say what was compared. "up to date with the code" read as a guarantee
    # about the whole graph, and on beeb838 it was not one:
    # Guardrails were outside the comparison entirely. Naming the scope keeps a
    # green verdict from being read as more than it is — a design's BODY can
    # still change without its title, and the mapper stores no digest of that.
    # Parsed back from the shape rather than recounted from the graph: the
    # shape IS what was compared, so counting anything else would report a
    # scope the verdict does not rest on.
    counted = json.loads(before)
    print(
        "✅ knowledge_graph.json matches the code — compared "
        f"{len(counted['nodes'])} tracked file(s), {len(counted['guardrails'])} guardrail(s) "
        f"and {len(counted['edges'])} edge(s) by name, language, symbols, title and pillar"
    )
    return True


def check_kg() -> bool:
    """
    CI validation for the Knowledge Graph (docs/PRODUCT_ARCHIVE.md P10a, Pillar 2).
    Runs map_codebase.py against the framework's own codebase and asserts the
    resulting graph is non-empty with at least the known scripts/ file nodes.

        python3 scripts/verify_system.py --check-kg
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import map_codebase  # type: ignore

    print("═══════════════════════════════════════════════════")
    print("  Knowledge Graph Check (self-test.yml)")
    print("═══════════════════════════════════════════════════\n")

    kg_path = fixtures_path("knowledge_graph.json")
    # Captured BEFORE run_map() overwrites it. Without this the check only ever
    # proved the mapper runs: it regenerated the graph and then asserted things
    # about the graph it had just written, so a committed file stale by two
    # releases passed every time. Observed 2026-08-24 — the committed graph was
    # 703 lines behind the portal work and the gate had been green throughout.
    before = _kg_shape(kg_path)

    # force=True: this check's regeneration is the reference the committed
    # graph is measured against, so it must not inherit whatever the
    # incremental path last left behind. Without it a graph corrupted by
    # anything other than a file edit compares equal to itself forever.
    stats = map_codebase.run_map(force=True)
    print(f"  ℹ️   map_codebase.py: {stats}")

    failures = 0

    if not _check("knowledge_graph.json written", kg_path.exists()):
        failures += 1
        print()
        print("═══════════════════════════════════════════════════")
        print(f"  🛑  {failures} check(s) failed")
        print("═══════════════════════════════════════════════════")
        return False

    with kg_path.open() as fh:
        data = json.load(fh)

    nodes = data.get("nodes", [])
    node_ids = {n.get("id") for n in nodes}
    edges = data.get("edges", data.get("links", []))

    if not _check("Knowledge Graph is non-empty", len(nodes) > 0):
        failures += 1

    # The drift check the name promised — on SHAPE, not bytes. See _kg_shape:
    # a byte compare would fail every CI run, because actions/checkout stamps
    # working-tree mtimes at checkout time and every `last_modified` in a
    # freshly built graph would differ from the committed one.
    if before is not None and before != _kg_shape(kg_path):
        # run_map() above has ALREADY rewritten the file, so the working tree
        # is now correct and a second run of this check goes green. Say so, or
        # "just run it again" looks like a flaky gate instead of a reminder
        # that the fix is still uncommitted.
        _check(
            "knowledge_graph.json was stale — it has just been regenerated in "
            "place; COMMIT .agent-rfc/fixtures/knowledge_graph.json. "
            "(Re-running this check will now pass without the commit.)",
            False,
        )
        failures += 1
    else:
        _check("knowledge_graph.json is up to date with the code", True)

    known_files = {
        "scripts/map_codebase.py",
        "scripts/verify_system.py",
        "scripts/local_knowledge_graph.py",
    }
    missing = known_files - node_ids
    if not _check(
        f"known scripts/ file nodes present ({len(known_files)} expected)",
        not missing,
        f"missing: {missing}",
    ):
        failures += 1

    print(f"  ℹ️   {len(nodes)} nodes, {len(edges)} edges")

    print()
    print("═══════════════════════════════════════════════════")
    print(
        "  🎉  Knowledge Graph check passed"
        if failures == 0
        else f"  🛑  {failures} check(s) failed"
    )
    print("═══════════════════════════════════════════════════")
    return failures == 0


def check_onprem_deploy() -> bool:
    """
    Syntax/shape validation for templates/onprem-deploy/ (docs/UserManual.md
    D.6) — no live cluster or Docker daemon required beyond `docker
    compose config` and `helm template`'s own dry-run rendering. Renders
    both proxy engines' configs with canary+shadow+with-db all enabled
    (the densest combination) and asserts the output is valid YAML with
    the expected weighted/mirror shape, then does the same for the Helm
    chart across both proxyEngine values.

        python3 scripts/verify_system.py --check-onprem-deploy
    """
    import shutil
    import subprocess
    import tempfile

    import yaml

    print("═══════════════════════════════════════════════════")
    print("  On-Prem Deploy Template Check")
    print("═══════════════════════════════════════════════════\n")

    base = _repo_root() / "templates" / "onprem-deploy"
    failures = 0

    if not base.exists():
        _check("templates/onprem-deploy/ exists", False)
        return False
    _check("templates/onprem-deploy/ exists", True)

    have_docker = shutil.which("docker") is not None
    have_helm = shutil.which("helm") is not None

    if have_docker:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            env_file = tmp / ".env"
            env_file.write_text(
                "APP_IMAGE_PROD=ghcr.io/acme/app:abc1234\n"
                "APP_IMAGE_CANARY=ghcr.io/acme/app:canary\n"
                "APP_IMAGE_SHADOW=ghcr.io/acme/app:shadow\n"
                "APP_PORT=8080\nCANARY_WEIGHT_PERCENT=15\nSHADOW_MIRROR_PERCENT=100\n"
            )
            # render scripts read ./.env relative to the template dir — copy
            # the fixture env there for the duration of this check.
            shutil.copy(env_file, base / ".env")
            for engine in ("traefik", "envoy"):
                render_script = base / "scripts" / f"render-{engine}-config.py"
                r = subprocess.run(
                    ["python3", str(render_script)],
                    cwd=base,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                rendered_ok = r.returncode == 0
                if not _check(
                    f"{engine}: render script exits 0", rendered_ok, r.stdout + r.stderr
                ):
                    failures += 1

                cfg_file = (
                    base / "proxy" / "traefik" / "dynamic.rendered.yml"
                    if engine == "traefik"
                    else base / "proxy" / "envoy" / "envoy.rendered.yaml"
                )
                if cfg_file.exists():
                    try:
                        yaml.safe_load(cfg_file.read_text())
                        _check(f"{engine}: rendered config is valid YAML", True)
                    except yaml.YAMLError as e:
                        _check(
                            f"{engine}: rendered config is valid YAML", False, str(e)
                        )
                        failures += 1
                    cfg_file.unlink()

                result = subprocess.run(
                    [
                        "docker",
                        "compose",
                        "--env-file",
                        str(base / ".env"),
                        "-f",
                        str(base / "docker-compose.yml"),
                        "-f",
                        str(base / f"docker-compose.{engine}.yml"),
                        "--profile",
                        "canary",
                        "--profile",
                        "shadow",
                        "--profile",
                        "with-db",
                        "config",
                        "--quiet",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if not _check(
                    f"{engine}: docker compose config validates",
                    result.returncode == 0,
                    result.stderr,
                ):
                    failures += 1
            (base / ".env").unlink(missing_ok=True)
    else:
        _check(
            "docker available for compose validation",
            False,
            "skipped — docker not installed",
            warn_only=True,
        )

    if have_helm:
        chart = base / "kubernetes"
        result = subprocess.run(
            ["helm", "lint", str(chart)], capture_output=True, text=True, check=False
        )
        if not _check(
            "helm lint passes", result.returncode == 0, result.stdout + result.stderr
        ):
            failures += 1
        for set_args, label in [
            ([], "defaults"),
            (
                [
                    "--set",
                    "canary.enabled=true",
                    "--set",
                    "shadow.enabled=true",
                    "--set",
                    "withDb.enabled=true",
                    "--set",
                    "withDb.credentialsSecretName=db-creds",
                ],
                "canary+shadow+db",
            ),
            (["--set", "proxyEngine=envoy-gateway"], "envoy-gateway"),
        ]:
            result = subprocess.run(
                ["helm", "template", "verify-check", str(chart), *set_args],
                capture_output=True,
                text=True,
                check=False,
            )
            ok = result.returncode == 0
            if ok:
                try:
                    list(yaml.safe_load_all(result.stdout))
                except yaml.YAMLError as e:
                    ok = False
                    result.stderr += str(e)
            if not _check(
                f"helm template ({label}) renders valid YAML", ok, result.stderr
            ):
                failures += 1
    else:
        _check(
            "helm available for chart validation",
            False,
            "skipped — helm not installed",
            warn_only=True,
        )

    print()
    print("═══════════════════════════════════════════════════")
    print(
        "  🎉  On-prem deploy check passed"
        if failures == 0
        else f"  🛑  {failures} check(s) failed"
    )
    print("═══════════════════════════════════════════════════")
    return failures == 0


def check_delivery_model() -> bool:
    """
    Soft gate for Enterprise Delivery Model (docs/PRODUCT_ARCHIVE.md).

    If `.agenticframework/org-policy.yaml` defines `delivery_model`, warn when
    tenant `delivery.platform` / `data_access_pattern` are missing or not in
    the approved catalog. Never fails CI (warn-only).

        python3 scripts/verify_system.py --check-delivery-model
    """
    scripts_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts_dir))
    from delivery_model import check_tenant_against_policy  # type: ignore
    from _shared import _repo_root  # type: ignore

    print("═══════════════════════════════════════════════════")
    print("  Delivery Model Soft Gate")
    print("═══════════════════════════════════════════════════\n")

    result = check_tenant_against_policy(_repo_root())
    status = result["status"]
    if status == "skip":
        _check(
            "No delivery_model in org-policy — soft gate skipped",
            True,
            warn_only=True,
        )
    elif status == "ok":
        _check("Tenant delivery.* matches approved catalog", True)
    else:
        for warning in result.get("warnings") or []:
            _check(warning, False, warn_only=True)
        _check(
            "Delivery Model soft gate complete (warnings above; CI not failed)",
            True,
            warn_only=True,
        )

    print()
    print("═══════════════════════════════════════════════════")
    print("  Soft gate finished (ok_for_ci=True)")
    print("  Evidence pack: python3 scripts/delivery_evidence.py")
    print("═══════════════════════════════════════════════════")
    return True  # soft gate — never hard-fail


MODES = [
    ("--check-security", "security harness registry + control coverage"),
    ("--check-redaction", "trace redaction profile for $ENVIRONMENT"),
    ("--check-idempotency", "idempotency store round-trip"),
    ("--check-dlq", "dead-letter queue replay path"),
    ("--check-hooks", "the commit guardrails / enterprise RFC checks, through the gate"),
    ("--check-onprem-deploy", "on-prem bundle renders and self-checks"),
    ("--check-kg", "Knowledge Graph freshness (drift gate)"),
    ("--check-kg-fresh", "This repository's committed graph is current (the gate's `kg check`)"),
    ("--check-delivery-model", "delivery-model evidence soft gate"),
]


def _usage() -> None:
    """`--help` used to fall through to the full verification run.

    Every other entry point in scripts/ uses argparse and answers `--help` in
    the ordinary way. This one dispatches on `sys.argv` — nine `in sys.argv`
    tests — so `--help` matched none of them, fell through to `run_checks()`,
    and printed a multi-second system scan. Exit 0, no usage, and the nine
    modes below documented in five different .md files and discoverable from
    the tool itself nowhere.

    Which is the same shape as the rest of this file's subject matter: a
    command that quietly does something other than what it was asked, and
    reports success.
    """
    print("usage: verify_system.py [MODE]\n")
    print("Runs the full system verification when given no mode.\n")
    print("Modes (each runs exactly one check and exits non-zero on failure):")
    width = max(len(f) for f, _ in MODES)
    for flag, what in MODES:
        print(f"  {flag:<{width}}  {what}")
    print("\nThese are single-purpose CI entry points, not composable flags:")
    print("the first one matched wins and the rest are ignored.")


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        _usage()
        sys.exit(0)
    if "--check-redaction" in sys.argv:
        sys.exit(0 if check_redaction() else 1)
    if "--check-security" in sys.argv:
        sys.exit(0 if check_security() else 1)
    if "--check-idempotency" in sys.argv:
        sys.exit(0 if check_idempotency() else 1)
    if "--check-dlq" in sys.argv:
        sys.exit(0 if check_dlq() else 1)
    if "--check-hooks" in sys.argv:
        sys.exit(0 if check_hooks() else 1)
    if "--check-onprem-deploy" in sys.argv:
        sys.exit(0 if check_onprem_deploy() else 1)
    if "--check-kg-fresh" in sys.argv:
        sys.exit(0 if check_kg_fresh() else 1)
    if "--check-kg" in sys.argv:
        sys.exit(0 if check_kg() else 1)
    if "--governed" in sys.argv:
        sys.exit(0 if check_governed() else 1)
    if "--check-delivery-model" in sys.argv:
        sys.exit(0 if check_delivery_model() else 1)
    ok = run_checks()
    sys.exit(0 if ok else 1)
