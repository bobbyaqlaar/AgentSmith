"""
scripts/test/test_ops_contract.py — the Ops contract: what a running tenant tells
its portal, and what the portal sends back (.agent-rfc/designs/ops-contract.md,
contract/ops/v1/protocol.md).

The published files are held to the models; AgentSmith's senders — the worker's
run status, dead letters and settings, and `agentsmith ops settings` — are held
to the contract against a loopback receiver, and senders that follow a redirect
or carry a secret are shown failing; its replay webhook is held to the replay
side. The portal's receiver is held by portal/test/opsContract.test.ts and
opsIngestDb.test.ts, and by the self-test against a live portal.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from runtime import conformance as rc
from runtime import ops_contract as oc

V1 = REPO / "contract" / "ops" / "v1"
CLI = f"{sys.executable} -m runtime.cli"


@pytest.fixture
def repo_env(monkeypatch):
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("PYTHONPATH", str(REPO))
    monkeypatch.delenv(oc.URL_ENV, raising=False)
    monkeypatch.delenv(oc.TOKEN_ENV, raising=False)


# ── The published contract ────────────────────────────────────────────────────


def _bare(schema: dict) -> dict:
    return {k: v for k, v in schema.items() if k not in ("$schema", "$id", "title", "description")}


def test_the_message_schema_is_the_model():
    published = json.loads((V1 / "message.schema.json").read_text(encoding="utf-8"))
    assert _bare(published) == _bare(oc.MESSAGE.json_schema(by_alias=True))


def test_the_replay_schema_is_the_model():
    published = json.loads((V1 / "replay.schema.json").read_text(encoding="utf-8"))
    assert _bare(published) == _bare(oc.ReplayRequest.model_json_schema(by_alias=True))


def test_every_case_is_decided_by_the_model_as_the_contract_says():
    """The sender's models refuse exactly what a receiver must: a sender built on
    them cannot send a message the contract refuses."""
    cases = json.loads((V1 / "cases.json").read_text(encoding="utf-8"))["cases"]
    for case in cases:
        message = rc.ops_case_message(case, "t")
        try:
            oc.MESSAGE.validate_python(message)
            accepted = True
        except Exception:
            accepted = False
        assert accepted == (case["expect"] == 200), case["name"]


def test_the_portal_creates_the_dead_letter_table_the_runtime_does():
    """Two copies of one DDL that cannot import each other — Python and
    TypeScript — held equal column by column."""
    from runtime.dead_letter import _DLQ_DDL

    def columns(ddl: str) -> list[str]:
        body = ddl[ddl.index("(") + 1: ddl.rindex(")")]
        return [" ".join(line.split()) for line in body.strip().splitlines() if line.strip()]

    runtime_ddl = _DLQ_DDL[0] if isinstance(_DLQ_DDL, (list, tuple)) else _DLQ_DDL
    portal = (REPO / "portal" / "lib" / "dlq.ts").read_text(encoding="utf-8")
    portal_ddl = re.search(r"export const DLQ_DDL = `(.*?)`;", portal, re.S).group(1)
    assert columns(portal_ddl) == columns(runtime_ddl)


def test_the_protocol_is_declared_reference_documentation():
    config = json.loads((REPO / ".agenticframework" / "process-gates.json").read_text(encoding="utf-8"))
    assert "contract/ops/v1/protocol.md" in config["extends"]["artifacts"]["reference"]


# ── AgentSmith's senders ─────────────────────────────────────────────────────


def test_agentsmiths_settings_sender_passes_the_contract(tmp_path, repo_env):
    report = rc.run_ops_sender(f"{CLI} ops settings", tmp_path / "work")
    assert report.passed, report.render()


def _liar(tmp_path: Path, *, follow: bool = False, secret: bool = False) -> str:
    """A sender that follows a redirect, or copies the replay secret it found."""
    script = tmp_path / "liar.py"
    script.write_text(
        "import json, os, urllib.request, yaml\n"
        "doc = yaml.safe_load(open('.agenticframework/tenant.yaml'))\n"
        "body = {'schema': 1, 'kind': 'settings'}\n"
        + ("body['notes'] = doc['hitl']['replay_webhook_secret']\n" if secret else "")
        + "req = urllib.request.Request(os.environ['OPS_PORTAL_URL'] + '/api/ops/ingest', "
        "data=json.dumps(body).encode(), method='POST', headers={'Authorization': 'Bearer ' + "
        "os.environ['OPS_PORTAL_TOKEN'], 'Content-Type': 'application/json'})\n"
        + ("urllib.request.urlopen(req)\n" if follow else
           "try:\n    urllib.request.build_opener(type('N', (urllib.request.HTTPRedirectHandler,), "
           "{'redirect_request': lambda *a, **k: None})).open(req)\nexcept Exception as e:\n"
           "    raise SystemExit(0 if '503' in str(e) else 1)\n"))
    return f"{sys.executable} {script}"


def test_a_sender_that_follows_a_redirect_is_not_conformant(tmp_path):
    report = rc.run_ops_sender(_liar(tmp_path, follow=True), tmp_path / "work")
    assert not report.passed
    assert not next(c for c in report.checks if c.name == "a redirect is never followed").ok


def test_a_sender_that_carries_the_secret_is_not_conformant(tmp_path):
    report = rc.run_ops_sender(_liar(tmp_path, secret=True), tmp_path / "work")
    check = report.checks[0]
    assert not check.ok and "replay secret" in check.why


def test_send_never_follows_a_redirect_and_never_raises(monkeypatch):
    with rc._OpsLoopback() as portal:
        monkeypatch.setenv(oc.URL_ENV, portal.url)
        monkeypatch.setenv(oc.TOKEN_ENV, "aso_t")
        portal.mode = "redirect"
        assert oc.send(oc.SettingsMessage(budget_cap_usd=1)) == 302
        assert portal.followed == []
        monkeypatch.setenv(oc.URL_ENV, "http://127.0.0.1:9")  # nothing listens
        assert oc.send(oc.SettingsMessage()) is None


def test_send_says_nothing_and_sends_nothing_unconfigured(monkeypatch):
    monkeypatch.delenv(oc.URL_ENV, raising=False)
    monkeypatch.delenv(oc.TOKEN_ENV, raising=False)
    assert not oc.configured() and oc.send(oc.SettingsMessage()) is None


def test_settings_never_carry_a_secret_and_say_where_it_belongs(tmp_path):
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(
        "hitl:\n  replay_webhook_url: http://plain.example/replay\n  replay_webhook_secret: s3\n", encoding="utf-8")
    message, notes = oc.settings_from_tenant_yaml(tmp_path)
    assert "s3" not in message.model_dump_json()
    assert message.replay_webhook_url is None
    assert any("REPLAY_WEBHOOK_SECRET" in n for n in notes) and any("https" in n for n in notes)


def test_the_gateway_reports_run_status_by_the_contract_when_it_holds_an_ops_token(monkeypatch):
    from runtime.llm_gateway import LLMGateway

    sent = []
    monkeypatch.setattr(oc, "send", lambda message, **_k: sent.append(message) or 200)
    monkeypatch.setenv(oc.URL_ENV, "http://127.0.0.1:9")
    monkeypatch.setenv(oc.TOKEN_ENV, "aso_t")
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.tenant_id = "someone"
    gateway._report_run_status("run-1", "success", input_tokens=3)
    assert [(m.kind, m.run_id, m.status, m.input_tokens) for m in sent] == [("run", "run-1", "success", 3)]
    assert "tenant" not in sent[0].model_dump_json()


def test_the_gateway_keeps_the_deprecated_route_without_an_ops_token(monkeypatch, caplog):
    import httpx

    from runtime.llm_gateway import LLMGateway

    posted = []
    monkeypatch.delenv(oc.TOKEN_ENV, raising=False)
    monkeypatch.setenv("OPS_PORTAL_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("OPS_PORTAL_SYNC_TOKEN", "shared")
    monkeypatch.setattr(httpx, "post", lambda url, **k: posted.append(url))
    oc._warned.discard("legacy-run-status")
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.tenant_id = "t"
    with caplog.at_level("WARNING"):
        gateway._report_run_status("run-2", "success")
    assert posted == ["http://127.0.0.1:9/api/runs/ingest"]
    assert "deprecated" in caplog.text


def test_a_dead_letter_is_reported_with_its_error_bounded(monkeypatch):
    from runtime import dead_letter

    sent = []
    monkeypatch.setattr(oc, "send", lambda message, **_k: sent.append(message) or 200)
    monkeypatch.setenv(oc.URL_ENV, "http://127.0.0.1:9")
    monkeypatch.setenv(oc.TOKEN_ENV, "aso_t")
    entry = dead_letter.DLQEntry(task_id="t-1", tenant_id="x", payload={"when": object()}, error="e" * 5000,
                                 reason="crm_quota")
    dead_letter._report(entry)
    assert sent and sent[0].kind == "dead_letter" and len(sent[0].error) == oc.TEXT_LIMIT
    assert sent[0].reason == "crm_quota"


def test_the_worker_reports_its_settings_at_start_up(tmp_path, monkeypatch, capsys):
    from runtime import worker

    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text("budget:\n  monthly_usd_cap: 4\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    sent = []
    monkeypatch.setattr(oc, "send", lambda message, **_k: sent.append(message) or 200)
    monkeypatch.setenv(oc.URL_ENV, "http://127.0.0.1:9")
    monkeypatch.setenv(oc.TOKEN_ENV, "aso_t")
    worker._report_settings()
    assert [(m.kind, m.budget_cap_usd) for m in sent] == [("settings", 4.0)]
    assert "settings reported" in capsys.readouterr().err


# ── AgentSmith's replay webhook ──────────────────────────────────────────────


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_agentsmiths_replay_webhook_passes_the_contract(repo_env, monkeypatch):
    port = _free_port()
    env = {"REPLAY_WEBHOOK_SECRET": "conformance-replay-key", "PYTHONPATH": str(REPO),
           "PATH": "/usr/bin:/bin", "DATABASE_URL": "postgresql://nobody@127.0.0.1:9/none"}
    server = subprocess.Popen([sys.executable, "-m", "runtime.replay_webhook_server", str(port)], cwd=REPO, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        report = rc.run_ops_replay(f"http://127.0.0.1:{port}/replay", "conformance-replay-key")
    finally:
        server.terminate()
        server.wait(timeout=10)
    assert report.passed, report.render()


# ── `agentsmith ops settings` ────────────────────────────────────────────────


@pytest.mark.parametrize("mode, code", [("ok", 0), ("refuse", 1), ("redirect", 1), ("unwell", 0)])
def test_the_ci_sender_fails_on_configuration_and_warns_on_an_outage(tmp_path, repo_env, mode, code):
    root = rc.build_ops_fixture(tmp_path / "repo")
    with rc._OpsLoopback() as portal:
        portal.mode = mode
        done = subprocess.run([*CLI.split(), "ops", "settings"], cwd=root, capture_output=True, text=True, check=False,
                              env={**os.environ, oc.URL_ENV: portal.url, oc.TOKEN_ENV: "aso_t"})
    assert done.returncode == code, done.stdout + done.stderr


def test_a_long_error_summary_is_bounded_not_dropped(monkeypatch):
    """A run report over the contract's text limit would fail validation and
    never be sent; the gateway bounds it instead."""
    from runtime.llm_gateway import LLMGateway

    sent = []
    monkeypatch.setattr(oc, "send", lambda message, **_k: sent.append(message) or 200)
    monkeypatch.setenv(oc.URL_ENV, "http://127.0.0.1:9")
    monkeypatch.setenv(oc.TOKEN_ENV, "aso_t")
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.tenant_id = "t"
    gateway._report_run_status("run-3", "failed", error_summary="x" * 9000)
    assert len(sent) == 1 and len(sent[0].error_summary) == oc.TEXT_LIMIT
