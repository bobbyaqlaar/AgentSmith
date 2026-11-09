"""A run names the commit it was built from (.agent-rfc/designs/accountability-chain.md)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentsmith import ops_contract as oc, tracing
from agentsmith.version import app_commit

SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


@pytest.mark.parametrize("value, expected", [
    (SHA, SHA), (SHA[:7], SHA[:7]), (SHA.upper(), SHA), (f"  {SHA}\n", SHA),
])
def test_a_hash_is_read(monkeypatch, value, expected):
    monkeypatch.setenv("APP_COMMIT", value)
    assert app_commit() == expected


@pytest.mark.parametrize("value", ["", "main", "abc123", "g" * 40, "a" * 41, "unknown", "../../etc"])
def test_anything_else_is_not_a_commit(monkeypatch, value):
    monkeypatch.setenv("APP_COMMIT", value)
    assert app_commit() is None


def test_unset_is_not_a_commit(monkeypatch):
    monkeypatch.delenv("APP_COMMIT", raising=False)
    assert app_commit() is None


def test_a_run_may_carry_a_commit_and_need_not():
    assert oc.RunMessage(run_id="r", status="success", app_commit=SHA).app_commit == SHA
    assert oc.RunMessage(run_id="r", status="success").app_commit is None


@pytest.mark.parametrize("value", ["main", "ABCDEF1", "abc"])
def test_a_run_refuses_what_is_not_a_lowercase_hash(value):
    with pytest.raises(ValidationError):
        oc.RunMessage(run_id="r", status="success", app_commit=value)


def _resource(monkeypatch) -> dict:
    monkeypatch.setenv("AGENT_PROJECT_NAME", "p")
    return tracing.resource_attributes()


def test_the_trace_resource_names_the_commit(monkeypatch):
    monkeypatch.setenv("APP_COMMIT", SHA)
    assert _resource(monkeypatch)["app.commit"] == SHA


def test_the_trace_resource_says_nothing_without_one(monkeypatch):
    monkeypatch.delenv("APP_COMMIT", raising=False)
    assert "app.commit" not in _resource(monkeypatch)


def test_the_deploy_templates_set_it_from_the_commit_ci_validated():
    root = Path(__file__).resolve().parents[2] / "workflow-templates"
    for name in ("cd-production.yml", "cd-staging.yml"):
        assert "APP_COMMIT: ${{ github.event.workflow_run.head_sha }}" in (root / name).read_text(encoding="utf-8")


def test_the_gateway_sends_the_commit_with_each_run(monkeypatch):
    from agentsmith.llm_gateway import LLMGateway

    sent = []
    monkeypatch.setattr(oc, "send", lambda message, **_k: sent.append(message) or 200)
    monkeypatch.setenv(oc.URL_ENV, "http://127.0.0.1:9")
    monkeypatch.setenv(oc.TOKEN_ENV, "aso_t")
    monkeypatch.setenv("APP_COMMIT", SHA)
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.tenant_id = "someone"
    gateway._report_run_status("run-1", "success")
    assert sent[0].app_commit == SHA
