"""
scripts/test/test_generate_ide_config_governance.py — the permission-to-deviate
rule reaches EVERY IDE, not just the one with hooks
(.agent-rfc/designs/governance-enforcement.md, G1).

The owner's requirement is that at design start, in any IDE, the agent asks
before deviating. The hooks can only block; what makes an agent ask is the
rule file it reads — so every generated file must carry the same block, from
the same source, and a drift check must fail when one does not.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
GENERATOR = REPO / "scripts" / "generate-ide-config.py"
sys.path.insert(0, str(REPO / "scripts"))

from _shared import load_script  # imported after the path insert above

# The generator is a hyphenated script; `load_script` is the one loader
# (scripts/test/test_security_registry.py fails on a hand-rolled second).
generate = load_script("generate-ide-config")

RULES = yaml.safe_load((REPO / "templates" / "agent-rules.yaml").read_text(encoding="utf-8"))
CTX = {"project_name": "t", "owner_id": "o@x", "otel_endpoint": "http://localhost:6006",
       "test_cmd": "pytest", "framework_version": "1.0.0"}
RENDERERS = {
    ".cursorrules": lambda: generate._render_cursorrules(RULES, "python-fastapi", CTX),
    "CLAUDE.md": lambda: generate._render_claude_md(RULES, CTX),
    "AGENTS.md": lambda: generate._render_agents_md(RULES, "python-fastapi", CTX),
    "GEMINI.md": lambda: generate._render_gemini_md(RULES, "python-fastapi", CTX),
    ".github/copilot-instructions.md": lambda: generate._render_copilot_instructions(RULES, "python-fastapi", CTX),
}


def test_the_rules_source_states_the_design_start_block():
    lines = generate._design_start_lines(RULES)
    assert lines, "agent-rules.yaml records.design_start is where this text lives"
    joined = " ".join(lines)
    assert "agentsmith design new" in joined and "agentsmith approve" in joined
    assert "ask the owner" in joined.lower()


@pytest.mark.parametrize("name", sorted(RENDERERS))
def test_every_ide_rule_file_tells_the_agent_to_ask_before_deviating(name):
    text = RENDERERS[name]()
    assert "ask the owner" in text.lower(), name
    assert "agentsmith approve" in text, name
    assert "## Pillars" in text or "`## Pillars`" in text, name


def test_an_antigravity_skill_that_covers_the_design_pillar_carries_it_too():
    skill = next(s for s in RULES["skills"] if 1 in (s.get("pillars") or []))
    text = generate._render_skill(skill, RULES, CTX)
    assert "agentsmith approve" in text


def test_write_regenerates_a_tracked_rule_file_and_check_only_sees_the_drift(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates/agent-rules.yaml").write_text(
        (REPO / "templates/agent-rules.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")

    def run(*args):
        return subprocess.run([sys.executable, str(GENERATOR), "--repo-root", str(tmp_path), *args],
                              capture_output=True, text=True, check=False)

    assert run().returncode == 0
    claude = tmp_path / "CLAUDE.md"
    assert "agentsmith approve" in claude.read_text(encoding="utf-8")

    claude.write_text("# hand-edited\n", encoding="utf-8")
    drifted = run("--check-only")
    assert drifted.returncode == 1 and "CLAUDE.md has drifted" in drifted.stdout

    assert run().returncode == 0 and claude.read_text(encoding="utf-8") == "# hand-edited\n", \
        "the default never overwrites: first provisioning must not clobber a repo's file"
    assert run("--write").returncode == 0
    assert "agentsmith approve" in claude.read_text(encoding="utf-8")
    assert run("--check-only").returncode == 0


def test_a_repos_own_notes_and_test_command_ride_in_every_generated_file(tmp_path):
    """A tenant's repo-specific instructions (OTS's two test surfaces, its
    vendoring note) must come from its config, not from hand edits to generated
    files — a hand edit makes the drift check fail on every regeneration."""
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates/agent-rules.yaml").write_text(
        (REPO / "templates/agent-rules.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework/process-gates.json").write_text(json.dumps({
        "gated": ["src/**", ".agenticframework/process-gates.json"],
        "extends": {"rules_extra": ["Two test surfaces: web and API."], "test_command": "make check"},
    }), encoding="utf-8")

    result = subprocess.run([sys.executable, str(GENERATOR), "--repo-root", str(tmp_path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

    for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".github/copilot-instructions.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "Two test surfaces: web and API." in text, name
        assert "make check" in text, name

    check = subprocess.run([sys.executable, str(GENERATOR), "--repo-root", str(tmp_path), "--check-only"],
                           capture_output=True, text=True, check=False)
    assert check.returncode == 0, check.stdout


def test_the_generator_reads_the_tenants_own_declaration(tmp_path):
    """CI runs the drift check with no arguments. Unless the defaults come from
    what the repo declares, CI generates different files from a developer and
    the check passes only on a placeholder owner."""
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates/agent-rules.yaml").write_text(
        (REPO / "templates/agent-rules.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework/tenant.yaml").write_text(
        'tenant:\n  id: acme\n  name: AcmeStudio\n  owner: owner@acme.example\n'
        'framework:\n  version: "1.3.0"\n', encoding="utf-8")

    subprocess.run([sys.executable, str(GENERATOR), "--repo-root", str(tmp_path)], check=True,
                   capture_output=True, text=True)

    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AcmeStudio" in text and "owner@acme.example" in text
    assert "unknown@unknown" not in text
    assert "1.3.0" in (tmp_path / ".cursorrules").read_text(encoding="utf-8")

