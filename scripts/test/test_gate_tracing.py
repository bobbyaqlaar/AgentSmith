"""
scripts/test/test_gate_tracing.py — every gate decision is a span (pillar 3),
without a down collector ever slowing an edit or losing a span
(.agent-rfc/designs/governance-enforcement.md, G1).

Spans are asserted from what the exporter writes and what the collector
receives — the artifact — not from the helper's arguments.
"""

from __future__ import annotations

import http.server
import sys
import threading
import time
from pathlib import Path
from typing import ClassVar

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import gate_tracing as gt

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest


def _spans_in(data: bytes) -> list:
    request = ExportTraceServiceRequest()
    request.ParseFromString(data)
    return [s for rs in request.resource_spans for ss in rs.scope_spans for s in ss.spans]


def _attrs(span) -> dict:
    return {a.key: (a.value.string_value or a.value.int_value or a.value.bool_value) for a in span.attributes}


@pytest.fixture()
def spool(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTSMITH_STATE_DIR", str(tmp_path / "state"))
    for var in ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "AGENT_PHOENIX_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    gt.reset_for_tests()
    yield gt.spool_dir()
    gt.reset_for_tests()


def test_a_decision_is_spooled_as_an_otlp_batch_with_identity(spool, tmp_path):
    with gt.gate_span("pre_edit", root=tmp_path, ide="claude", rule="design-before-code",
                      decision="deny", files=1):
        pass
    gt.flush()

    batches = sorted(spool.glob("*.pb"))
    assert len(batches) == 1
    [span] = _spans_in(batches[0].read_bytes())
    attrs = _attrs(span)
    assert span.name == "agent.gate.pre_edit"
    assert attrs["agent.decision"] == "deny"
    assert attrs["agent.rule"] == "design-before-code"
    assert attrs["agent.ide"] == "claude"
    assert attrs["agent.role"] == "process-gate"


def test_the_gate_still_answers_when_tracing_cannot_start(spool, tmp_path, monkeypatch):
    monkeypatch.setattr(gt, "_provider", lambda: (_ for _ in ()).throw(RuntimeError("no sdk")))
    ran = []
    with gt.gate_span("stop", root=tmp_path, ide="claude") as span:
        ran.append(True)
        span.set_attribute("agent.decision", "allow")
    assert ran == [True]
    assert "no sdk" in gt.status_line()


def test_without_an_endpoint_the_spool_is_kept_and_said_so(spool, tmp_path):
    with gt.gate_span("stop", root=tmp_path, ide="claude"):
        pass
    gt.flush()

    result = gt.ship()

    assert result.endpoint is None and result.sent == 0 and result.kept == 1
    assert "NOT exported (no OTLP endpoint)" in gt.status_line(result)
    assert len(list(spool.glob("*.pb"))) == 1


class _Collector(http.server.BaseHTTPRequestHandler):
    received: ClassVar[list] = []
    status: ClassVar[int] = 200

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).received.append((self.path, self.headers["Content-Type"], body))
        self.send_response(type(self).status)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture()
def collector():
    _Collector.received = []
    _Collector.status = 200
    server = http.server.HTTPServer(("127.0.0.1", 0), _Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def test_shipping_posts_the_spooled_bytes_and_deletes_only_what_was_accepted(spool, tmp_path, collector, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", f"http://127.0.0.1:{collector.server_port}/v1/traces")
    with gt.gate_span("session_start", root=tmp_path, ide="cursor"):
        pass
    gt.flush()
    [batch] = spool.glob("*.pb")
    spooled = batch.read_bytes()

    _Collector.status = 503
    refused = gt.ship()
    assert refused.sent == 0 and refused.kept == 1 and batch.exists()

    _Collector.status = 200
    accepted = gt.ship()
    assert accepted.sent == 1 and not batch.exists()
    path, content_type, body = _Collector.received[-1]
    assert path == "/v1/traces" and content_type == "application/x-protobuf" and body == spooled


def test_a_dead_collector_costs_at_most_the_timeout(spool, tmp_path, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://10.255.255.1:9/v1/traces")  # unroutable
    with gt.gate_span("stop", root=tmp_path, ide="claude"):
        pass
    gt.flush()
    start = time.monotonic()
    result = gt.ship(timeout=0.3)
    assert time.monotonic() - start < 2.0
    assert result.kept == 1 and result.errors


def test_the_spool_is_capped_and_drops_are_counted_not_silent(spool, tmp_path, monkeypatch):
    monkeypatch.setattr(gt, "MAX_BATCHES", 3)
    for _ in range(5):
        with gt.gate_span("pre_edit", root=tmp_path, ide="claude"):
            pass
        gt.flush()
    assert len(list(spool.glob("*.pb"))) == 3
    assert gt.dropped_count() == 2
    assert "2 dropped" in gt.status_line(gt.ship())


def test_a_spool_that_cannot_be_written_is_reported_not_raised(spool, tmp_path, monkeypatch):
    """A hook must not die, or claim success, because the state directory is
    read-only — the decision it made still stands."""
    monkeypatch.setattr(gt, "spool_dir", lambda: tmp_path / "nope" / "gate-spans")
    (tmp_path / "nope").write_text("not a directory", encoding="utf-8")
    with gt.gate_span("pre_edit", root=tmp_path, ide="claude") as span:
        span.set_attribute("agent.decision", "deny")
    gt.flush()
    assert "spool write failed" in gt.status_line()

