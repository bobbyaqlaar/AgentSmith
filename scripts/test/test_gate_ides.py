"""
scripts/test/test_gate_ides.py — G2a: one gate, six dialects.

The rules are one implementation; what differs per IDE is the shape of the
payload on stdin and the shape of the answer on stdout. Those differences live
in `gate_ides.py` and nowhere else, so a seventh IDE is a table entry and a
fixture rather than a second gate.

Every IDE has a golden payload under fixtures/ide-payloads/. Claude Code's is
verified by use — it is what this repo runs. Cursor's is from the vendor's docs,
re-read on 2026-09-17. The other four are the design's pinned table and are
NOT re-verified: the fixture is where a real session's payload gets pinned, and
these tests are what say whether anything else has to change when it does.

A write payload the adapter cannot read is DENIED, with the keys it saw. Field
names are the part most likely to be wrong, and a parser that shrugged would
leave a silent hole in exactly the IDEs nobody here tests daily.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import REPO, _write, needs_git

sys.path.insert(0, str(REPO / "scripts"))
import gate_ides as gi

FIXTURES = Path(__file__).parent / "fixtures" / "ide-payloads"


def _fixture(ide: str, event: str) -> dict:
    return json.loads((FIXTURES / f"{ide}-{event}.json").read_text(encoding="utf-8"))


# ── the six are declared in one place ────────────────────────────────────────


def test_the_ide_catalogue_is_not_empty() -> None:
    """Two tests below iterate `gi.IDES`; emptying it would pass both over
    nothing (.agent-rfc/designs/sibling-sweep.md)."""
    assert len(gi.IDES) >= 6, f"the IDE catalogue holds {len(gi.IDES)}"


def test_every_ide_has_a_parser_a_renderer_and_a_config_target() -> None:
    for ide in gi.IDES:
        adapter = gi.ADAPTERS[ide]
        assert adapter.config_path, ide
        assert callable(adapter.parse) and callable(adapter.render), ide


def test_the_registry_names_the_same_six() -> None:
    import gate_models as gm

    registry = gm.Registry.model_validate_json(
        (REPO / "templates" / "governance.json").read_text(encoding="utf-8"))
    assert {i.id for i in registry.ides} == set(gi.IDES)
    for ide in registry.ides:
        assert ide.config == gi.ADAPTERS[ide.id].config_path


@pytest.mark.parametrize("ide", gi.IDES)
def test_every_ide_has_a_golden_payload_for_every_event(ide) -> None:
    for event in ("pre-edit", "session-start", "stop"):
        assert (FIXTURES / f"{ide}-{event}.json").is_file(), f"{ide}-{event}.json"


# ── reading each dialect ─────────────────────────────────────────────────────


@pytest.mark.parametrize("ide", gi.IDES)
def test_an_edit_payload_yields_the_path_it_is_about(ide) -> None:
    event = gi.parse(ide, "pre-edit", _fixture(ide, "pre-edit"))
    assert event.kind == "edit"
    assert event.paths and event.paths[0].endswith("tool.py"), event.paths


@pytest.mark.parametrize("ide", gi.IDES)
def test_every_dialect_finds_the_repository(ide) -> None:
    """Cursor's stop and sessionStart carry no `cwd` at all — the root comes
    from `workspace_roots`. A gate that cannot find the repo checks nothing."""
    for name in ("pre-edit", "session-start", "stop"):
        event = gi.parse(ide, name, _fixture(ide, name))
        assert event.cwd, f"{ide} {name}"


def test_vs_code_spells_the_tool_fields_in_camel_case() -> None:
    """It reads Claude's config but not Claude's field names."""
    event = gi.parse("copilot", "pre-edit",
                     {"cwd": "/repo", "toolName": "Edit", "toolInput": {"filePath": "/repo/scripts/tool.py"}})
    assert event.kind == "edit" and event.paths == ["/repo/scripts/tool.py"]


def test_a_tool_that_is_not_an_edit_is_not_an_edit() -> None:
    event = gi.parse("claude", "pre-edit",
                     {"cwd": "/repo", "tool_name": "Read", "tool_input": {"file_path": "/repo/x.py"}})
    assert event.kind == "other"


def test_a_shell_tool_is_recognised_as_one() -> None:
    """G2b gates these; G2a has to tell them apart from an edit."""
    event = gi.parse("cursor", "pre-edit",
                     {"cwd": "/repo", "tool_name": "Shell", "tool_input": {"command": "git commit --no-verify"}})
    assert event.kind == "shell" and event.command == "git commit --no-verify"


def test_a_write_payload_nobody_can_read_is_refused_with_what_it_saw() -> None:
    """Field names are the part most likely to be wrong. A shrug here is a
    silent hole in the IDEs nobody tests daily."""
    with pytest.raises(gi.Unreadable) as raised:
        gi.parse("cursor", "pre-edit", {"cwd": "/repo", "tool_name": "Write", "tool_input": {"weird_key": "x"}})
    assert "weird_key" in str(raised.value)


def test_a_stop_payload_says_whether_it_is_a_repeat() -> None:
    assert gi.parse("claude", "stop", {"cwd": "/r", "stop_hook_active": True}).stop_active
    assert not gi.parse("claude", "stop", {"cwd": "/r"}).stop_active


# ── answering in each dialect ────────────────────────────────────────────────


def test_claude_denies_the_way_claude_reads_it() -> None:
    answer = json.loads(gi.render("claude", "deny", "no design covers it"))
    assert answer["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no design covers it" in answer["hookSpecificOutput"]["permissionDecisionReason"]


def test_cursor_denies_the_way_cursor_reads_it() -> None:
    answer = json.loads(gi.render("cursor", "deny", "no design covers it"))
    assert answer["permission"] == "deny"
    assert "no design covers it" in answer["user_message"]
    assert "no design covers it" in answer["agent_message"]


def test_cursor_blocks_a_turn_with_a_followup_message() -> None:
    answer = json.loads(gi.render("cursor", "block", "unreviewed changes"))
    assert "unreviewed changes" in answer["followup_message"]


def test_cursor_adds_session_context() -> None:
    answer = json.loads(gi.render("cursor", "context", "the rules"))
    assert answer["additional_context"] == "the rules"


@pytest.mark.parametrize("ide", gi.IDES)
def test_every_dialect_answers_every_decision_in_json(ide) -> None:
    for decision in ("deny", "block", "context"):
        rendered = gi.render(ide, decision, "because")
        assert json.loads(rendered), f"{ide} {decision}"
        assert "because" in rendered


@pytest.mark.parametrize("ide", gi.IDES)
def test_a_repeated_stop_never_blocks_twice(ide) -> None:
    """Blocking a turn that is already being blocked loops forever. Every IDE
    gets the warning shape instead, and the commit and CI gates still hold."""
    again = gi.render(ide, "block", "unreviewed", repeat=True)
    first = gi.render(ide, "block", "unreviewed", repeat=False)

    assert "unreviewed" in again
    assert again != first, "a repeat must not be the same answer as the first block"
    assert '"block"' not in again and '"deny"' not in again


# ── the gate speaks them end to end ──────────────────────────────────────────


@needs_git
@pytest.mark.parametrize("ide", gi.IDES)
def test_the_gate_denies_an_undesigned_edit_in_every_ide(gated_repo, ide) -> None:
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    payload = _fixture(ide, "pre-edit")
    payload = gi.ADAPTERS[ide].retarget(payload, str(gated_repo), str(gated_repo / "scripts" / "tool.py"))

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts" / "process_gate.py"), "pre-edit", "--ide", ide],
        cwd=gated_repo, input=json.dumps(payload), capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "scripts/tool.py" in result.stdout
    # In THIS ide's dialect: the same deny, rendered by the same adapter.
    assert sorted(json.loads(result.stdout)) == sorted(json.loads(gi.render(ide, "deny", "x")))


@needs_git
@pytest.mark.parametrize("ide", gi.IDES)
def test_a_write_the_adapter_cannot_read_is_denied_by_the_gate(gated_repo, ide) -> None:
    """The fail-closed half, end to end: the field names are the part most
    likely to be wrong, and a shrug here is a silent hole."""
    payload = {"cwd": str(gated_repo), "tool_name": "Write", "tool_input": {"weird_key": "x"}}

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts" / "process_gate.py"), "pre-edit", "--ide", ide],
        cwd=gated_repo, input=json.dumps(payload), capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "weird_key" in result.stdout
    assert sorted(json.loads(result.stdout)) == sorted(json.loads(gi.render(ide, "deny", "x")))


@needs_git
def test_the_ide_comes_from_the_flag_then_the_environment_then_claude(gated_repo, monkeypatch) -> None:
    assert gi.resolve(None, {}) == "claude"
    assert gi.resolve(None, {"AGENTSMITH_IDE": "cursor"}) == "cursor"
    assert gi.resolve("gemini", {"AGENTSMITH_IDE": "cursor"}) == "gemini"


def test_an_ide_nobody_wrote_an_adapter_for_is_named() -> None:
    with pytest.raises(ValueError, match="notepad"):
        gi.resolve("notepad", {})


def test_every_ide_hook_config_is_a_gated_path() -> None:
    """Editing a generated hook config is the way round the gate in a
    hook-capable IDE, so the config is itself gated — an edit to one needs a
    design, and the commit gate sees it either way."""
    import json as _json
    import sys as _sys

    _sys.path.insert(0, str(REPO / "scripts"))
    import process_gate as pg

    config = pg.Config(_json.loads((REPO / pg.CONFIG).read_text(encoding="utf-8")))
    for ide in gi.IDES:
        assert config.is_gated(gi.ADAPTERS[ide].config_path), gi.ADAPTERS[ide].config_path


# ── the configs that are generated, and the ones that are not ────────────────


@pytest.mark.parametrize("ide", gi.GENERATED)
def test_the_committed_config_is_the_generated_one(ide) -> None:
    """A hook config someone edited by hand is a gate that changed unreviewed."""
    target = REPO / gi.ADAPTERS[ide].config_path
    existing = json.loads(target.read_text(encoding="utf-8"))
    expected = json.dumps(gi.render_config(ide, existing), indent=2, ensure_ascii=False) + "\n"
    assert target.read_text(encoding="utf-8") == expected, \
        "run scripts/generate-ide-config.py --hooks"


def test_generating_claudes_config_keeps_what_it_does_not_own() -> None:
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    rendered = gi.render_config("claude", settings)
    assert rendered["permissions"] == settings["permissions"]
    assert rendered["attribution"] == settings["attribution"]


def test_cursors_config_fails_closed_on_the_edit_gate() -> None:
    """The one IDE that lets a hook refuse on its own failure."""
    config = gi.render_config("cursor")
    pre_tool_use = config["hooks"]["preToolUse"][0]
    assert pre_tool_use["failClosed"] is True
    assert pre_tool_use["matcher"] == "Write", "preToolUse fires for every tool; Write is the edit gate"
    assert "--ide cursor" in pre_tool_use["command"]


def test_claudes_config_still_denies_when_the_launcher_cannot_run() -> None:
    # By matcher, not by position: the shell surface (G2b) added a second
    # PreToolUse entry, and indexing [0] silently started asserting about it.
    entries = gi.render_config("claude", {})["hooks"]["PreToolUse"]
    edit = next(e for e in entries if "Edit" in e["matcher"])
    command = edit["hooks"][0]["command"]
    assert "||" in command and "deny" in command


@pytest.mark.parametrize("ide", [i for i in gi.IDES if i not in gi.GENERATED])
def test_an_unverified_config_schema_is_refused_rather_than_guessed(ide) -> None:
    """A file in a shape nobody confirmed looks like enforcement and may be
    ignored in silence — worse than no file."""
    with pytest.raises(ValueError, match="no verified config schema"):
        gi.render_config(ide)
