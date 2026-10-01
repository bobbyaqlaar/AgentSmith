"""
runtime/test/test_intake.py — `agentsmith tenant init --from <id>`: pulling a
portal intake, re-validating it, scaffolding from it, and consuming it only once
it has landed (.agent-rfc/designs/portal-intake-pull.md).

Against a real HTTP server on 127.0.0.1 that serves contract/intake/v1/fixture.json
— the same record the portal's own tests pin — so the client is exercised over
a socket, not a mock of urllib.
"""

from __future__ import annotations

import copy
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from runtime import cli, intake

REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / "contract" / "intake" / "v1"
SCHEMA = json.loads((CONTRACT / "record.schema.json").read_text(encoding="utf-8"))
FIXTURE = json.loads((CONTRACT / "fixture.json").read_text(encoding="utf-8"))
ID = FIXTURE["intake_id"]
TOKEN = "asx_test-token-for-a-local-stub"


class Portal:
    """A stand-in portal: answers by route, and records what it was sent."""

    def __init__(self):
        self.read = (200, FIXTURE)
        self.consume = (200, {"intake_id": ID, "consumed_at": "2026-10-01T00:00:00.000Z"})
        self.redirect_to: str | None = None
        self.raw: bytes | None = None
        self.requests: list[tuple[str, str, str | None]] = []
        portal = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self, method: str):
                portal.requests.append((method, self.path, self.headers.get("authorization")))
                if portal.redirect_to:
                    self.send_response(302)
                    self.send_header("location", portal.redirect_to + self.path)
                    self.end_headers()
                    return
                status, body = portal.consume if self.path.endswith("/consume") else portal.read
                data = portal.raw if portal.raw is not None else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._answer("GET")

            def do_POST(self):
                self.rfile.read(int(self.headers.get("content-length") or 0))
                self._answer("POST")

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def portal(monkeypatch):
    stub = Portal()
    monkeypatch.setenv(intake.URL_VAR, stub.url)
    monkeypatch.setenv(intake.TOKEN_VAR, TOKEN)
    yield stub
    stub.close()


def _record(**changes):
    record = copy.deepcopy(FIXTURE)
    for key, value in changes.items():
        if value is ...:
            record.pop(key)
        else:
            record[key] = value
    return record


# ── the client ───────────────────────────────────────────────────────────────

def test_the_record_is_fetched_with_the_token_and_returned_validated(portal):
    pulled = intake.fetch(ID)
    assert pulled.record["tenant_id"] == FIXTURE["tenant_id"]
    assert pulled.record["rfc"] == FIXTURE["rfc"]
    assert portal.requests == [("GET", f"/api/dev/scaffold/{ID}", f"Bearer {TOKEN}")]


@pytest.mark.parametrize("bad", ["../admin", "42/consume", "42?x=1", "", "4" * 20, "-1"])
def test_an_intake_id_that_is_not_digits_never_reaches_a_url(portal, bad):
    with pytest.raises(intake.IntakeError) as caught:
        intake.fetch(bad)
    assert caught.value.exit_code == intake.CHANGE_SOMETHING
    assert portal.requests == [], "a malformed id was sent as a path"


def test_an_unset_address_or_token_is_not_configured_and_says_which(portal, monkeypatch):
    monkeypatch.delenv(intake.URL_VAR)
    with pytest.raises(intake.IntakeError, match=intake.URL_VAR):
        intake.fetch(ID)
    monkeypatch.setenv(intake.URL_VAR, portal.url)
    monkeypatch.delenv(intake.TOKEN_VAR)
    # pytest's stdin is not a terminal, so there is no one to ask.
    with pytest.raises(intake.IntakeError, match=intake.TOKEN_VAR):
        intake.fetch(ID)
    assert portal.requests == []


def test_plain_http_to_another_host_is_refused_before_the_token_is_sent(portal, monkeypatch):
    monkeypatch.setenv(intake.URL_VAR, "http://portal.example.invalid")
    with pytest.raises(intake.IntakeError, match="https"):
        intake.fetch(ID)


def test_the_token_is_never_in_the_intakes_repr(portal):
    """A traceback or a debug print shows an object's repr."""
    pulled = intake.fetch(ID)
    assert TOKEN not in repr(pulled) and TOKEN not in str(pulled)


def test_a_redirect_is_refused_and_the_token_does_not_follow_it(portal):
    elsewhere = Portal()
    try:
        portal.redirect_to = elsewhere.url
        with pytest.raises(intake.IntakeError, match="redirected"):
            intake.fetch(ID)
        assert elsewhere.requests == [], "the token followed the redirect"
    finally:
        elsewhere.close()


@pytest.mark.parametrize(
    "status, reason, exit_code",
    [
        (401, "unknown intake token", intake.CHANGE_SOMETHING),
        (404, "no intake 42 for this token", intake.CHANGE_SOMETHING),
        (410, "intake 42 expired at …", intake.CHANGE_SOMETHING),
        (503, "the portal could not read the database", intake.RETRY),
    ],
)
def test_the_portals_refusal_reaches_the_author_with_the_right_exit_code(portal, status, reason, exit_code):
    portal.read = (status, {"error": reason})
    with pytest.raises(intake.IntakeError) as caught:
        intake.fetch(ID)
    assert reason in str(caught.value)
    assert caught.value.exit_code == exit_code


def test_an_unreachable_portal_is_a_retry(monkeypatch):
    stub = Portal()
    url = stub.url
    stub.close()
    monkeypatch.setenv(intake.URL_VAR, url)
    monkeypatch.setenv(intake.TOKEN_VAR, TOKEN)
    with pytest.raises(intake.IntakeError) as caught:
        intake.fetch(ID)
    assert caught.value.exit_code == intake.RETRY


def test_an_answer_that_is_too_large_or_not_json_is_refused(portal):
    portal.raw = b" " * (intake.MAX_BYTES + 1)
    with pytest.raises(intake.IntakeError, match="larger"):
        intake.fetch(ID)
    portal.raw = b"<html>login</html>"
    with pytest.raises(intake.IntakeError, match="not JSON"):
        intake.fetch(ID)


# ── the receiving side ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "changes, field",
    [
        ({"schema_version": 2}, "version"),
        ({"surprise": True}, "surprise"),
        ({"stack": ...}, "stack"),
        ({"intake_id": "43"}, "43"),
        # Valid for the CLI's own rule, refused because the portal could not register it.
        ({"tenant_id": "Acme_Orders"}, "register"),
        ({"tenant_id": "acme orders"}, "tenant id"),
        ({"stack": "rust"}, "stack"),
        ({"isolation": "private"}, "isolation"),
        ({"architecture": "Hexagonal; rm -rf /"}, "architecture"),
        ({"agentic": "yes"}, "agentic"),
        ({"ides": ["cursor", "cursor"]}, "ides"),
        ({"rfc": {"objective": "x", "acceptance_criteria": ["y"]}}, "rfc"),
        ({"rfc": {"objective": "x" * 4001, "acceptance_criteria": ["y"], "files_to_modify": []}}, "rfc.objective"),
        ({"rfc": {"objective": "x", "acceptance_criteria": [], "files_to_modify": []}}, "rfc.acceptance_criteria"),
    ],
)
def test_every_field_is_checked_again_here_whatever_the_portal_accepted(changes, field):
    with pytest.raises(intake.IntakeError, match=re.escape(field)):
        intake.validate_record(_record(**changes), ID)


def test_control_characters_go_and_a_list_item_stays_on_one_line():
    record = _record(rfc={
        "objective": "Take orders.\x07\x1b[31m\nThen confirm them.",
        "acceptance_criteria": ["Stored\n## A heading the author did not mean"],
        "files_to_modify": [],
    })
    rfc = intake.validate_record(record, ID)["rfc"]
    assert rfc["objective"] == "Take orders.[31m\nThen confirm them."
    assert rfc["acceptance_criteria"] == ["Stored ## A heading the author did not mean"]


# ── pinned to the contract and to its sibling ────────────────────────────────

def test_the_mirrored_rules_are_the_contracts():
    props = SCHEMA["properties"]
    assert intake.SCHEMA_VERSION == props["schema_version"]["const"]
    assert intake.APP_ID.pattern == props["tenant_id"]["pattern"]
    assert intake.INTAKE_ID.pattern == props["intake_id"]["pattern"]
    assert intake.ARCHITECTURE.pattern == props["architecture"]["anyOf"][1]["pattern"]
    assert intake.FIELDS == set(props) == set(SCHEMA["required"])
    rfc = props["rfc"]["properties"]
    assert intake.RFC_FIELDS == set(rfc)
    assert intake.LIMITS == {
        "objective": rfc["objective"]["maxLength"],
        "criteria": rfc["acceptance_criteria"]["maxItems"],
        "files": rfc["files_to_modify"]["maxItems"],
        "item": rfc["acceptance_criteria"]["items"]["maxLength"],
    }
    assert rfc["files_to_modify"]["items"]["maxLength"] == intake.LIMITS["item"]
    assert set(props["stack"]["enum"]) == set(cli.STACKS)
    assert set(props["isolation"]["enum"]) == set(cli.ISOLATIONS)


def test_each_variable_is_read_by_the_name_its_messages_give():
    """The reads are literal so the env-var documentation sweep can see them; the
    constants are what every message names. This keeps the two the same."""
    source = (REPO / "runtime" / "intake.py").read_text(encoding="utf-8")
    for name in (intake.URL_VAR, intake.TOKEN_VAR):
        assert f'os.environ.get("{name}"' in source, name


@pytest.mark.parametrize("url", [
    "https://portal.example.com", "http://localhost:3000", "http://127.0.0.1:3000",
    "http://portal.example.com", "http://10.0.0.5", "ftp://localhost", "localhost:3000",
    "http://localhost.example.com", "http://127.0.0.1@example.com",
])
def test_the_portal_address_rule_is_send_dev_records(url, monkeypatch, capsys, tmp_path):
    """Both send a token to AGENTSMITH_PORTAL_URL and ship to different places
    (scripts/ to CI, runtime/ vendored into tenants), so the rule exists twice.
    Pinned by behaviour: send_dev_record refuses an unsafe address with exit 1
    before it reads its record, and gets as far as the missing record (exit 0)
    for a safe one — no network either way."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("send_dev_record", REPO / "scripts" / "send_dev_record.py")
    sender = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sender)
    monkeypatch.setenv("AGENTSMITH_PORTAL_URL", url)
    monkeypatch.setenv("AGENTSMITH_PORTAL_INGEST_TOKEN", "x")
    sender_refuses = sender.main(["send_dev_record.py", str(tmp_path / "absent.json")]) == 1
    assert sender_refuses == (not intake.safe_portal_url(url)), url


# ── tenant init --from ───────────────────────────────────────────────────────

def _init(root: Path, *extra: str) -> int:
    return cli.main(["tenant", "init", "--from", ID, "--root", str(root), *extra])


def test_init_from_an_intake_scaffolds_it_and_then_consumes_it(portal, tmp_path, capsys):
    assert _init(tmp_path) == 0
    rfc = (tmp_path / ".agent-rfc" / "001-scaffold.md").read_text(encoding="utf-8")
    assert FIXTURE["rfc"]["objective"] in rfc
    assert all(f"- [ ] {c}" in rfc for c in FIXTURE["rfc"]["acceptance_criteria"])
    assert "TEMPLATE" not in rfc
    assert 'ides: ["cursor"]' in (tmp_path / ".agenticframework" / "tenant.yaml").read_text(encoding="utf-8")
    assert (tmp_path / ".cursor" / "hooks.json").is_file() and not (tmp_path / ".claude" / "settings.json").exists()
    assert [r[0] for r in portal.requests] == ["GET", "POST"], "consume was not called exactly once, after the read"
    assert "marked used" in capsys.readouterr().out


@pytest.mark.parametrize("extra", [("acme",), ("--stack", "go"), ("--isolation", "shared"), ("--agentic",),
                                   ("--ide", "cursor"), ("--architecture", "layered")])
def test_from_refuses_what_the_intake_decides_rather_than_letting_one_win(portal, tmp_path, extra, capsys):
    argv = ["tenant", "init", *extra, "--from", ID, "--root", str(tmp_path)]
    assert cli.main(argv) == 2
    assert portal.requests == []
    assert extra[0] in capsys.readouterr().err


def test_a_tenant_id_or_an_intake_is_required(tmp_path, capsys):
    assert cli.main(["tenant", "init", "--root", str(tmp_path)]) == 2
    assert "--from" in capsys.readouterr().err


def test_a_refused_intake_writes_nothing(portal, tmp_path):
    portal.read = (410, {"error": "intake 42 expired", "reason": "expired"})
    assert _init(tmp_path) == intake.CHANGE_SOMETHING
    assert list(tmp_path.iterdir()) == []


def test_an_intake_whose_rfc_could_not_land_is_left_unused(portal, tmp_path, capsys):
    """The scaffold never writes an RFC beside another, so the author's text was
    not written. Consuming would burn the only copy of it."""
    (tmp_path / ".agent-rfc").mkdir()
    (tmp_path / ".agent-rfc" / "000-existing.md").write_text("# an RFC already here\n", encoding="utf-8")
    assert _init(tmp_path) == 0
    out = capsys.readouterr().out
    assert "000-existing.md" in out and "left unused" in out
    assert [r[0] for r in portal.requests] == ["GET"], "consumed an intake whose RFC did not land"


def test_a_failed_consume_leaves_the_scaffold_and_says_so(portal, tmp_path, capsys):
    portal.consume = (503, {"error": "database unavailable"})
    assert _init(tmp_path) == 0
    assert (tmp_path / ".agent-rfc" / "001-scaffold.md").is_file()
    out = capsys.readouterr().out
    assert "not marked used" in out
    assert re.search(r"^  ⚠️", out, re.M), "a column-0 warning fails a tenant build (.github/scratch-tenants/build.sh)"


def test_running_it_again_after_a_failed_consume_consumes(portal, tmp_path):
    portal.consume = (503, {"error": "database unavailable"})
    assert _init(tmp_path) == 0
    portal.consume = (200, {"intake_id": ID})
    portal.requests.clear()
    assert _init(tmp_path) == 0
    assert [r[0] for r in portal.requests] == ["GET", "POST"]
