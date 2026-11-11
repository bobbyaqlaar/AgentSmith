"""What AgentSmith puts into a coding agent's context stays within a budget
(.agent-rfc/designs/coding-agent-tokens.md). Every session reads the rule files and the
session-start message, and every turn re-reads them, so their size is paid for again and again.

Tokens are estimated as characters divided by four: close enough for a budget, and it needs
no tokenizer."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _shared import load_script

REPO = Path(__file__).resolve().parents[2]
RULE_FILE_TOKENS = 3_000
SESSION_START_TOKENS = 1_200


def _tokens(text: str) -> int:
    return len(text) // 4


def _generator():
    return load_script("generate-ide-config")


@pytest.mark.parametrize("stack", ["python-fastapi", "ts-react", "go"])
def test_every_rule_file_a_tenant_gets_stays_within_its_budget(stack):
    generator = _generator()
    rules = generator._load_rules(REPO / "templates" / "agent-rules.yaml")
    ctx = {**generator.declared_context(REPO), "stack": stack}
    over = {rel: _tokens(text) for rel, text, kind in generator.render_files(REPO, rules, ctx)
            if _tokens(text) > RULE_FILE_TOKENS}
    assert not over, f"rule files over {RULE_FILE_TOKENS} tokens (estimated) for {stack}: {over}"


def test_the_rule_files_carry_the_token_discipline():
    generator = _generator()
    rules = generator._load_rules(REPO / "templates" / "agent-rules.yaml")
    rendered = {rel: text for rel, text, _kind in generator.render_files(REPO, rules, generator.declared_context(REPO))}
    for rel in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".github/copilot-instructions.md"):
        assert "One slice per session" in rendered[rel], rel


def test_the_session_start_message_stays_within_its_budget():
    # No transcript_path: this runs against the real repository, whose session ledger is not the test's.
    payload = json.dumps({"cwd": str(REPO), "hook_event_name": "SessionStart"})
    # The gate itself, with this interpreter: the launcher looks for an installed environment,
    # which a CI runner does not have.
    gate = str(REPO / "scripts" / "process_gate.py")
    done = subprocess.run([sys.executable, gate, "session-start", "--ide", "claude"],
                          input=payload, capture_output=True, text=True, cwd=REPO, check=False)
    text = json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]
    assert _tokens(text) <= SESSION_START_TOKENS, f"{_tokens(text)} tokens (estimated)"
