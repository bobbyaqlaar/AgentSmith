"""One rule for outbound addresses: https anywhere, plain http only to this
machine (compliance.is_web_url). Pinned at the three places that send data:
the OTLP exporter, the intake client, and scripts/send_dev_record.py (which
keeps an inline copy because it is stdlib-only).

Each refusal test fails on the code before this rule: the exporter used to
build a plain-http exporter for a remote host."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from agentsmith import compliance, intake, otlp

REPO = Path(__file__).resolve().parents[2]

URLS = [
    "https://collector.example.com:4318",
    "https://10.0.0.5:4318",
    "http://localhost:6006",
    "http://127.0.0.1:6006",
    "http://[::1]:6006",
    "http://collector.example.com:4318",
    "http://10.0.0.5:4318",
    "ftp://collector.example.com",
    "file:///etc/passwd",
    "",
]


@pytest.mark.parametrize(
    "endpoint",
    ["http://collector.example.com:4318", "http://10.0.0.5:4318"],
)
def test_security_otlp_refuses_plain_http_to_another_host(endpoint):
    env = {"OTEL_EXPORTER_OTLP_ENDPOINT": endpoint}
    assert otlp.span_exporter(env) is None
    assert otlp.metric_exporter(env) is None


def test_otlp_still_exports_to_this_machine_over_http():
    env = {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:6006"}
    assert otlp.span_exporter(env) is not None


def test_otlp_still_exports_over_https():
    env = {"OTEL_EXPORTER_OTLP_ENDPOINT": "https://collector.example.com:4318"}
    assert otlp.span_exporter(env) is not None


@pytest.mark.parametrize("url", URLS)
def test_intake_uses_the_one_rule(url):
    assert intake.safe_portal_url(url) == compliance.is_web_url(url), url


@pytest.mark.parametrize("url", [u for u in URLS if u])  # "" means not configured: exit 0, not a refusal
def test_send_dev_record_inline_copy_matches_the_one_rule(url, monkeypatch, tmp_path):
    """send_dev_record refuses an unsafe address with exit 1 before it reads
    its record, and gets as far as the missing record (exit 0) for a safe one.
    No network either way."""
    spec = importlib.util.spec_from_file_location("send_dev_record", REPO / "scripts" / "send_dev_record.py")
    sender = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sender)
    monkeypatch.setenv("AGENTSMITH_PORTAL_URL", url)
    monkeypatch.setenv("AGENTSMITH_PORTAL_INGEST_TOKEN", "x")
    refused = sender.main(["send_dev_record.py", str(tmp_path / "absent.json")]) == 1
    assert refused == (not compliance.is_web_url(url)), url
