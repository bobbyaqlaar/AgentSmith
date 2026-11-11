"""What a coding agent's session spends, and the commit that says so
(.agent-rfc/designs/coding-agent-tokens.md)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import agent_tokens as at

from test_process_gate import needs_git


def _line(message_id: str, output: int, cache_read: int = 0, cache_write: int = 0, new: int = 0) -> str:
    usage = {"output_tokens": output, "input_tokens": new, "cache_read_input_tokens": cache_read,
             "cache_creation_input_tokens": cache_write}
    return json.dumps({"type": "assistant", "message": {"id": message_id, "usage": usage}}) + "\n"


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    return root


def _session(repo: Path, tmp_path: Path, *lines: str) -> Path:
    transcript = tmp_path / "session.jsonl"
    transcript.write_text("".join(lines), encoding="utf-8")
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    return transcript


def test_one_response_over_several_lines_is_counted_once(repo, tmp_path):
    _session(repo, tmp_path, _line("m1", 10, cache_read=100), _line("m1", 10, cache_read=100),
             _line("m2", 5, cache_read=200, cache_write=7, new=3))
    totals = at.load(repo)["totals"]
    assert totals == {"output": 15, "input": 3, "cache_read": 300, "cache_write": 7}


def test_only_new_whole_lines_are_read(repo, tmp_path):
    transcript = _session(repo, tmp_path, _line("m1", 10))
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(_line("m2", 20) + _line("m3", 30)[:-12])  # the last line is still being written
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    assert at.load(repo)["totals"]["output"] == 30
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(_line("m3", 30)[-12:])
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    assert at.load(repo)["totals"]["output"] == 60


def test_the_context_is_what_the_last_response_read(repo, tmp_path):
    _session(repo, tmp_path, _line("m1", 1, cache_read=1000), _line("m2", 1, cache_read=4000, cache_write=500, new=2))
    assert at.load(repo)["context"] == 4502


@pytest.mark.parametrize("ide, payload", [("cursor", {"transcript_path": "/x"}), ("claude", {}),
                                          ("claude", {"transcript_path": ""})])
def test_another_agent_or_no_transcript_records_nothing(repo, ide, payload):
    assert at.remember(repo, ide, payload) is None
    assert at.load(repo) == {}


def test_a_new_session_starts_from_zero(repo, tmp_path):
    _session(repo, tmp_path, _line("m1", 10))
    other = tmp_path / "other.jsonl"
    other.write_text(_line("x1", 3), encoding="utf-8")
    at.remember(repo, "claude", {"transcript_path": str(other)})
    assert at.load(repo)["totals"]["output"] == 3


def test_the_note_comes_once_per_step(repo, tmp_path):
    transcript = _session(repo, tmp_path, _line("m1", 1, cache_read=149_000))
    assert at.context_note(repo, limit=150_000) is None
    for message_id, size, expected in (("m2", 151_000, True), ("m3", 170_000, False), ("m4", 201_000, True)):
        with transcript.open("a", encoding="utf-8") as handle:
            handle.write(_line(message_id, 1, cache_read=size))
        at.remember(repo, "claude", {"transcript_path": str(transcript)})
        note = at.context_note(repo, limit=150_000)
        assert (note is not None) is expected, (size, note)
    assert "fresh session" in (at.context_note(repo, limit=10) or "fresh session")


def test_no_agent_no_trailer(repo, tmp_path):
    _session(repo, tmp_path, _line("m1", 10))
    assert at.trailers(repo, {}) == []


def test_an_agent_without_a_session_says_only_who(repo):
    assert at.trailers(repo, {"CLAUDECODE": "1"}) == ["Agent: claude-code"]


def test_each_commit_carries_what_was_spent_since_the_last(repo, tmp_path):
    transcript = _session(repo, tmp_path, _line("m1", 1500, cache_read=2_000_000, cache_write=30_000, new=40))
    first = at.trailers(repo, {"CLAUDECODE": "1"})
    assert first[0] == "Agent: claude-code"
    assert first[1].startswith("Agent-Tokens: output 1.5k, new input 40, cache read 2.0M, cache write 30.0k")
    assert first[1].endswith("(this session so far: its first commit)")
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(_line("m2", 200, cache_read=500))
    second = at.trailers(repo, {"CLAUDECODE": "1"})
    assert second[1].startswith("Agent-Tokens: output 200, new input 0, cache read 500, cache write 0")
    assert second[1].endswith("(since this session's previous commit)")
    assert at.trailers(repo, {"CLAUDECODE": "1"}) == ["Agent: claude-code"]  # nothing spent since


def test_the_trailers_land_in_the_message(repo, tmp_path):
    _session(repo, tmp_path, _line("m1", 7))
    message = tmp_path / "MSG"
    message.write_text("feat: a thing\n\nDesign: d.md\nReview: r.md\n", encoding="utf-8")
    at.add_trailers(message, repo, {"CLAUDECODE": "1"})
    text = message.read_text(encoding="utf-8")
    assert "Design: d.md" in text and "Agent: claude-code" in text and "Agent-Tokens: output 7" in text


@needs_git
def test_a_real_commit_through_the_tenants_hooks_carries_the_trailers(tmp_path, monkeypatch):
    """The hook path, not only the module: an adopted tenant's own commit-msg hook."""
    from test_framework_sync import _adopted, _git

    root = _adopted(tmp_path, monkeypatch)
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(_line("m1", 900, cache_read=50_000), encoding="utf-8")
    at.remember(root, "claude", {"transcript_path": str(transcript)})
    monkeypatch.setenv("CLAUDECODE", "1")
    (root / "NOTES.md").write_text("notes\n", encoding="utf-8")
    _git(root, "add", "NOTES.md")
    done = _git(root, "commit", "-q", "-m", "docs: notes")
    assert done.returncode == 0, done.stderr
    body = _git(root, "log", "-1", "--format=%B").stdout
    assert "Agent: claude-code" in body and "Agent-Tokens: output 900" in body


@needs_git
def test_a_commit_made_by_hand_gets_no_trailer(tmp_path, monkeypatch):
    from test_framework_sync import _adopted, _git

    root = _adopted(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    (root / "NOTES.md").write_text("notes\n", encoding="utf-8")
    _git(root, "add", "NOTES.md")
    assert _git(root, "commit", "-q", "-m", "docs: notes").returncode == 0
    assert "Agent:" not in _git(root, "log", "-1", "--format=%B").stdout


def test_trailers_join_the_existing_block_and_replace_only_themselves(repo, tmp_path):
    _session(repo, tmp_path, _line("m1", 7))
    message = tmp_path / "MSG"
    message.write_text("feat: a thing\n\nbody\n\nDesign: d.md\nAgent: someone-else\n\n# Please enter the message\n",
                       encoding="utf-8")
    at.add_trailers(message, repo, {"CLAUDECODE": "1"})
    lines = message.read_text(encoding="utf-8").splitlines()
    assert lines[:5] == ["feat: a thing", "", "body", "", "Design: d.md"]
    assert lines[5] == "Agent: claude-code" and lines[6].startswith("Agent-Tokens: output 7")
    assert lines[-1] == "# Please enter the message"
    assert sum(line.startswith("Agent: ") for line in lines) == 1


def test_a_message_with_no_trailers_gets_a_blank_line_first(repo, tmp_path):
    message = tmp_path / "MSG"
    message.write_text("docs: notes\n", encoding="utf-8")
    at.add_trailers(message, repo, {"CLAUDECODE": "1"})
    assert message.read_text(encoding="utf-8") == "docs: notes\n\nAgent: claude-code\n"


@needs_git
@pytest.mark.parametrize("event", ["stop", "session-start"])
def test_the_gates_own_hooks_record_the_session(tmp_path, monkeypatch, event):
    """The stop and session-start commands record the transcript, not only the module."""
    from test_framework_sync import _adopted

    root = _adopted(tmp_path, monkeypatch)
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(_line("m1", 42), encoding="utf-8")
    payload = json.dumps({"cwd": str(root), "transcript_path": str(transcript), "stop_hook_active": False,
                          "hook_event_name": "Stop" if event == "stop" else "SessionStart"})
    done = subprocess.run([sys.executable, str(HERE.parent / "process_gate.py"), event, "--ide", "claude"],
                          input=payload, capture_output=True, text=True, cwd=root, check=False)
    assert done.returncode == 0, done.stderr
    assert at.load(root)["totals"]["output"] == 42


@pytest.mark.parametrize("value, shown", [(950, "950"), (1_500, "1.5k"), (2_000_000, "2.0M"), (5_276_600_000, "5.3B")])
def test_counts_read_at_a_glance(value, shown):
    assert at._short(value) == shown
