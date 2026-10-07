"""
scripts/test/test_env_file_credentials.py — a repository's .env wins for its
credentials in script-only processes too, and `agentsmith doctor` reports where
the shell would have overridden one (.agent-rfc/designs/env-file-credentials.md).

The runtime half is in runtime/test/test_config.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import _shared
from _shared import load_script


def test_the_standalone_credential_rule_is_the_runtimes():
    """A deliberate mirror — scripts run where runtime/ is absent — pinned."""
    from runtime.config import CREDENTIAL_NAME

    assert _shared._CREDENTIAL_NAME.pattern == CREDENTIAL_NAME.pattern


def _tenant(tmp_path: Path, dotenv: str, tenant_yaml: str = "tenant:\n  id: t\n") -> Path:
    (tmp_path / ".agenticframework").mkdir(exist_ok=True)
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(tenant_yaml)
    (tmp_path / ".env").write_text(dotenv)
    return tmp_path


@pytest.fixture(autouse=True)
def _said(monkeypatch):
    monkeypatch.setattr(_shared, "_CREDENTIALS_SAID", set())


def test_standalone_a_declared_credential_beats_the_shell_by_name(tmp_path, monkeypatch, capsys):
    root = _tenant(tmp_path, "GROQ_API_KEY=declared-1\nPLAIN_SETTING=from-file\n")
    monkeypatch.setenv("GROQ_API_KEY", "stale-2")
    monkeypatch.setenv("PLAIN_SETTING", "from-shell")

    _shared._load_dotenv_standalone(root)

    assert os.environ["GROQ_API_KEY"] == "declared-1"
    assert os.environ["PLAIN_SETTING"] == "from-shell", "only credentials change precedence"
    err = capsys.readouterr().err
    assert "GROQ_API_KEY" in err and "declared-1" not in err and "stale-2" not in err


def test_standalone_env_overrides_lets_the_shell_win(tmp_path, monkeypatch, capsys):
    root = _tenant(tmp_path, "GROQ_API_KEY=declared\n", "env_overrides: [GROQ_API_KEY]\n")
    monkeypatch.setenv("GROQ_API_KEY", "deliberate")

    _shared._load_dotenv_standalone(root)

    assert os.environ["GROQ_API_KEY"] == "deliberate"
    assert capsys.readouterr().err == ""


def test_standalone_without_yaml_the_declaration_wins(tmp_path, monkeypatch):
    """No YAML to read env_overrides with: the safe side is the declared key."""
    root = _tenant(tmp_path, "GROQ_API_KEY=declared\n", "env_overrides: [GROQ_API_KEY]\n")
    monkeypatch.setenv("GROQ_API_KEY", "deliberate")
    monkeypatch.setitem(sys.modules, "yaml", None)

    _shared._load_dotenv_standalone(root)

    assert os.environ["GROQ_API_KEY"] == "declared"


# ── agentsmith doctor ─────────────────────────────────────────────────────────


def test_doctor_finds_credentials_exported_in_a_profile_by_name_and_line(tmp_path):
    verify = load_script("verify_system")
    (tmp_path / ".zshrc").write_text("export PATH=/x\nexport GEMINI_API_KEY='AIza-secret'\n# OPENAI_API_KEY=old\n")
    (tmp_path / ".bash_profile").write_text("OPS_PORTAL_SYNC_TOKEN=abc\nMAX_TOKENS=5\n")

    found = verify.exported_credentials(tmp_path)

    assert found == ["~/.zshrc:2 GEMINI_API_KEY", "~/.bash_profile:1 OPS_PORTAL_SYNC_TOKEN"]
    assert not any("secret" in f or "abc" in f for f in found)


def test_doctor_names_a_shell_credential_that_differs_from_the_repository(tmp_path):
    verify = load_script("verify_system")
    root = _tenant(tmp_path, "GEMINI_API_KEY=declared\nGROQ_API_KEY=same\nOPENAI_API_KEY=\nPLAIN=x\n"
                             "ANTHROPIC_API_KEY=declared\n", "env_overrides: [ANTHROPIC_API_KEY]\n")
    ambient = {"GEMINI_API_KEY": "stale", "GROQ_API_KEY": "same", "OPENAI_API_KEY": "shell", "PLAIN": "y",
               "ANTHROPIC_API_KEY": "deliberate"}

    assert verify.shadowed_credentials(root, ambient) == ["GEMINI_API_KEY"]


def test_doctor_without_a_dotenv_reports_nothing(tmp_path):
    assert load_script("verify_system").shadowed_credentials(tmp_path, {"GEMINI_API_KEY": "x"}) == []
