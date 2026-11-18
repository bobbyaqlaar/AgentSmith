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
                               text=True, check=True).stdout.strip()) / at.LEDGER
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


# ── The 4.1.0 review's second pass: P2-R4 (.agent-rfc/designs/scratch-dates-and-worktree-tokens.md) ──


@needs_git
def test_a_commit_in_a_linked_worktree_carries_its_sessions_tokens(repo, tmp_path):
    """P2-R4: the hooks recorded the session in the main checkout's git directory, and a
    commit in a linked worktree read its own, found nothing, and carried `Agent:` alone."""
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "commit", "-q", "--allow-empty", "--no-verify", "-m", "init"], check=True)
    worktree = tmp_path / "wt"
    subprocess.run([*git, "worktree", "add", "-q", "-b", "side", str(worktree)], check=True)
    env = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "session"}
    transcript = _session(repo, tmp_path, _line("m1", 1500))  # the hooks run in the main checkout

    first = _tokens(_commit(worktree, tmp_path, env))
    assert first.startswith("Agent-Tokens: output 1.5k")
    _spend(transcript, "m2", 200)
    second = _tokens(_commit(worktree, tmp_path, env))
    assert second.startswith("Agent-Tokens: output 200") and second.endswith("(since this session's previous commit)")
    assert at._ledger_path(worktree) == at._ledger_path(repo)
