"""One rule for outbound addresses: https anywhere, plain http only to this
machine, and always a host (compliance.is_web_url). Pinned at the three places
that send data: the OTLP exporter, the intake client, and
scripts/send_dev_record.py, which uses scripts/_shared.py's stdlib copy
(scripts/ runs without the runtime package), pinned here to the same cases.

Each refusal test fails on the code before this rule: the exporter used to
build a plain-http exporter for a remote host, and a malformed address raised
out of tracer set-up instead of being refused."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

import pytest

from agentsmith import compliance, intake, otlp

REPO = Path(__file__).resolve().parents[2]

# Not https, or http to this machine with a host: refused.
REFUSED = [
    "http://collector.example.com:4318",
    "http://10.0.0.5:4318",
    "ftp://collector.example.com",
    "file:///etc/passwd",
    "https://",  # no host
    "https:evil.com",  # no host: "evil.com" is the path
    "http://",
    "http://[::1:6006",  # malformed IPv6: urlparse raises
    "https://[::1:6006",
    "ftp://localhost",
    "localhost:3000",  # no scheme
    "http://localhost.example.com",  # a name that merely starts with localhost
    "http://127.0.0.1@example.com",  # userinfo: the host is example.com
    "http://portal.example.com",
    # Pass 10, item U: a port urllib cannot use passed the rule, then failed as a "password" problem.
    "http://127.0.0.1:6006x",
    "http://127.0.0.1:99999",
    "https://collector.example:-1",
]
ALLOWED = [
    "https://collector.example.com:4318",
    "https://10.0.0.5:4318",
    "http://localhost:6006",
    "http://127.0.0.1:6006",
    "http://[::1]:6006",
]
URLS = [*ALLOWED, *REFUSED, ""]


@pytest.mark.parametrize("url", REFUSED)
def test_security_is_web_url_refuses(url):
    assert compliance.is_web_url(url) is False


@pytest.mark.parametrize("url", ALLOWED)
def test_is_web_url_allows(url):
    assert compliance.is_web_url(url) is True


# Refusal tests assert the guard's own ERROR line, which is logged before the
# exporter package is imported. So they are not vacuous when the package is
# absent: without the guard, that case logs the "not installed" WARNING instead.
@pytest.mark.parametrize(
    "endpoint",
    ["http://collector.example.com:4318", "http://10.0.0.5:4318", "https://", "http://[::1:6006"],
)
@pytest.mark.parametrize("build", [otlp.span_exporter, otlp.metric_exporter])
def test_security_otlp_refuses_and_says_so(endpoint, build, caplog):
    env = {"OTEL_EXPORTER_OTLP_ENDPOINT": endpoint}
    with caplog.at_level(logging.ERROR, logger="agentsmith.otlp"):
        assert build(env) is None
    # The guard's own ERROR line; with the guard gone, the package-missing case logs a WARNING instead.
    refusals = [r for r in caplog.records if r.levelno == logging.ERROR and "will not be exported" in r.getMessage()]
    assert refusals, f"{endpoint}: refused without the ERROR line"


# The positive tests need the exporter package; skip by name, never pass empty.
_EXPORTER_PKG = "opentelemetry.exporter.otlp.proto.http"


@pytest.mark.parametrize("endpoint", ["http://localhost:6006", "https://collector.example.com:4318"])
@pytest.mark.parametrize("build", [otlp.span_exporter, otlp.metric_exporter])
def test_otlp_still_exports_to_this_machine_and_over_https(endpoint, build):
    pytest.importorskip(_EXPORTER_PKG, reason="opentelemetry-exporter-otlp-proto-http not installed")
    assert build({"OTEL_EXPORTER_OTLP_ENDPOINT": endpoint}) is not None


@pytest.mark.parametrize("url", URLS)
def test_intake_uses_the_one_rule(url):
    assert intake.safe_portal_url(url) == compliance.is_web_url(url), url


@pytest.mark.parametrize("url", [u for u in URLS if u])  # "" means not configured: exit 0, not a refusal
def test_send_dev_record_matches_the_one_rule(url, monkeypatch, tmp_path):
    """send_dev_record refuses an unsafe address with exit 1 before it reads
    its record, and gets as far as the missing record (exit 0) for a safe one.
    No network either way. A malformed address is a refusal, not an exception."""
    monkeypatch.syspath_prepend(str(REPO / "scripts"))  # its `from _shared import is_web_url`
    spec = importlib.util.spec_from_file_location("send_dev_record", REPO / "scripts" / "send_dev_record.py")
    sender = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sender)
    monkeypatch.setenv("AGENTSMITH_PORTAL_URL", url)
    monkeypatch.setenv("AGENTSMITH_PORTAL_INGEST_TOKEN", "x")
    refused = sender.main(["send_dev_record.py", str(tmp_path / "absent.json")]) == 1
    assert refused == (not compliance.is_web_url(url)), url


def test_the_tls_front_proxies_the_auth_sidecar_not_phoenix():
    """docs/team-observability.md's TLS front (Caddy and Nginx) must reach
    Phoenix through the basic-auth sidecar (PHOENIX_AUTH_PORT, default 6007),
    never Phoenix's own 6006, which has no auth (Pass 7, item D)."""
    import re

    text = (REPO / "docs" / "team-observability.md").read_text(encoding="utf-8")
    blocks = re.findall(r"^```[^\n]*\n(.*?)^```", text, flags=re.M | re.S)
    proxy = re.compile(r"^\s*(?:reverse_proxy|proxy_pass)\s+([^\s;]+)", flags=re.M)
    targets = [m.group(1) for b in blocks for m in proxy.finditer(b)]
    assert targets, "no reverse_proxy / proxy_pass found in the doc's code blocks"
    assert all(t.rsplit(":", 1)[-1].rstrip("/") == "6007" for t in targets), targets


def _scripts_shared(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO / "scripts"))
    import _shared

    return _shared


@pytest.mark.parametrize("url", URLS)
def test_scripts_shared_rule_matches_the_one_rule(url, monkeypatch):
    """scripts/ runs without the runtime package, so scripts/_shared.py keeps a
    stdlib copy of the rule (the agentsmith/ <-> scripts/ boundary is real).
    Pinned by behaviour across every case."""
    assert _scripts_shared(monkeypatch).is_web_url(url) == compliance.is_web_url(url), url


def test_shared_imports_only_stdlib():
    """send_dev_record and the sovereign probe import scripts/_shared.py in any
    CI job, so importing it must load no third-party or runtime package."""
    import subprocess
    import sys

    probe = ("import sys; sys.path.insert(0, sys.argv[1]); import _shared; "
             "print(sorted(m for m in ('yaml', 'httpx', 'pydantic', 'agentsmith') if m in sys.modules))")
    done = subprocess.run([sys.executable, "-I", "-c", probe, str(REPO / "scripts")],
                          capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "[]", done.stdout


# ── An operator URL is never printed with its userinfo (Pass 8, item I) ──────
# The docs put the auth sidecar's password in AGENT_PHOENIX_ENDPOINT
# (https://ops:<password>@host), and refusal and status messages printed the
# URL whole: into the exporter's ERROR line, and through gate_tracing's status
# line into the coding agent's session context.

PW = "PLACEHOLDER-PW"
DISPLAYED = [
    ("http://ops:" + PW + "@10.0.0.5:6007/v1/traces", "http://10.0.0.5:6007/v1/traces"),
    ("https://ops:" + PW + "@phoenix.example/v1/traces?token=" + PW + "#" + PW, "https://phoenix.example/v1/traces"),
    ("https://" + PW + "@[::1]:6006", "https://[::1]:6006"),
    ("https://collector.example:4318", "https://collector.example:4318"),
    ("http://ops:" + PW + "@[::1:6006", "<an address that does not parse>"),
    ("http://127.0.0.1:6006x/v1/traces?t=1", "http://127.0.0.1:6006x/v1/traces"),  # no @: shown, so the typo is seen
    ("", ""),
    # Pass 9, item R: a password holding `/`, `?` or `#` ends urlparse's netloc
    # early, so its tail read as the path, query or fragment.
    ("https://ops:123/" + PW + "@phoenix.example", "<an address whose credential cannot be separated>"),
    ("https://ops:a@b/" + PW + "@phoenix.example", "<an address whose credential cannot be separated>"),
    ("https://ops:12#" + PW + "@phoenix.example", "<an address whose credential cannot be separated>"),
    ("https://ops:12?" + PW + "@phoenix.example", "<an address whose credential cannot be separated>"),
    ("https://ops:" + PW + "@", "<an address whose credential cannot be separated>"),
    # Pass 9, item S: a hostless address with no credential in it is shown as written.
    ("phoenix:6006", "phoenix:6006"),
    ("https://", "https://"),
    ("file:///etc/passwd?x=1", "file:///etc/passwd"),
]


@pytest.mark.parametrize("url, shown", DISPLAYED)
def test_display_url_drops_userinfo_query_and_fragment(url, shown):
    assert compliance.display_url(url) == shown


@pytest.mark.parametrize("url", [u for u, _ in DISPLAYED] + URLS)
def test_scripts_shared_display_matches_the_runtime_one(url, monkeypatch):
    assert _scripts_shared(monkeypatch).display_url(url) == compliance.display_url(url), url


def test_a_phoenix_api_error_does_not_carry_the_password(monkeypatch):
    """httpx's HTTPStatusError text is the whole URL, userinfo included, and the docs put
    the auth sidecar's password in the Phoenix address. The scripts' one Phoenix request
    path wrapped that text into its own error, which the sync scripts print (independent
    review of the ruff-s rebuild, finding 4's sibling)."""
    import httpx

    shared = _scripts_shared(monkeypatch)
    real = httpx.Client

    def refusing(method, url, **kwargs):
        with real(transport=httpx.MockTransport(lambda request: httpx.Response(401, request=request))) as client:
            return client.request(method.upper(), url, **kwargs)

    monkeypatch.setattr(httpx, "get", lambda url, **kw: refusing("get", url, **kw))
    with pytest.raises(RuntimeError) as raised:
        shared._phoenix_request(f"https://ops:{PW}@phoenix.example.invalid:6007", "/v1/projects")
    said = str(raised.value)
    assert PW not in said and raised.value.__cause__ is None and raised.value.__suppress_context__, said
    assert "HTTP 401" in said and "https://phoenix.example.invalid:6007/v1/projects" in said, said


@pytest.mark.parametrize("build", [otlp.span_exporter, otlp.metric_exporter])
def test_the_exporter_refusal_does_not_log_the_password(build, caplog):
    env = {"AGENT_PHOENIX_ENDPOINT": f"http://ops:{PW}@10.0.0.5:6007"}
    with caplog.at_level(logging.DEBUG, logger="agentsmith.otlp"):
        assert build(env) is None
    assert any("must be https" in r.getMessage() for r in caplog.records)
    assert PW not in caplog.text


def test_the_exporter_boundary_refusal_does_not_log_the_password(monkeypatch, caplog):
    monkeypatch.setattr(compliance, "outbound_allowed", lambda _url: False)
    env = {"AGENT_PHOENIX_ENDPOINT": f"https://ops:{PW}@phoenix.example"}
    with caplog.at_level(logging.DEBUG, logger="agentsmith.otlp"):
        assert otlp.span_exporter(env) is None
    assert any("outside the declared boundary" in r.getMessage() for r in caplog.records)
    assert PW not in caplog.text


def _gate_tracing(tmp_path, monkeypatch, endpoint):
    monkeypatch.syspath_prepend(str(REPO / "scripts"))
    import gate_tracing as gt

    for var in ("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "OTEL_EXPORTER_OTLP_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AGENTSMITH_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AGENT_PHOENIX_ENDPOINT", endpoint)
    gt.spool_dir().mkdir(parents=True)
    (gt.spool_dir() / "batch.pb").write_bytes(b"\x00")
    return gt


def test_the_span_shipping_refusal_does_not_print_the_password(tmp_path, monkeypatch):
    gt = _gate_tracing(tmp_path, monkeypatch, f"http://ops:{PW}@10.0.0.5:6007")
    line = gt.status_line(gt.ship())
    assert "must be https" in line and "10.0.0.5:6007" in line
    assert PW not in line


def test_a_user_and_password_in_the_collector_address_is_reported_not_raised(tmp_path, monkeypatch):
    """Pass 9, item O: real urllib, no stub. urllib cannot send userinfo and
    raises http.client.InvalidURL with the password in it, before any DNS lookup,
    and that escaped ship() and with it session start."""
    gt = _gate_tracing(tmp_path, monkeypatch, f"https://ops:{PW}@phoenix.example.invalid")
    result = gt.ship()
    line = gt.status_line(result)
    assert result.kept == 1 and result.sent == 0
    assert "OTEL_EXPORTER_OTLP_HEADERS" in line and "phoenix.example.invalid" in line
    assert PW not in line


def test_the_machine_package_stays_import_light():
    """agentsmith/machine/__init__.py: nothing there imports a third-party
    package at module scope (Pass 9, item Q: ops imported compliance, so pydantic)."""
    import subprocess
    import sys

    probe = ("import sys; sys.path.insert(0, sys.argv[1]); "
             "import agentsmith.machine.ops, agentsmith.machine.policy, agentsmith.machine.state; "
             "print(sorted(m for m in ('pydantic', 'yaml', 'httpx') if m in sys.modules))")
    done = subprocess.run([sys.executable, "-I", "-c", probe, str(REPO)], capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "[]", done.stdout


def test_a_collector_that_cannot_be_reached_does_not_print_the_password(tmp_path, monkeypatch):
    import urllib.request

    gt = _gate_tracing(tmp_path, monkeypatch, f"https://ops:{PW}@phoenix.example")

    def refuse(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    line = gt.status_line(gt.ship())
    assert "connection refused" in line and "phoenix.example" in line
    assert PW not in line


def test_machine_status_does_not_print_the_password(monkeypatch, tmp_path):
    from agentsmith.machine import ops

    monkeypatch.setattr(ops, "_online", lambda: False)
    monkeypatch.setattr(ops, "judge_model", lambda: None)
    lines = []
    ops.status(out=lines.append, env={"AGENT_PHOENIX_ENDPOINT": f"https://ops:{PW}@phoenix.example",
                                      "AGENTSMITH_STATE_DIR": str(tmp_path)})
    text = "\n".join(lines)
    assert "https://phoenix.example" in text
    assert PW not in text


# ── A user:password in an operator address (Pass 9, items O and P) ───────────


def test_intake_reports_a_user_and_password_it_cannot_send(monkeypatch):
    monkeypatch.setenv("AGENTSMITH_PORTAL_URL", f"https://dev:{PW}@portal.example.invalid")
    monkeypatch.setenv("AGENTSMITH_INTAKE_TOKEN", "PLACEHOLDER-TOKEN")
    with pytest.raises(intake.IntakeError) as caught:
        intake.fetch("123")
    assert PW not in str(caught.value) and "portal.example.invalid" in str(caught.value)


def test_the_intake_refusal_does_not_print_the_password(monkeypatch):
    monkeypatch.setenv("AGENTSMITH_PORTAL_URL", f"http://dev:{PW}@portal.lan.example")
    monkeypatch.setenv("AGENTSMITH_INTAKE_TOKEN", "PLACEHOLDER-TOKEN")
    with pytest.raises(intake.IntakeError, match="must be https") as caught:
        intake.fetch("123")
    assert PW not in str(caught.value)


def test_send_dev_record_reports_a_user_and_password_it_cannot_send(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("send_dev_record", REPO / "scripts" / "send_dev_record.py")
    sender = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sender)
    monkeypatch.setenv("AGENTSMITH_PORTAL_URL", f"https://dev:{PW}@portal.example.invalid")
    monkeypatch.setenv("AGENTSMITH_PORTAL_INGEST_TOKEN", "PLACEHOLDER-TOKEN")
    said = []
    code = sender.send({"commits": [{"sha": "0" * 40}]}, lambda level, text: said.append((level, text)))
    assert code == 1, said
    assert said and all(PW not in text for _, text in said)


@pytest.mark.parametrize("run", ["_post_status", "run_record_receiver"])
def test_a_conformance_receiver_with_a_user_and_password_is_named_not_answered_0(run):
    """Pass 10, item T: _post_status returned 0, "nothing answered", so every
    ops case read as a failing receiver; run_record_receiver let InvalidURL out
    with the password in it."""
    from agentsmith import conformance

    url = f"https://u:{PW}@receiver.example.invalid"
    call = (lambda: conformance._post_status(url, {"x": 1}, "PLACEHOLDER-TOKEN")) if run == "_post_status" \
        else (lambda: conformance.run_record_receiver(url, "PLACEHOLDER-TOKEN"))
    with pytest.raises(ValueError, match="user:password") as caught:
        call()
    assert PW not in str(caught.value) and "receiver.example.invalid" in str(caught.value)


@pytest.mark.parametrize("url, names_password", [(f"https://u:{PW}@host.example", True),
                                                 ("https://host.example/a\nb", False)])
def test_unopenable_names_a_password_only_when_there_is_one(url, names_password, monkeypatch):
    for module in (compliance, _scripts_shared(monkeypatch)):
        said = module.unopenable(url, "HINT")
        assert ("user:password" in said) == names_password and ("HINT" in said) == names_password
        assert PW not in said


def test_the_conformance_cli_says_a_refused_receiver_without_a_traceback(capsys, monkeypatch):
    from agentsmith import cli

    monkeypatch.setenv("GOVERNANCE_RECORD_TOKEN", "PLACEHOLDER-TOKEN")
    monkeypatch.setenv("GOVERNANCE_OPS_TOKEN", "PLACEHOLDER-TOKEN")
    for port in ("record", "ops"):
        code = cli.main(["conformance", "--port", port, "--receiver", f"https://u:{PW}@receiver.example.invalid"])
        err = capsys.readouterr().err
        assert code == 2, (port, err)
        assert "user:password" in err and PW not in err, (port, err)


def test_the_sovereign_probe_reports_a_user_and_password_it_cannot_send(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO / "scripts"))
    import verify_sovereign_endpoint as vse

    with pytest.raises(ValueError) as caught:
        vse._chat(f"https://u:{PW}@ollama.example.invalid", "model", "prompt", token="PLACEHOLDER-TOKEN")
    assert PW not in str(caught.value) and "ollama.example.invalid" in str(caught.value)


# ── A bad port is said as a bad port (Pass 11, item V) ───────────────────────

BAD_PORT = "http://127.0.0.1:6006x"
PORT_SAID = "has a port that is not one"


# The first thing the operator must change (Pass 12, item X): "must be https"
# is false for `https://`, and the port is named only once the rest would pass.
CAUSE = {
    "https://": "has no host", "http://": "has no host", "https:evil.com": "has no host",
    "http://[::1:6006": "does not parse", "https://[::1:6006": "does not parse",
    BAD_PORT: "has a port that is not one", "http://localhost:600600": "has a port that is not one",
    "https://h.example:-1": "has a port that is not one", "http://127.0.0.1:99999": "has a port that is not one",
    "https://collector.example:-1": "has a port that is not one",
    "ftp://collector.example:99999": "must be https",  # the scheme first
    "http://10.0.0.5:99999": "must be https",  # plain http to another host first
}


@pytest.mark.parametrize("url", [*URLS, *CAUSE])
def test_the_refusal_phrase_names_the_first_cause_and_the_copies_agree(url, monkeypatch):
    said = compliance.web_url_refusal(url)
    assert said == _scripts_shared(monkeypatch).web_url_refusal(url), url
    assert CAUSE.get(url, "must be https") in said, (url, said)


@pytest.mark.parametrize("base", ["https://", "http://localhost:99999"])
def test_the_probe_says_the_cause_once(monkeypatch, base):
    monkeypatch.syspath_prepend(str(REPO / "scripts"))
    import verify_sovereign_endpoint as vse

    with pytest.raises(ValueError) as caught:
        vse._chat(base, "model", "prompt")
    assert "with a host" not in str(caught.value) and "must be https" not in str(caught.value), caught.value


def test_the_exporter_says_a_bad_port(caplog):
    with caplog.at_level(logging.ERROR, logger="agentsmith.otlp"):
        assert otlp.span_exporter({"AGENT_PHOENIX_ENDPOINT": BAD_PORT}) is None
    assert PORT_SAID in caplog.text and "must be https" not in caplog.text


def test_span_shipping_says_a_bad_port(tmp_path, monkeypatch):
    gt = _gate_tracing(tmp_path, monkeypatch, BAD_PORT)
    line = gt.status_line(gt.ship())
    assert PORT_SAID in line and "must be https" not in line


def test_intake_says_a_bad_port(monkeypatch):
    monkeypatch.setenv("AGENTSMITH_PORTAL_URL", "http://localhost:3000x")
    monkeypatch.setenv("AGENTSMITH_INTAKE_TOKEN", "PLACEHOLDER-TOKEN")
    with pytest.raises(intake.IntakeError, match=PORT_SAID):
        intake.fetch("123")


def test_a_conformance_receiver_with_a_bad_port_is_said_by_name():
    from agentsmith import conformance

    with pytest.raises(conformance.ReceiverRefused, match=PORT_SAID):
        conformance.run_record_receiver(BAD_PORT, "PLACEHOLDER-TOKEN")


def test_the_conformance_cli_does_not_swallow_a_harness_bug(monkeypatch):
    """Pass 11, item W: the CLI caught every ValueError, so a bug in the harness
    read as a one-line refusal with exit 2."""
    from agentsmith import cli, conformance

    def broken(*_args, **_kwargs):
        raise ValueError("a harness bug")

    monkeypatch.setenv("GOVERNANCE_OPS_TOKEN", "PLACEHOLDER-TOKEN")
    monkeypatch.setattr(conformance, "ops_case_message", broken)
    with pytest.raises(ValueError, match="a harness bug"):
        cli.main(["conformance", "--port", "ops", "--receiver", "http://127.0.0.1:9"])
