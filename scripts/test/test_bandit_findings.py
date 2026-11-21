"""
scripts/test/test_bandit_findings.py — the findings Ruff's flake8-bandit rules
(`S`) raised that were real, each held by a test that fails on the code before
the fix (.agent-rfc/designs/ruff-s-rules.md).

Two kinds:
  - argument injection into git (CWE-88): a ref the operator or an event
    supplies, spelled like an option, was read as one — `--output=<path>` made
    `git diff` / `git show` write a file. The ref now follows --end-of-options.
  - URL schemes not restricted (S310): `urlopen` also serves `file:` and
    `ftp:`, and plain http carried a bearer token across the network in clear
    text. A configured URL must now be https, or http to this machine
    (localhost, 127.0.0.1, ::1) — `agentsmith.compliance.is_web_url`, the
    owner's rule of 2026-11-19.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import gate_kg
import process_gate

from agentsmith import compliance


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x"]
    subprocess.run(["git", "init", "-q", "--template=", str(root)], check=True)
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "one"], check=True)
    (root / "a.txt").write_text("b\n", encoding="utf-8")
    return root


# ── git: a ref is a ref, however it is spelled ───────────────────────────────


def test_a_diff_base_spelled_like_an_option_writes_no_file(repo, tmp_path):
    planted = tmp_path / "planted.txt"
    gate_kg.changed_files(f"--output={planted}", root=repo)
    assert not planted.exists()


def test_a_diff_base_that_is_a_ref_still_lists_the_change(repo):
    assert gate_kg.changed_files("HEAD", root=repo) == ["a.txt"]


def test_a_revision_spelled_like_an_option_writes_no_file(repo, tmp_path):
    planted = tmp_path / "planted.txt"
    read = process_gate._reader_at(repo, f"--output={planted}")
    assert read("a.txt") is None
    assert not list(tmp_path.glob("planted.txt*"))


def test_a_revision_that_is_a_ref_still_reads_the_file(repo):
    assert process_gate._reader_at(repo, "HEAD")("a.txt") == "a\n"


# ── URLs: https anywhere, plain http only to this machine ────────────────────

REMOTE_HTTP = "http://portal.example/api"


@pytest.mark.parametrize("url, allowed", [
    ("https://portal.example/api", True),
    ("https://10.0.0.5:11434", True),
    ("http://127.0.0.1:4318/v1/traces", True),
    ("http://localhost:6006", True),
    ("http://[::1]:8080/x", True),
    ("http://portal.example/api", False),
    ("http://10.0.0.5:11434", False),
    ("http://localhost.example/x", False),
    ("file:///etc/hosts", False),
    ("ftp://example.org/x", False),
    ("portal.example/api", False),
    ("", False),
])
def test_https_anywhere_and_http_only_to_loopback(url, allowed):
    assert compliance.is_web_url(url) is allowed


def _spooled(tmp_path, monkeypatch, endpoint):
    import gate_tracing as gt

    monkeypatch.setenv("AGENTSMITH_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", endpoint)
    gt.spool_dir().mkdir(parents=True)
    (gt.spool_dir() / "batch.pb").write_bytes(b"\x00")
    return gt


def test_shipping_spans_to_a_file_url_keeps_them_and_says_why(tmp_path, monkeypatch):
    """Before: urlopen served the file, its status was None, and the comparison
    raised TypeError out of ship() — the hook crashed instead of keeping the spans."""
    target = tmp_path / "collector"
    target.write_text("not a collector", encoding="utf-8")
    gt = _spooled(tmp_path, monkeypatch, target.as_uri())

    result = gt.ship()

    assert result.sent == 0 and result.kept == 1
    assert result.errors and "must be https" in result.errors[0]
    assert (gt.spool_dir() / "batch.pb").exists()


def test_shipping_spans_over_plain_http_to_another_host_is_refused(tmp_path, monkeypatch):
    gt = _spooled(tmp_path, monkeypatch, "http://collector.example:4318/v1/traces")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("opened"))

    result = gt.ship()

    assert result.kept == 1 and "must be https" in result.errors[0]


def _audit(tmp_path, monkeypatch, url):
    from agentsmith.machine import policy

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(compliance, "outbound_allowed", lambda _url: True)
    opened = []

    def urlopen(request, **_kwargs):
        opened.append(request.full_url)
        raise OSError("not a real portal")

    # Both ways a request leaves: urlopen, and an opener (the no-redirect one).
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda self, request, *a, **k: urlopen(request))
    policy.audit_log_event("config_change", "actor", "tenant", {},
                           env={"OPS_PORTAL_URL": url, "AUDIT_LOG_WRITE_TOKEN": "t"})
    log = tmp_path / ".agent-framework" / "local-audit-fallback.log"
    [record] = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    return opened, record["reason"]


@pytest.mark.parametrize("url", ["file:///tmp/portal", REMOTE_HTTP])
def test_an_audit_event_is_not_sent_in_clear_or_to_a_file(tmp_path, monkeypatch, url):
    opened, reason = _audit(tmp_path, monkeypatch, url)
    assert not opened and reason == "ops_portal_url_not_https"


@pytest.mark.parametrize("url", ["https://portal.example", "http://127.0.0.1:3000"])
def test_an_audit_event_is_sent_over_https_or_to_loopback(tmp_path, monkeypatch, url):
    opened, reason = _audit(tmp_path, monkeypatch, url)
    assert opened == [f"{url}/api/audit/append"] and reason == "ops_portal_write_failed"


def _webhook(monkeypatch, url, allowed=True):
    import notifier

    opened = []
    monkeypatch.setattr(notifier, "WEBHOOK_URL", url)
    monkeypatch.setattr(compliance, "outbound_allowed", lambda _url: allowed)
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, **k: opened.append(request.full_url))
    started = []
    real_start = threading.Thread.start

    def start(self):
        started.append(self)
        real_start(self)

    monkeypatch.setattr(threading.Thread, "start", start)
    notifier._send_webhook("title", "message")
    for thread in started:
        thread.join(timeout=5)
    assert started
    return opened


@pytest.mark.parametrize("url", ["file:///etc/hosts", "http://hooks.example/x"])
def test_the_webhook_is_not_opened_in_clear_or_for_a_file(monkeypatch, url):
    assert _webhook(monkeypatch, url) == []


@pytest.mark.parametrize("url", ["https://hooks.example/x", "http://localhost:9000/x"])
def test_the_webhook_is_opened_over_https_or_to_loopback(monkeypatch, url):
    assert _webhook(monkeypatch, url) == [url]


@pytest.mark.parametrize("url", ["file:///etc/hosts", "http://receiver.example/ingest"])
def test_a_conformance_receiver_must_be_https_or_loopback(url):
    from agentsmith import conformance

    with pytest.raises(ValueError, match="must be https"):
        conformance.run_record_receiver(url, "token")
    with pytest.raises(ValueError, match="must be https"):
        conformance._post_status(url, {}, "token")


def test_a_loopback_conformance_receiver_is_still_reached():
    from agentsmith import conformance

    # Port 9 on loopback refuses the connection: "nothing answered", not a refusal by rule.
    assert conformance._post_status("http://127.0.0.1:9/ingest", {}, "token") == 0


@pytest.mark.parametrize("base", ["file:///etc", "http://10.0.0.5:11434"])
def test_the_sovereign_probe_refuses_clear_text_to_another_host(monkeypatch, base):
    import verify_sovereign_endpoint as vse

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("opened"))
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda *a, **k: pytest.fail("opened"))
    with pytest.raises(ValueError, match="must be https"):
        vse._chat(base, "model", "prompt")


@pytest.mark.parametrize("base, cause", [("https://", "has no host"), ("https:evil.com", "has no host"),
                                         ("http://[::1:6006", "does not parse")])
def test_the_sovereign_probe_refuses_an_address_with_no_host_or_that_does_not_parse(monkeypatch, base, cause):
    """Pass 7: the probe's own copy let a hostless address reach urlopen, and a
    malformed one raised urlparse's "Invalid IPv6 URL", which names no setting."""
    import verify_sovereign_endpoint as vse

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("opened"))
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda *a, **k: pytest.fail("opened"))
    with pytest.raises(ValueError, match=cause):
        vse._chat(base, "model", "prompt")


def test_the_shipped_sovereign_template_passes_the_probe_rule():
    """templates/uae-sovereign/env.example's OLLAMA_BASE_URL is what an operator
    copies; the probe must not refuse the value the template ships (Q1, strict)."""
    from _shared import is_web_url

    env = REPO / "templates" / "uae-sovereign" / "env.example"
    values = [line.split("=", 1)[1].strip() for line in env.read_text(encoding="utf-8").splitlines()
              if line.startswith("OLLAMA_BASE_URL=")]
    assert values, "env.example no longer sets OLLAMA_BASE_URL"
    assert all(is_web_url(v) for v in values), values


@pytest.mark.parametrize("base", ["https://10.0.0.5:11434", "http://127.0.0.1:11434"])
def test_the_sovereign_probe_reaches_https_or_loopback(monkeypatch, base):
    import verify_sovereign_endpoint as vse

    opened = []

    def urlopen(request, **_kwargs):
        opened.append(request.full_url)
        raise OSError("no server")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda self, request, *a, **k: urlopen(request))
    with pytest.raises(OSError):
        vse._chat(base, "model", "prompt")
    assert opened == [f"{base}/v1/chat/completions"]


# ── Token-sending sites (.agent-rfc/designs/ruff-s-rules.md, Pass 7) ─────────
# A portal token or a secret webhook URL went to the configured address with
# only the residency check in front of it, which allows everything when no
# profile is declared. Each test fails on the code before the rule: the secret
# crossed the network over plain http.


def test_the_ops_token_is_not_sent_in_clear_to_another_host(monkeypatch, caplog):
    import httpx

    from agentsmith import ops_contract as oc

    monkeypatch.setenv(oc.URL_ENV, REMOTE_HTTP)
    monkeypatch.setenv(oc.TOKEN_ENV, "aso_t")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("the token was sent"))
    oc._warned.clear()
    with caplog.at_level("WARNING"):
        assert oc.send(oc.RunMessage(run_id="r", status="success")) is None
    assert "must be https" in caplog.text and oc.URL_ENV in caplog.text


def test_the_deprecated_route_does_not_send_the_shared_token_in_clear(monkeypatch, caplog):
    import httpx

    from agentsmith import ops_contract as oc
    from agentsmith.llm_gateway import LLMGateway

    posted = []
    monkeypatch.delenv(oc.TOKEN_ENV, raising=False)
    monkeypatch.setenv("OPS_PORTAL_URL", REMOTE_HTTP)
    monkeypatch.setenv("OPS_PORTAL_SYNC_TOKEN", "shared")
    monkeypatch.setattr(httpx, "post", lambda url, **k: posted.append(url))
    oc._warned.clear()
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.tenant_id = "t"
    with caplog.at_level("WARNING"):
        gateway._report_run_status("run-2", "success")
    assert posted == []
    assert "must be https" in caplog.text


def test_signatures_are_not_sent_in_clear_inside_the_boundary(tmp_path, monkeypatch):
    import httpx

    import compliance_port as cp
    from test_compliance_port import _repo

    monkeypatch.chdir(_repo(tmp_path))  # boundary: x.example.ae
    monkeypatch.setenv("OPS_PORTAL_URL", "http://x.example.ae")
    monkeypatch.setenv("OPS_PORTAL_TOKEN", "t")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("the token was sent"))
    records, why = cp.exchange([])
    assert records == [] and "must be https" in why


def _dead_letter_notify(monkeypatch, url):
    import httpx

    from agentsmith import dead_letter

    posted = []
    monkeypatch.delenv("TEAMS_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", url)
    monkeypatch.setattr(httpx, "post", lambda target, **k: posted.append(target))
    dead_letter._notify("t", "task", "r", "e")
    return posted


def test_a_dead_letter_webhook_in_clear_is_not_called_and_not_logged(monkeypatch, caplog):
    with caplog.at_level("WARNING", logger="agentsmith.dead_letter"):
        assert _dead_letter_notify(monkeypatch, "http://hooks.example/T000/B000/placeholder") == []
    assert "SLACK_WEBHOOK_URL" in caplog.text and "must be https" in caplog.text
    assert "hooks.example" not in caplog.text  # the URL is the secret


def test_a_dead_letter_webhook_over_https_is_still_called(monkeypatch):
    assert _dead_letter_notify(monkeypatch, "https://hooks.example/x") == ["https://hooks.example/x"]


def test_the_runtime_conformance_token_is_not_sent_in_clear(monkeypatch):
    import httpx

    from agentsmith import conformance

    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("the token was sent"))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("the token was sent"))
    checks = conformance.run_runtime("http://receiver.example", "tok")
    assert [(name, ok) for name, ok, _why in checks] == [("receiver address", False)]
    assert "must be https" in checks[0][2]


# ── Pass 8 (.agent-rfc/designs/ruff-s-rules.md, items H, K, L) ───────────────


def _redirecting_pair():
    """Two loopback servers: the first answers every request with a 302 to the
    second, and the second records the Authorization header it is sent. A URL
    that passes the rule must not carry the token on to wherever a 3xx points."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    seen: list = []

    class Target(BaseHTTPRequestHandler):
        def _answer(self):
            seen.append(self.headers.get("Authorization"))
            body = b'{"choices": [{"message": {"content": "ok"}}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._answer()

        def do_POST(self):
            self._answer()

        def log_message(self, *_args):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)

    class Redirect(BaseHTTPRequestHandler):
        def _answer(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/elsewhere")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            self._answer()

        def do_POST(self):
            self._answer()

        def log_message(self, *_args):
            pass

    first = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    for server in (target, first):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{first.server_port}", seen, (first, target)


@pytest.fixture()
def redirecting():
    url, seen, servers = _redirecting_pair()
    yield url, seen
    for server in servers:
        server.shutdown()
        server.server_close()


def test_the_audit_token_does_not_follow_a_redirect(tmp_path, monkeypatch, redirecting):
    from agentsmith.machine import policy

    url, seen = redirecting
    monkeypatch.setenv("HOME", str(tmp_path))
    policy.audit_log_event("config_change", "actor", "tenant", {},
                           env={"OPS_PORTAL_URL": url, "AUDIT_LOG_WRITE_TOKEN": "PLACEHOLDER-TOKEN"})
    assert seen == [], "the redirect target was sent the request"
    log = tmp_path / ".agent-framework" / "local-audit-fallback.log"
    [record] = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert record["reason"] == "ops_portal_write_failed"


def test_the_probe_token_does_not_follow_a_redirect(redirecting):
    import urllib.error

    import verify_sovereign_endpoint as vse

    url, seen = redirecting
    with pytest.raises(urllib.error.HTTPError):
        vse._chat(url, "model", "prompt", token="PLACEHOLDER-TOKEN")
    assert seen == [], "the redirect target was sent the request"


@pytest.mark.parametrize("url, allowed", [("http://hooks.example/PLACEHOLDER-SECRET", True),
                                          ("https://hooks.example/PLACEHOLDER-SECRET", False)])
def test_a_refused_webhook_is_said_by_variable_never_by_url(monkeypatch, capsys, url, allowed):
    """Before: _post returned without a word, so an operator's alerts stopped
    silently after the upgrade (Pass 8, item K)."""
    assert _webhook(monkeypatch, url, allowed=allowed) == []
    err = capsys.readouterr().err
    assert "AGENT_NOTIFY_WEBHOOK" in err
    assert "PLACEHOLDER-SECRET" not in err and "hooks.example" not in err


def test_an_audit_write_refused_by_the_boundary_says_so(tmp_path, monkeypatch):
    """Before: recorded as ops_portal_not_configured, though it was configured
    (Pass 8, item L)."""
    from agentsmith.machine import policy

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(compliance, "outbound_allowed", lambda _url: False)
    policy.audit_log_event("config_change", "actor", "tenant", {},
                           env={"OPS_PORTAL_URL": "https://portal.example", "AUDIT_LOG_WRITE_TOKEN": "t"})
    log = tmp_path / ".agent-framework" / "local-audit-fallback.log"
    [record] = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert record["reason"] == "ops_portal_outside_boundary"
