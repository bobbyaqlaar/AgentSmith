"""
scripts/test/test_record_contract.py — the record a gate provider sends a portal,
as a contract (contract/record/v1/, .agent-rfc/designs/record-contract.md).

One model, one generated schema, both sides held to it: the gate validates
before it sends; the conformance runs judge a sender and a receiver — and can
fail them, which is the point of having them.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

V1 = REPO / "contract" / "record" / "v1"
PROVIDER = f"{sys.executable} -m runtime.cli gate"


def test_the_record_schema_is_the_model():
    import gate_models as gm

    published = json.loads((V1 / "record.schema.json").read_text(encoding="utf-8"))
    generated = gm.DevRecord.model_json_schema(by_alias=True)
    for key in ("description", "$schema", "$id"):
        published.pop(key, None)
        generated.pop(key, None)
    assert published == generated


def test_the_model_decides_every_parseable_case_as_the_contract_does():
    """The provider's side of the same cases the portal runs."""
    import gate_models as gm
    from runtime import conformance as rc

    for case in rc.record_cases():
        if case.token != "valid" or case.expect == 413:
            continue  # token and size are the transport's, not the shape's
        try:
            gm.DevRecord.model_validate_json(rc.record_body(case))
            accepted = True
        except ValueError:
            accepted = False
        assert accepted == (case.expect == 200), case.name


def test_the_gate_and_the_contract_agree_on_the_record():
    """Replaces a regex pin of one hand-written constant against another."""
    import gate_models as gm
    import process_gate as pg
    import send_dev_record

    schema = json.loads((V1 / "record.schema.json").read_text(encoding="utf-8"))
    assert pg.DEV_RECORD_SCHEMA == schema["properties"]["schema"]["const"]
    assert pg.DEV_VERDICTS == tuple(schema["$defs"]["RecordCommit"]["properties"]["verdict"]["enum"])
    # The sender is standard-library only, so it cannot import the model; its
    # chunk size is pinned to the contract's limit instead.
    assert send_dev_record.CHUNK == gm.RECORD_LIMITS["commits"] == schema["properties"]["commits"]["maxItems"]


def test_a_record_the_contract_would_refuse_never_leaves_the_gate():
    import process_gate as pg

    good = json.loads((V1 / "fixture.json").read_text())["record"]
    assert pg.record_problem(good) is None
    bad = {**good, "commits": [{**good["commits"][0], "verdict": "probably_fine"}]}
    assert "verdict" in (pg.record_problem(bad) or "")


class _Stub:
    """A receiver: `strict` validates as the contract says; otherwise it stores anything."""

    def __init__(self, strict: bool):
        import gate_models as gm

        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("content-length", 0)))
                status = 200
                if strict:
                    if self.headers.get("authorization") != "Bearer good-token":
                        status = 401
                    elif len(body) > gm.RECORD_LIMITS["body_bytes"]:
                        status = 413
                    else:
                        try:
                            gm.DevRecord.model_validate_json(body)
                        except ValueError:
                            status = 400
                self.send_response(status)
                self.send_header("content-length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/dev/ingest"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        stub.strict = strict


@pytest.mark.parametrize("strict", [True, False])
def test_the_receiver_suite_passes_a_conformant_receiver_and_fails_one_that_stores_anything(strict):
    from runtime import conformance as rc

    stub = _Stub(strict)
    try:
        report = rc.run_record_receiver(stub.url, "good-token")
    finally:
        stub.server.shutdown()

    assert report.passed is strict, report.render()


def test_agentsmith_passes_the_sender_suite(tmp_path, monkeypatch):
    from runtime import conformance as rc

    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("PYTHONPATH", str(REPO))

    report = rc.run_record_sender(PROVIDER, tmp_path / "work")

    assert report.passed, report.render()


def test_the_sender_suite_fails_a_sender_that_sends_nothing_and_always_allows(tmp_path):
    """Exactly the checks such a sender breaks fail — each check can fail on its
    own, so a check that always passed would change this set."""
    from runtime import conformance as rc

    lazy = tmp_path / "lazy-provider"
    lazy.write_text('#!/usr/bin/env bash\ncat >/dev/null\necho \'{"decision": "allow", "text": ""}\'\n')
    lazy.chmod(0o755)

    report = rc.run_record_sender(str(lazy), tmp_path / "work")

    failed = {check.name for check in report.checks if not check.ok}
    assert failed == {"a stored record is sent, and satisfies the schema", "it carries the token as a bearer",
                      "a redirect is not followed, and fails the answer", "a refused token fails the answer"}


def test_a_range_named_by_ref_records_commit_hashes(tmp_path):
    """A new branch (an all-zeros base) is judged by its head alone, and the head
    was recorded as the caller spelled it: `after`, not a hash — a record no
    receiver can store. Found by validating the record; the gate now resolves it."""
    import subprocess

    import gate_models as gm
    from runtime.conformance import build_fixture

    root = build_fixture(tmp_path / "repo", 2)
    out = tmp_path / "record.json"
    done = subprocess.run([sys.executable, str(REPO / "scripts" / "process_gate.py"), "ci", "--base", "0" * 40,
                           "--head", "after", "--json", str(out)], cwd=root, capture_output=True, text=True,
                          check=False)

    assert out.is_file(), done.stdout + done.stderr
    record = gm.DevRecord.model_validate_json(out.read_text())
    assert [c.commit for c in record.commits] == [record.head]
