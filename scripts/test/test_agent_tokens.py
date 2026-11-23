"""What a coding agent's session spends, and the commit that says so
(.agent-rfc/designs/coding-agent-tokens.md)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import agent_tokens as at

from test_process_gate import needs_git

# Claude Code sets it in its shell; it is the transcript's file name without `.jsonl`.
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"


def _line(message_id: str, output: int, cache_read: int = 0, cache_write: int = 0, new: int = 0) -> str:
    usage = {"output_tokens": output, "input_tokens": new, "cache_read_input_tokens": cache_read,
             "cache_creation_input_tokens": cache_write}
    return json.dumps({"type": "assistant", "message": {"id": message_id, "usage": usage}}) + "\n"


@pytest.fixture(autouse=True)
def _no_session_of_ours(monkeypatch):
    """The session running these tests has its own id; a test names one when it means to."""
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)


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
    totals = at.entry(repo)["totals"]
    assert totals == {"output": 15, "input": 3, "cache_read": 300, "cache_write": 7}


def test_only_new_whole_lines_are_read(repo, tmp_path):
    transcript = _session(repo, tmp_path, _line("m1", 10))
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(_line("m2", 20) + _line("m3", 30)[:-12])  # the last line is still being written
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    assert at.entry(repo)["totals"]["output"] == 30
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(_line("m3", 30)[-12:])
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    assert at.entry(repo)["totals"]["output"] == 60


def test_the_context_is_what_the_last_response_read(repo, tmp_path):
    _session(repo, tmp_path, _line("m1", 1, cache_read=1000), _line("m2", 1, cache_read=4000, cache_write=500, new=2))
    assert at.entry(repo)["context"] == 4502


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
    assert at.entry(repo, str(other))["totals"]["output"] == 3


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


def _commit(repo: Path, tmp_path: Path, env: dict, *, amend: bool = False, land: bool = True) -> str:
    """What commit-msg does, then the commit itself (or not, when a later hook refuses it)."""
    message = tmp_path / "MSG"
    message.write_text("feat: a thing\n", encoding="utf-8")
    at.add_trailers(message, repo, env, amend=amend)
    if land:
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "--no-verify", *(["--amend"] if amend else []), "-F", str(message)],
                       check=True)
    return message.read_text(encoding="utf-8")


def _tokens(message: str) -> str:
    return next((line for line in message.splitlines() if line.startswith("Agent-Tokens: ")), "")


def _spend(transcript: Path, message_id: str, output: int, cache_read: int = 0) -> None:
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(_line(message_id, output, cache_read=cache_read))


def test_each_commit_carries_what_was_spent_since_the_last(repo, tmp_path):
    transcript = _session(repo, tmp_path, _line("m1", 1500, cache_read=2_000_000, cache_write=30_000, new=40))
    first = at.trailers(repo, {"CLAUDECODE": "1"})
    assert first[0] == "Agent: claude-code"
    assert first[1].startswith("Agent-Tokens: output 1.5k, new input 40, cache read 2.0M, cache write 30.0k")
    assert first[1].endswith("(this session so far: its first commit)")
    _commit(repo, tmp_path, {"CLAUDECODE": "1"})
    _spend(transcript, "m2", 200, cache_read=500)
    second = _tokens(_commit(repo, tmp_path, {"CLAUDECODE": "1"}))
    assert second.startswith("Agent-Tokens: output 200, new input 0, cache read 500, cache write 0")
    assert second.endswith("(since this session's previous commit)")
    assert at.trailers(repo, {"CLAUDECODE": "1"}) == ["Agent: claude-code"]  # nothing spent since


# ── The 4.1.0 release review: R3 ──


def test_two_sessions_in_one_checkout_each_count_their_own(repo, tmp_path):
    """A's commit carried B's tokens, and A's third counted its first 100 again."""
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    a.write_text(_line("a1", 100), encoding="utf-8")
    b.write_text(_line("b1", 7), encoding="utf-8")
    env_a = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "a"}
    at.remember(repo, "claude", {"transcript_path": str(a)})
    assert "output 100," in _tokens(_commit(repo, tmp_path, env_a))
    at.remember(repo, "claude", {"transcript_path": str(b)})  # B's stop hook
    _spend(a, "a2", 5)
    assert "output 5," in _tokens(_commit(repo, tmp_path, env_a))
    at.remember(repo, "claude", {"transcript_path": str(a)})  # A's stop hook
    _spend(a, "a3", 3)
    third = _tokens(_commit(repo, tmp_path, env_a))
    assert "output 3," in third and "since this session's previous commit" in third
    assert "output 7," in _tokens(_commit(repo, tmp_path, {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "b"}))


def test_two_sessions_and_no_way_to_tell_which_says_only_who(repo, tmp_path):
    for name in ("a", "b"):
        (tmp_path / f"{name}.jsonl").write_text(_line(f"{name}1", 10), encoding="utf-8")
        at.remember(repo, "claude", {"transcript_path": str(tmp_path / f"{name}.jsonl")})
    assert at.trailers(repo, {"CLAUDECODE": "1"}) == ["Agent: claude-code"]


def test_a_commit_that_never_landed_does_not_move_the_baseline(repo, tmp_path):
    transcript = _session(repo, tmp_path, _line("m1", 100))
    _commit(repo, tmp_path, {"CLAUDECODE": "1"})
    _spend(transcript, "m2", 40)
    _commit(repo, tmp_path, {"CLAUDECODE": "1"}, land=False)  # a chained hook refused it
    _spend(transcript, "m3", 2)
    assert "output 42," in _tokens(_commit(repo, tmp_path, {"CLAUDECODE": "1"}))


def test_an_amended_commit_carries_what_the_one_it_replaces_did(repo, tmp_path):
    transcript = _session(repo, tmp_path, _line("m1", 100))
    _commit(repo, tmp_path, {"CLAUDECODE": "1"})
    _spend(transcript, "m2", 30)
    _commit(repo, tmp_path, {"CLAUDECODE": "1"})
    _spend(transcript, "m3", 5)
    amended = _tokens(_commit(repo, tmp_path, {"CLAUDECODE": "1"}, amend=True))
    assert "output 35," in amended and "since this session's previous commit" in amended
    _spend(transcript, "m4", 1)
    assert "output 1," in _tokens(_commit(repo, tmp_path, {"CLAUDECODE": "1"}))


def test_the_old_one_session_ledger_is_read(repo, tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(_line("m1", 10), encoding="utf-8")
    path = Path(subprocess.run(["git", "-C", str(repo), "rev-parse", "--absolute-git-dir"], capture_output=True,
                               text=True, check=True).stdout.strip()) / at.LEGACY_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    old = at._fresh("claude", str(transcript))
    old.update(at_last_commit={"output": 4, "input": 0, "cache_read": 0, "cache_write": 0})
    path.write_text(json.dumps(old), encoding="utf-8")
    assert "output 6," in _tokens(_commit(repo, tmp_path, {"CLAUDECODE": "1"}))


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
    assert at.entry(root)["totals"]["output"] == 42


@pytest.mark.parametrize("value, shown", [(950, "950"), (1_500, "1.5k"), (2_000_000, "2.0M"), (5_276_600_000, "5.3B")])
def test_counts_read_at_a_glance(value, shown):
    assert at._short(value) == shown


@needs_git
def test_a_real_amend_through_the_tenants_hooks_carries_both(tmp_path, monkeypatch):
    """The hook passes --amend through to the trailer step, not only the gate."""
    from test_framework_sync import _adopted, _git

    root = _adopted(tmp_path, monkeypatch)
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(_line("m1", 900), encoding="utf-8")
    at.remember(root, "claude", {"transcript_path": str(transcript)})
    monkeypatch.setenv("CLAUDECODE", "1")
    (root / "NOTES.md").write_text("notes\n", encoding="utf-8")
    _git(root, "add", "NOTES.md")
    assert _git(root, "commit", "-q", "-m", "docs: notes").returncode == 0
    _spend(transcript, "m2", 100)
    done = _git(root, "commit", "-q", "--amend", "-m", "docs: notes, amended")
    assert done.returncode == 0, done.stderr
    assert "Agent-Tokens: output 1.0k" in _git(root, "log", "-1", "--format=%B").stdout


# --- worktrees and concurrent sessions (the design's "Worktrees and concurrent sessions") ---


def _transcript(tmp_path: Path, name: str, *lines: str) -> Path:
    path = tmp_path / f"{name}.jsonl"
    path.write_text("".join(lines), encoding="utf-8")
    return path


def _claude(transcript: Optional[Path] = None) -> dict:
    env = {"CLAUDECODE": "1"}
    if transcript is not None:
        env[SESSION_ENV] = transcript.stem
    return env


def _tokens_in(lines: list) -> Optional[str]:
    return next((line for line in lines if line.startswith("Agent-Tokens: ")), None)


def test_two_sessions_in_one_repository_keep_their_own_counts(repo, tmp_path):
    one = _transcript(tmp_path, "aaaa-1111", _line("a1", 100))
    two = _transcript(tmp_path, "bbbb-2222", _line("b1", 7))
    at.remember(repo, "claude", {"transcript_path": str(one)})
    at.remember(repo, "claude", {"transcript_path": str(two)})
    with one.open("a", encoding="utf-8") as handle:
        handle.write(_line("a2", 50))
    at.remember(repo, "claude", {"transcript_path": str(one)})  # its stop hook, after the other started
    assert _tokens_in(at.trailers(repo, _claude(one))).startswith("Agent-Tokens: output 150,")
    assert _tokens_in(at.trailers(repo, _claude(two))).startswith("Agent-Tokens: output 7,")
    assert at.entry(repo, str(one))["totals"]["output"] == 150


def test_a_session_this_repository_never_recorded_gets_no_tokens(repo, tmp_path):
    _session(repo, tmp_path, _line("m1", 10))
    stranger = tmp_path / "cccc-3333.jsonl"
    assert at.trailers(repo, _claude(stranger)) == ["Agent: claude-code"]
    # and the recorded session's baseline is untouched by the stranger's commit
    assert _tokens_in(at.trailers(repo, _claude(tmp_path / "session.jsonl"))).startswith("Agent-Tokens: output 10,")


def test_several_sessions_and_no_session_id_get_no_tokens(repo, tmp_path):
    for name in ("aaaa-1111", "bbbb-2222"):
        at.remember(repo, "claude", {"transcript_path": str(_transcript(tmp_path, name, _line(name, 5)))})
    assert at.trailers(repo, {"CLAUDECODE": "1"}) == ["Agent: claude-code"]


def _git_dir(root: Path) -> Path:
    return Path(subprocess.run(["git", "-C", str(root), "rev-parse", "--absolute-git-dir"], capture_output=True,
                               text=True, check=True).stdout.strip())


def _old_ledger(git_dir: Path, transcript: Path, committed_output: int) -> Path:
    """What the code before 2026-11-22 wrote: one session, in this checkout's own git directory."""
    old = at.read_new(at._fresh("claude", str(transcript)))
    old["at_last_commit"] = {"output": committed_output, "input": 0, "cache_read": 0, "cache_write": 0}
    path = git_dir / "agentsmith" / "agent-tokens.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(old), encoding="utf-8")
    return path


def test_a_single_session_ledger_from_before_is_read_as_one_entry(repo, tmp_path):
    transcript = _transcript(tmp_path, "dddd-4444", _line("m1", 10), _line("m2", 5))
    _old_ledger(_git_dir(repo), transcript, committed_output=10)
    line = _tokens_in(at.trailers(repo, _claude(transcript)))
    assert line.startswith("Agent-Tokens: output 5,") and line.endswith("(since this session's previous commit)")


def test_older_code_writing_its_ledger_drops_no_other_session(repo, tmp_path):
    one = _transcript(tmp_path, "aaaa-1111", _line("a1", 100))
    two = _transcript(tmp_path, "bbbb-2222", _line("b1", 7))
    for transcript in (one, two):
        at.remember(repo, "claude", {"transcript_path": str(transcript)})
    old = _transcript(tmp_path, "oooo-0000", _line("o1", 3))
    legacy = _old_ledger(_git_dir(repo), old, committed_output=0)  # a session on an older branch, its stop hook
    assert set(at.load(repo).get("sessions", {})) == {str(one), str(two), str(old)}
    assert _tokens_in(at.trailers(repo, _claude(two))).startswith("Agent-Tokens: output 7,")
    assert json.loads(legacy.read_text(encoding="utf-8"))["transcript"] == str(old)  # never rewritten


@needs_git
def test_a_worktrees_own_ledger_from_before_is_read(repo, tmp_path):
    from test_framework_sync import _git

    (repo / "a").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "a")
    assert _git(repo, "commit", "-q", "-m", "docs: a").returncode == 0
    side = _worktree(repo, tmp_path)
    transcript = _transcript(tmp_path, "wwww-7777", _line("m1", 40), _line("m2", 2))
    _old_ledger(_git_dir(side), transcript, committed_output=40)
    assert _tokens_in(at.trailers(side, _claude(transcript))).startswith("Agent-Tokens: output 2,")


def test_a_gone_transcripts_session_is_dropped(repo, tmp_path):
    gone = _transcript(tmp_path, "gone", _line("g1", 1))
    kept = _transcript(tmp_path, "kept", _line("k1", 1))
    at.remember(repo, "claude", {"transcript_path": str(kept)})
    at.remember(repo, "claude", {"transcript_path": str(gone)})  # the newest, so only its absence drops it
    gone.unlink()
    with kept.open("a", encoding="utf-8") as handle:
        handle.write(_line("k2", 1))
    at.remember(repo, "claude", {"transcript_path": str(kept)})
    assert set(at.load(repo).get("sessions", {})) == {str(kept)}


def test_the_ledger_keeps_the_newest_sessions_only(repo, tmp_path):
    for index in range(at.MAX_SESSIONS + 3):
        at.remember(repo, "claude", {"transcript_path": str(_transcript(tmp_path, f"s{index:02d}", _line("x", 1)))})
    sessions = at.load(repo).get("sessions", {})
    assert len(sessions) == at.MAX_SESSIONS
    assert str(tmp_path / "s02.jsonl") not in sessions and str(tmp_path / "s03.jsonl") in sessions
    assert str(tmp_path / f"s{at.MAX_SESSIONS + 2:02d}.jsonl") in sessions


def test_a_malformed_entry_does_not_stop_the_recording(repo, tmp_path):
    transcript = _session(repo, tmp_path, _line("m1", 10))
    path = _git_dir(repo) / at.LEDGER
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["sessions"][str(transcript)]["seen"] = "yesterday"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    other = _transcript(tmp_path, "other", _line("x1", 3))
    at.remember(repo, "claude", {"transcript_path": str(other)})
    assert set(at.load(repo).get("sessions", {})) == {str(transcript), str(other)}


def test_a_filesystem_without_locks_still_records(repo, tmp_path, monkeypatch):
    import errno

    def unsupported(*_args):
        raise OSError(errno.ENOTSUP, "no locks here")

    monkeypatch.setattr(at.fcntl, "flock", unsupported)
    _session(repo, tmp_path, _line("m1", 10))
    assert at.entry(repo)["totals"]["output"] == 10


def test_a_held_lock_skips_the_bookkeeping_and_never_hangs(repo, tmp_path, monkeypatch):
    import fcntl
    import time

    transcript = _session(repo, tmp_path, _line("m1", 10))
    monkeypatch.setattr(at, "LOCK_SECONDS", 0.2)
    path = _git_dir(repo) / at.LEDGER
    with open(path.with_name(path.name + ".lock"), "a+", encoding="utf-8") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        started = time.monotonic()
        assert at.trailers(repo, _claude(transcript)) == ["Agent: claude-code"]
        assert time.monotonic() - started < 5
    assert _tokens_in(at.trailers(repo, _claude(transcript))).startswith("Agent-Tokens: output 10,")


def test_the_stop_hooks_note_is_its_own_sessions(repo, tmp_path, monkeypatch, capsys):
    import process_gate as pg

    small = _transcript(tmp_path, "small", _line("s1", 1, cache_read=1_000))
    big = _transcript(tmp_path, "big", _line("m1", 1, cache_read=200_000))
    at.remember(repo, "claude", {"transcript_path": str(small)})
    at.remember(repo, "claude", {"transcript_path": str(big)})  # read last
    monkeypatch.setitem(pg._IDE, "value", "claude")
    monkeypatch.setenv(at.NOTE_TOKENS_ENV, "150000")
    pg._context_note(repo, {"transcript_path": str(small)})
    assert capsys.readouterr().out == ""
    pg._context_note(repo, {"transcript_path": str(big)})
    assert "fresh session" in capsys.readouterr().out


def test_the_note_belongs_to_its_own_session(repo, tmp_path):
    big = _transcript(tmp_path, "big", _line("m1", 1, cache_read=200_000))
    small = _transcript(tmp_path, "small", _line("s1", 1, cache_read=1_000))
    at.remember(repo, "claude", {"transcript_path": str(big)})
    at.remember(repo, "claude", {"transcript_path": str(small)})
    assert at.context_note(repo, limit=150_000, transcript=str(small)) is None
    assert at.context_note(repo, limit=150_000, transcript=str(big)) is not None
    assert at.context_note(repo, limit=150_000, transcript=str(big)) is None  # once per step


def _worktree(root: Path, tmp_path: Path) -> Path:
    from test_framework_sync import _git

    side = tmp_path / "side"
    done = _git(root, "worktree", "add", "-q", "-b", "side", str(side))
    assert done.returncode == 0, done.stderr
    return side


@needs_git
def test_a_linked_worktree_reads_the_sessions_ledger(repo, tmp_path):
    from test_framework_sync import _git

    (repo / "a").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "a")
    assert _git(repo, "commit", "-q", "-m", "docs: a").returncode == 0
    transcript = _transcript(tmp_path, "eeee-5555", _line("m1", 300))
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    side = _worktree(repo, tmp_path)
    assert "Agent-Tokens: output 300," in _commit(side, tmp_path, _claude(transcript))
    # The commit landed on the worktree's branch; the main checkout's next commit, and
    # its hooks, must see it there and not claim the same tokens again.
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    assert at.trailers(repo, _claude(transcript)) == ["Agent: claude-code"]


@needs_git
def test_a_real_commit_from_a_linked_worktree_carries_the_tokens(tmp_path, monkeypatch):
    """The case that lost the trailer: the session's hooks ran in the main checkout,
    the commit was made in a worktree, through the worktree's own commit-msg hook."""
    from test_framework_sync import _adopted, _git

    root = _adopted(tmp_path, monkeypatch)
    transcript = _transcript(tmp_path, "ffff-6666", _line("m1", 900, cache_read=50_000))
    payload = json.dumps({"cwd": str(root), "transcript_path": str(transcript), "hook_event_name": "SessionStart"})
    done = subprocess.run([sys.executable, str(HERE.parent / "process_gate.py"), "session-start", "--ide", "claude"],
                          input=payload, capture_output=True, text=True, cwd=root, check=False)
    assert done.returncode == 0, done.stderr
    side = _worktree(root, tmp_path)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv(SESSION_ENV, transcript.stem)
    (side / "NOTES.md").write_text("notes\n", encoding="utf-8")
    _git(side, "add", "NOTES.md")
    done = _git(side, "commit", "-q", "-m", "docs: notes")
    assert done.returncode == 0, done.stderr
    body = _git(side, "log", "-1", "--format=%B").stdout
    assert "Agent: claude-code" in body and "Agent-Tokens: output 900" in body, body


def test_a_committed_session_outlasts_the_cap(repo, tmp_path):
    """Pass 11: a session known only from a legacy ledger had no `seen`, so the cap dropped
    it right after its commit, the legacy copy came back, and the next commit repeated it."""
    for index in range(at.MAX_SESSIONS):
        at.remember(repo, "claude", {"transcript_path": str(_transcript(tmp_path, f"s{index:02d}", _line("x", 1)))})
    legacy = _transcript(tmp_path, "llll-8888", _line("m1", 100), _line("m2", 7))
    _old_ledger(_git_dir(repo), legacy, committed_output=100)
    assert "Agent-Tokens: output 7," in _commit(repo, tmp_path, _claude(legacy))
    assert str(legacy) in at.load(repo).get("sessions", {})
    assert at.trailers(repo, _claude(legacy)) == ["Agent: claude-code"]  # nothing spent since


def test_sessions_are_ordered_even_when_the_clock_stands_still(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(at.time, "time", lambda: 1_000.0)
    for index in range(3):
        at.remember(repo, "claude", {"transcript_path": str(_transcript(tmp_path, f"t{index}", _line("x", 1)))})
    seen = {Path(key).stem: entry["seen"] for key, entry in at.load(repo).get("sessions", {}).items()}
    assert seen["t0"] < seen["t1"] < seen["t2"]


def test_a_ledger_a_later_version_wrote_is_left_alone(repo, tmp_path):
    transcript = _transcript(tmp_path, "nnnn-9999", _line("m1", 10))
    path = _git_dir(repo) / at.LEDGER
    path.parent.mkdir(parents=True)
    later = json.dumps({"version": at.VERSION + 1, "sessions": {str(transcript): {"transcript": str(transcript)}}})
    path.write_text(later, encoding="utf-8")
    assert at.remember(repo, "claude", {"transcript_path": str(transcript)}) is None
    assert at.trailers(repo, _claude(transcript)) == ["Agent: claude-code"]
    assert path.read_text(encoding="utf-8") == later


def test_the_usage_is_only_the_commands(capsys):
    assert at.main(["nonsense"]) == 2
    assert capsys.readouterr().err.splitlines()[0].strip().startswith("agent_tokens.py trailers")


@needs_git
def test_the_stop_command_gives_its_sessions_note(tmp_path, monkeypatch):
    """The note reaches the person through the stop command, for the session stopping,
    not only through `_context_note`; a smaller session recorded alongside gets none."""
    from test_framework_sync import _adopted

    root = _adopted(tmp_path, monkeypatch)
    monkeypatch.setenv(at.NOTE_TOKENS_ENV, "150000")

    def stop(transcript: Path) -> str:
        payload = json.dumps({"cwd": str(root), "transcript_path": str(transcript), "stop_hook_active": False,
                              "hook_event_name": "Stop"})
        done = subprocess.run([sys.executable, str(HERE.parent / "process_gate.py"), "stop", "--ide", "claude"],
                              input=payload, capture_output=True, text=True, cwd=root, check=False)
        assert done.returncode == 0, done.stderr
        return done.stdout

    big = _transcript(tmp_path, "big", _line("m1", 1, cache_read=200_000))
    small = _transcript(tmp_path, "small", _line("s1", 1, cache_read=1_000))
    assert "fresh session" in stop(big)
    assert "fresh session" not in stop(small)


def test_a_legacy_session_whose_transcript_is_gone_is_not_read(repo, tmp_path):
    """Pass 12: the old ledger is never rewritten, so a gone session it held came back on
    every read, and a second session stopped every trailer from a Claude Code without the id."""
    old = _transcript(tmp_path, "old", _line("o1", 3))
    _old_ledger(_git_dir(repo), old, committed_output=0)
    old.unlink()
    new = _session(repo, tmp_path, _line("n1", 9))
    assert set(at.load(repo).get("sessions", {})) == {str(new)}
    assert _tokens_in(at.trailers(repo, {"CLAUDECODE": "1"})).startswith("Agent-Tokens: output 9,")


def test_report_says_when_a_later_version_wrote_the_ledger(repo, monkeypatch, capsys):
    path = _git_dir(repo) / at.LEDGER
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": at.VERSION + 1, "sessions": {}}), encoding="utf-8")
    monkeypatch.chdir(repo)
    assert at.main(["report"]) == 0
    out = capsys.readouterr().out
    assert "later AgentSmith release" in out and "no coding-agent session" not in out


def test_the_ledger_keeps_the_umask_mode(repo, tmp_path):
    previous = os.umask(0o002)
    try:
        _session(repo, tmp_path, _line("m1", 1))
    finally:
        os.umask(previous)
    assert (_git_dir(repo) / at.LEDGER).stat().st_mode & 0o777 == 0o664


def test_an_unwritable_ledger_still_says_who(repo, tmp_path):
    transcript = _transcript(tmp_path, "uuuu-1212", _line("m1", 5))
    (_git_dir(repo) / "agentsmith").write_text("not a directory\n", encoding="utf-8")
    assert at.trailers(repo, _claude(transcript)) == ["Agent: claude-code"]


@needs_git
def test_the_stop_command_never_lends_another_sessions_note(tmp_path, monkeypatch, capsys):
    """Pass 12 and 16: the stop command records its session, then asks for that session's
    note. Another session's hook can run in between (they take the lock separately) and be
    read last; the note must still be this session's."""
    import process_gate as pg
    from test_framework_sync import _adopted

    root = _adopted(tmp_path, monkeypatch)
    monkeypatch.setenv(at.NOTE_TOKENS_ENV, "150000")
    monkeypatch.setitem(pg._IDE, "value", "claude")
    big = _transcript(tmp_path, "big", _line("m1", 1, cache_read=200_000))
    small = _transcript(tmp_path, "small", _line("s1", 1, cache_read=1_000))
    recorded = pg._remember_session

    def and_another_sessions_hook(root_: Path, payload: dict) -> None:
        recorded(root_, payload)
        at.remember(root_, "claude", {"transcript_path": str(big)})

    monkeypatch.setattr(pg, "_remember_session", and_another_sessions_hook)
    payload = {"cwd": str(root), "transcript_path": str(small), "stop_hook_active": False, "hook_event_name": "Stop"}
    assert pg.cmd_stop(payload) == 0
    assert "fresh session" not in capsys.readouterr().out
    assert at._latest(at.load(root)["sessions"])["transcript"] == str(big)  # the other session was read last


@pytest.mark.parametrize("field, bad", [("totals", None), ("offset", "x"), ("recent_ids", 5), ("context", "x"),
                                        ("noted", "x"), ("at_last_commit", {"output": "lots"}),
                                        ("pending", {"line": "x", "totals": {}, "base": None, "at": "soon"}),
                                        ("pending", {"line": "x", "totals": {}, "base": None, "at": float("inf")}),
                                        ("pending", {"line": "x", "totals": {}, "base": None, "at": 10 ** 400}),
                                        ("totals", {"output": 10 ** 400}), ("context", 10 ** 400),
                                        ("recent_ids", [["m0"]]), ("ide", ["deep"])])
def test_a_malformed_entry_is_read_again_and_the_commit_still_says_who(repo, tmp_path, field, bad):
    """Pass 13: a field of the wrong type raised past `trailers` and lost `Agent:`, and a
    bad offset failed every hook for that session. Each shape here is left out and read
    again: without its check, all but `totals` raise, and `totals` is counted from nothing."""
    transcript = _transcript(tmp_path, "zzzz-1313", _line("m1", 5, cache_read=200_000))
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    path = _git_dir(repo) / at.LEDGER
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["sessions"][str(transcript)][field] = bad
    path.write_text(json.dumps(ledger), encoding="utf-8")
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(_line("m2", 1, cache_read=200_000))
    assert at.context_note(repo, limit=150_000, transcript=str(transcript)) is None  # left out, not raised
    assert at.trailers(repo, _claude(transcript))[0] == "Agent: claude-code"
    assert at.remember(repo, "claude", {"transcript_path": str(transcript)})["totals"]["output"] == 6
    assert at.context_note(repo, limit=150_000, transcript=str(transcript)) is not None  # read again, whole


@pytest.mark.parametrize("offset", [10_000, 2 ** 63])
def test_an_offset_past_the_transcripts_end_reads_it_again(repo, tmp_path, offset):
    """Pass 14: an offset of the right type but past the end (a replaced transcript, or one
    too large to seek to) failed every hook and commit for that session."""
    transcript = _transcript(tmp_path, "pppp-1414", _line("m1", 5))
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    path = _git_dir(repo) / at.LEDGER
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["sessions"][str(transcript)]["offset"] = offset
    path.write_text(json.dumps(ledger), encoding="utf-8")
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(_line("m2", 3))  # a replaced transcript goes on growing below the old offset
    line = _tokens_in(at.trailers(repo, _claude(transcript)))
    assert line.startswith("Agent-Tokens: output 8,") and line.endswith("(this session so far: its first commit)")


def test_a_session_recorded_before_its_transcript_exists_is_kept(repo, tmp_path):
    """Pass 16: Claude Code writes the transcript just after the SessionStart hook, so
    dropping "gone" transcripts dropped every new session until its first Stop."""
    one = _session(repo, tmp_path, _line("a1", 40))
    new = tmp_path / "bbbb-2222.jsonl"
    at.remember(repo, "claude", {"transcript_path": str(new)})  # session start: no file yet
    assert at.trailers(repo, {"CLAUDECODE": "1"}) == ["Agent: claude-code"]  # two sessions, no id: none
    new.write_text(_line("b1", 7), encoding="utf-8")  # the first turn
    assert _tokens_in(at.trailers(repo, _claude(new))).startswith("Agent-Tokens: output 7,")
    assert str(one) in at.load(repo).get("sessions", {})


def test_an_unread_session_is_dropped_after_a_day(repo, tmp_path, monkeypatch):
    never = tmp_path / "never.jsonl"
    at.remember(repo, "claude", {"transcript_path": str(never)})
    real = time.time
    monkeypatch.setattr(at.time, "time", lambda: real() + at.UNREAD_SECONDS + 1)
    at.remember(repo, "claude", {"transcript_path": str(_transcript(tmp_path, "later", _line("x", 1)))})
    assert str(never) not in at.load(repo).get("sessions", {})


@needs_git
def test_a_first_turn_commit_from_a_worktree_carries_the_tokens(tmp_path, monkeypatch):
    """The real order: session start runs before Claude Code writes the transcript."""
    from test_framework_sync import _adopted, _git

    root = _adopted(tmp_path, monkeypatch)
    transcript = tmp_path / "cccc-3333.jsonl"
    payload = json.dumps({"cwd": str(root), "transcript_path": str(transcript), "hook_event_name": "SessionStart"})
    done = subprocess.run([sys.executable, str(HERE.parent / "process_gate.py"), "session-start", "--ide", "claude"],
                          input=payload, capture_output=True, text=True, cwd=root, check=False)
    assert done.returncode == 0, done.stderr
    transcript.write_text(_line("m1", 600), encoding="utf-8")
    side = _worktree(root, tmp_path)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv(SESSION_ENV, transcript.stem)
    (side / "NOTES.md").write_text("notes\n", encoding="utf-8")
    _git(side, "add", "NOTES.md")
    assert _git(side, "commit", "-q", "-m", "docs: notes").returncode == 0
    assert "Agent-Tokens: output 600" in _git(side, "log", "-1", "--format=%B").stdout


def test_a_session_unused_for_a_fortnight_is_forgotten(repo, tmp_path, monkeypatch):
    """R3's rule, kept through the merge: its transcript is still there, but nothing has
    read it for 14 days."""
    idle = _session(repo, tmp_path, _line("m1", 1))
    real = time.time
    monkeypatch.setattr(at.time, "time", lambda: real() + at._FORGET_AFTER + 1)
    at.remember(repo, "claude", {"transcript_path": str(_transcript(tmp_path, "later", _line("x", 1)))})
    assert str(idle) not in at.load(repo)["sessions"]


def test_a_legacy_session_unused_for_a_fortnight_is_not_read(repo, tmp_path):
    """Pass 19: the old ledger is never rewritten, so the fortnight rule applied on write
    never reached it; its sessions came back on every read and, with no session id, a
    second session stopped every trailer."""
    old = _transcript(tmp_path, "old", _line("o1", 3))
    path = _old_ledger(_git_dir(repo), old, committed_output=0)
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["seen"] = time.time() - at._FORGET_AFTER - 60
    path.write_text(json.dumps(ledger), encoding="utf-8")
    new = _session(repo, tmp_path, _line("n1", 9))
    assert set(at.load(repo)["sessions"]) == {str(new)}
    assert "Agent-Tokens: output 9," in _commit(repo, tmp_path, {"CLAUDECODE": "1"})


def test_a_seen_too_large_for_a_float_still_says_who_and_counts(repo, tmp_path):
    """Pass 20: `float()` of an int that large raises, and it did so for every session's
    hook and commit, since `_seen` orders them all."""
    transcript = _transcript(tmp_path, "hhhh-1515", _line("m1", 5))
    at.remember(repo, "claude", {"transcript_path": str(transcript)})
    path = _git_dir(repo) / at.LEDGER
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["sessions"][str(transcript)]["seen"] = 10 ** 400
    path.write_text(json.dumps(ledger), encoding="utf-8")
    at.remember(repo, "claude", {"transcript_path": str(_transcript(tmp_path, "other", _line("x", 1)))})
    lines = at.trailers(repo, _claude(transcript))
    assert lines[0] == "Agent: claude-code" and _tokens_in(lines).startswith("Agent-Tokens: output 5,")


def test_a_legacy_session_not_yet_written_counts_as_recorded(repo, tmp_path):
    """Pass 20: R3's code records a session at its start, before Claude Code writes the
    transcript. Taken from the legacy ledger, it is a second session, so a commit with no
    session id does not get the first session's spend."""
    one = _session(repo, tmp_path, _line("a1", 40))
    unread = tmp_path / "bbbb-2222.jsonl"
    legacy = _git_dir(repo) / at.LEGACY_LEDGER
    entry = at._fresh("claude", str(unread))
    entry["seen"] = time.time()
    legacy.write_text(json.dumps({"sessions": {str(unread): entry}}), encoding="utf-8")
    assert set(at.load(repo)["sessions"]) == {str(one), str(unread)}
    assert at.trailers(repo, {"CLAUDECODE": "1"}) == ["Agent: claude-code"]


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root can look into any directory")
def test_another_users_transcript_is_not_a_gone_one(repo, tmp_path):
    """Pass 21: in a repository shared between users, one user's hook cannot look into the
    other's 0700 transcript directory. `Path.is_file` raised for it before Python 3.13, so
    every write failed and the second user was never recorded; on later versions the first
    user's session read as gone and was dropped."""
    private = tmp_path / "theirs"
    private.mkdir()
    theirs = _transcript(private, "aaaa-1111", _line("a1", 40))
    at.remember(repo, "claude", {"transcript_path": str(theirs)})
    private.chmod(0)
    try:
        mine = _transcript(tmp_path, "bbbb-2222", _line("b1", 9))
        assert at.remember(repo, "claude", {"transcript_path": str(mine)}) is not None
        assert set(at.load(repo)["sessions"]) == {str(theirs), str(mine)}
        assert "Agent-Tokens: output 9," in _commit(repo, tmp_path, _claude(mine))
    finally:
        private.chmod(0o700)


def test_a_ledger_nested_too_deep_to_read_is_replaced(repo, tmp_path):
    """Pass 21: `json.loads` raises `RecursionError` (not a `ValueError`) past some depth:
    about a thousand on Python 3.11, far deeper on 3.14; this depth is past both."""
    path = _git_dir(repo) / at.LEDGER
    path.parent.mkdir(parents=True)
    path.write_text('{"x": ' + "[" * 1_000_000 + "]" * 1_000_000 + "}", encoding="utf-8")
    transcript = _session(repo, tmp_path, _line("m1", 5))
    assert "Agent-Tokens: output 5," in _commit(repo, tmp_path, _claude(transcript))


def test_an_entry_keeps_only_the_fields_this_code_writes(repo, tmp_path):
    """Pass 21: anything else, nested deep enough, made the ledger's own snapshot raise on
    Python 3.11; the rule is tested here, at a depth that loads on every version."""
    transcript = _session(repo, tmp_path, _line("m1", 5))
    path = _git_dir(repo) / at.LEDGER
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["sessions"][str(transcript)]["junk"] = json.loads("[" * 20 + "]" * 20)
    path.write_text(json.dumps(ledger), encoding="utf-8")
    assert "Agent-Tokens: output 5," in _commit(repo, tmp_path, _claude(transcript))
    assert "junk" not in at.entry(repo, str(transcript))


def test_a_count_no_response_has_adds_nothing(repo, tmp_path):
    """Pass 21: a transcript count of 2**63 or more was saved and then refused on read, and
    one too large for a float lost `Agent:` where it was shown."""
    transcript = _session(repo, tmp_path, _line("m1", 5))
    _spend(transcript, "m2", 10 ** 400)
    _spend(transcript, "m3", 2)
    assert "Agent-Tokens: output 7," in _commit(repo, tmp_path, _claude(transcript))
    assert at.entry(repo, str(transcript))["totals"]["output"] == 7


def test_any_failure_in_the_count_keeps_who(repo, tmp_path, monkeypatch):
    """The guarantee at its boundary: whatever goes wrong while counting, the commit still
    says which agent made it."""
    def broken(*_args):
        raise RuntimeError("anything")

    monkeypatch.setattr(at, "_spend", broken)
    assert at.trailers(repo, {"CLAUDECODE": "1"}) == ["Agent: claude-code"]


def test_an_entry_is_rebuilt_from_what_this_code_writes_at_every_depth(repo, tmp_path):
    """Pass 22: an unknown key inside a count or `pending`, or a value that is not a string
    in `ide`, still carried any value into the write, where one nested deep enough failed
    every session's write on Python 3.11–3.13. The rule is tested, not the depth: how deep
    a value loads and encodes differs by version (Pass 23)."""
    transcript = _session(repo, tmp_path, _line("m1", 5))
    path = _git_dir(repo) / at.LEDGER
    ledger = json.loads(path.read_text(encoding="utf-8"))
    entry = ledger["sessions"][str(transcript)]
    deep = json.loads("[" * 20 + "]" * 20)
    entry["totals"]["x"] = deep
    entry["at_last_commit"] = {"output": 0, "y": deep}
    entry["pending"] = {"line": "Agent-Tokens: none", "totals": {"output": 1, "z": deep}, "base": None, "at": 1.0,
                        "w": deep}
    path.write_text(json.dumps(ledger), encoding="utf-8")
    kept = at.entry(repo, str(transcript))
    assert set(kept["totals"]) == set(at.KINDS) and set(kept["at_last_commit"]) == set(at.KINDS)
    assert set(kept["pending"]) == {"line", "totals", "base", "at"} and set(kept["pending"]["totals"]) == set(at.KINDS)
    assert "Agent-Tokens: output 5," in _commit(repo, tmp_path, _claude(transcript))
