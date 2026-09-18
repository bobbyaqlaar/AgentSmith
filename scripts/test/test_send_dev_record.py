"""
scripts/test/test_send_dev_record.py — sending the gate's record to the portal
(portal phase 1, S7).

A repository without a portal is not a failed build; a portal that refuses the
record is; a portal that is down is a warning, because the gate's verdict does
not depend on it. Tested against a local HTTP server standing in for the portal.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SENDER = REPO / "scripts" / "send_dev_record.py"


class Portal:
    """A stand-in portal that answers with a set status and records what it got."""

    def __init__(self, status: int = 200, body: dict | None = None):
        self.status = status
        self.body = body or {"stored": 1}
        self.received: list[tuple[str, dict]] = []
        portal = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("content-length", 0))
                body = json.loads(self.rfile.read(length))
                portal.received.append((self.headers.get("authorization", ""), body))
                data = json.dumps(portal.body).encode()
                self.send_response(portal.status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture()
def record(tmp_path):
    path = tmp_path / "dev-record.json"
    path.write_text(json.dumps({
        "schema": 1, "head": "a" * 40, "designs": [{"path": "x.md"}],
        "commits": [{"commit": "a" * 40, "subject": "feat: x"}],
    }))
    return path


def send(path: Path, url: str | None, token: str | None, extra_env: dict | None = None):
    env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true", **(extra_env or {})}
    if url is not None:
        env["AGENTSMITH_PORTAL_URL"] = url
    if token is not None:
        env["AGENTSMITH_PORTAL_INGEST_TOKEN"] = token
    command = [sys.executable, str(SENDER), str(path)]
    return subprocess.run(command, env=env, capture_output=True, text=True, check=False)


def test_without_a_portal_configured_it_says_so_and_succeeds(record):
    result = send(record, None, None)
    assert result.returncode == 0
    assert "::notice" in result.stdout and "AGENTSMITH_PORTAL_URL" in result.stdout


def test_a_stored_record_succeeds_with_the_token_as_a_bearer(record):
    portal = Portal(200, {"app": "acme", "stored": 1})
    try:
        result = send(record, portal.url, "asi_secret")
    finally:
        portal.close()
    assert result.returncode == 0, result.stdout
    [(auth, body)] = portal.received
    assert auth == "Bearer asi_secret"
    assert body["commits"][0]["subject"] == "feat: x"
    assert "asi_secret" not in result.stdout + result.stderr, "SECURITY: the token is never printed"


def test_a_refused_record_fails_the_step_with_the_portals_reason(record):
    portal = Portal(400, {"error": "commits[0].verdict must be one of …"})
    try:
        result = send(record, portal.url, "asi_secret")
    finally:
        portal.close()
    assert result.returncode == 1
    assert "::error" in result.stdout and "verdict" in result.stdout


def test_a_portal_that_is_down_is_a_warning_not_a_failure(record):
    portal = Portal(503, {"error": "database unavailable"})
    try:
        result = send(record, portal.url, "asi_secret")
    finally:
        portal.close()
    assert result.returncode == 0 and "::warning" in result.stdout

    unreachable = send(record, "http://127.0.0.1:9", "asi_secret")
    assert unreachable.returncode == 0 and "::warning" in unreachable.stdout


def test_security_a_plain_http_portal_is_refused_before_the_token_is_sent(record):
    result = send(record, "http://portal.example.com", "asi_secret")
    assert result.returncode == 1 and "https" in result.stdout
    assert "asi_secret" not in result.stdout + result.stderr, "the refusal must not print the token either"


def test_a_long_range_goes_in_parts_with_the_designs_last(tmp_path):
    path = tmp_path / "dev-record.json"
    commits = [{"commit": f"{i:040x}", "subject": f"c{i}"} for i in range(1200)]
    document = {"schema": 1, "head": commits[-1]["commit"], "designs": [{"path": "x.md"}], "commits": commits}
    path.write_text(json.dumps(document))
    portal = Portal(200)
    try:
        result = send(path, portal.url, "asi_secret")
    finally:
        portal.close()
    assert result.returncode == 0, result.stdout
    sizes = [len(body["commits"]) for _, body in portal.received]
    assert sizes == [500, 500, 200]
    assert [("designs" in body) for _, body in portal.received] == [False, False, True]
    assert portal.received[0][1]["commits"][0]["commit"] == commits[0]["commit"], "oldest first"


def test_no_record_file_is_a_warning(tmp_path):
    result = send(tmp_path / "missing.json", "https://portal.example.com", "asi_secret")
    assert result.returncode == 0 and "::warning" in result.stdout


def test_the_gate_names_the_ci_run_inside_github_actions(gated_repo, tmp_path):
    from test_process_gate import _git

    base = _git(gated_repo, "rev-parse", "HEAD").stdout.strip()
    _git(gated_repo, "commit", "-q", "--allow-empty", "-m", "docs: nothing", "--no-verify")
    out = tmp_path / "record.json"
    env = {"PATH": "/usr/bin:/bin", "GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "o/r",
           "GITHUB_RUN_ID": "42", "HOME": str(tmp_path)}
    gate = gated_repo / "scripts/process_gate.py"
    subprocess.run([sys.executable, str(gate), "ci", "--base", base, "--json", str(out)],
                   cwd=gated_repo, env=env, capture_output=True, text=True, check=False)
    assert json.loads(out.read_text())["ci_run_url"] == "https://github.com/o/r/actions/runs/42"
