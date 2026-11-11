"""scripts/agent_tokens.py — what a coding agent's session spends, from its own transcript.

Claude Code writes every response's usage to the session transcript, and its hook
payloads name that transcript (`transcript_path`). The session-start and stop hooks
record it here; the commit hook then writes the agent and what the session spent
since its previous commit onto the commit (.agent-rfc/designs/coding-agent-tokens.md).

Only Claude Code is read: the other agents' payloads and shells are unconfirmed (gap 11).
No measurement is no trailer, never a zero. Counts only — no prompt or response text
leaves the transcript.

One checkout may hold several sessions at once, so the ledger keeps one entry per
transcript, and a commit is charged to the session whose shell made it
(`CLAUDE_CODE_SESSION_ID`); with several sessions and no way to tell, it says only
which agent. The baseline moves only once the commit is seen to have landed, so a
commit a later hook refused charges nothing, and `--amend` carries what the commit it
replaces did (the 4.1.0 release review, R3).

    agent_tokens.py trailers [--amend] <message file>    add Agent / Agent-Tokens after the gate allowed
    agent_tokens.py report                     this repository's session, as the ledger has it
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Mapping, Optional

LEDGER = "agentsmith/agent-tokens.json"
KINDS = ("output", "input", "cache_read", "cache_write")
_USAGE_KEYS = {"output": "output_tokens", "input": "input_tokens",
               "cache_read": "cache_read_input_tokens", "cache_write": "cache_creation_input_tokens"}
# One response spans several transcript lines that repeat its usage; they are adjacent,
# so a short memory of ids is enough to count each response once.
_RECENT_IDS = 64
NOTE_TOKENS_ENV = "AGENTSMITH_CONTEXT_NOTE_TOKENS"
NOTE_TOKENS = 150_000
NOTE_STEP = 50_000
_KEEP_SESSIONS = 32
_FORGET_AFTER = 14 * 86_400


def _git_dir(root: Path) -> Optional[Path]:
    done = subprocess.run(["git", "-C", str(root), "rev-parse", "--absolute-git-dir"],
                          capture_output=True, text=True, check=False)
    return Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else None


def _ledger_path(root: Path) -> Optional[Path]:
    git_dir = _git_dir(root)
    return git_dir / LEDGER if git_dir else None


def load(root: Path) -> dict:
    """The ledger: `{"sessions": {transcript path: entry}}`. A ledger from before it kept
    one entry per session is read as that one session."""
    path = _ledger_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get("transcript"), str):
        return {"sessions": {data["transcript"]: data}}
    return data if isinstance(data.get("sessions"), dict) else {}


def _session_id(entry: dict) -> str:
    return str(entry.get("session_id") or Path(str(entry.get("transcript") or "")).stem)


def entry(root: Path, transcript: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> dict:
    """One session's entry: the named transcript, else the committing shell's session,
    else the only session there is. Empty when it cannot be told."""
    sessions = load(root).get("sessions") or {}
    if transcript is not None:
        return sessions.get(transcript) or {}
    wanted = (env or {}).get("CLAUDE_CODE_SESSION_ID")
    if wanted:
        return next((e for e in sessions.values() if _session_id(e) == wanted), {})
    return next(iter(sessions.values())) if len(sessions) == 1 else {}


def _store(root: Path, item: dict) -> None:
    ledger = load(root)
    sessions = ledger.setdefault("sessions", {})
    item["seen"] = time.time()
    sessions[item["transcript"]] = item
    fresh = sorted(sessions.items(), key=lambda kv: float(kv[1].get("seen") or 0), reverse=True)
    ledger["sessions"] = {k: v for k, v in fresh[:_KEEP_SESSIONS]
                          if k == item["transcript"] or time.time() - float(v.get("seen") or 0) < _FORGET_AFTER}
    _save(root, ledger)


def _save(root: Path, ledger: dict) -> None:
    path = _ledger_path(root)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def _fresh(ide: str, transcript: str, session_id: str = "") -> dict:
    return {"ide": ide, "transcript": transcript, "session_id": session_id or Path(transcript).stem, "offset": 0,
            "recent_ids": [], "totals": dict.fromkeys(KINDS, 0), "context": 0, "at_last_commit": None,
            "before_last_commit": None, "last_commit": None, "pending": None, "noted": 0}


def read_new(entry: dict) -> dict:
    """Add the responses written since the last read. Only whole lines are consumed:
    a line still being written is read next time."""
    path = Path(entry["transcript"])
    try:
        with path.open("rb") as handle:
            handle.seek(int(entry.get("offset") or 0))
            chunk = handle.read()
    except OSError:
        return entry
    end = chunk.rfind(b"\n")
    if end < 0:
        return entry
    recent: deque[str] = deque(entry.get("recent_ids") or [], maxlen=_RECENT_IDS)
    totals = {kind: int((entry.get("totals") or {}).get(kind, 0)) for kind in KINDS}
    context = int(entry.get("context") or 0)
    for raw in chunk[: end + 1].splitlines():
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        message = record.get("message") if isinstance(record, dict) else None
        usage = message.get("usage") if isinstance(message, dict) else None
        if not isinstance(usage, dict):
            continue
        message_id = message.get("id")
        if message_id and message_id in recent:
            continue
        if message_id:
            recent.append(message_id)
        for kind, key in _USAGE_KEYS.items():
            value = usage.get(key)
            totals[kind] += value if isinstance(value, int) and value > 0 else 0
        context = sum(usage.get(key) or 0 for key in ("input_tokens", "cache_read_input_tokens",
                                                       "cache_creation_input_tokens")
                      if isinstance(usage.get(key), int))
    entry.update(offset=int(entry.get("offset") or 0) + end + 1, recent_ids=list(recent), totals=totals,
                 context=context)
    return entry


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else ""


def _settle(root: Path, item: dict) -> dict:
    """Move the baseline for a commit this session's hook prepared, once it is seen to
    have landed: a recent commit whose message carries the exact line written. One
    that never appeared was refused after the trailer step, and charged nothing."""
    pending = item.get("pending")
    if not isinstance(pending, dict):
        return item
    item["pending"] = None
    since = max(0, int(float(pending.get("at") or 0)) - 5)
    log = _git(root, "log", "-n", "50", f"--since={since}", "--format=%H%x00%B%x1e")
    landed = next((record.split("\0", 1)[0].strip() for record in log.split("\x1e")
                   if "\0" in record and pending.get("line") in record.split("\0", 1)[1].splitlines()), None)
    if landed:
        item.update(before_last_commit=pending.get("base"), at_last_commit=pending.get("totals"),
                    last_commit=landed)
    return item


def remember(root: Path, ide: str, payload: Mapping[str, Any]) -> Optional[dict]:
    """Record the session a hook was called from, and bring its totals up to date.
    Other sessions in the same checkout keep their own entries."""
    transcript = payload.get("transcript_path") if ide == "claude" else None
    if not isinstance(transcript, str) or not transcript:
        return None
    item = entry(root, transcript) or _fresh(ide, transcript, str(payload.get("session_id") or ""))
    item = read_new(_settle(root, item))
    _store(root, item)
    return item


def context_note(root: Path, limit: Optional[int] = None, transcript: Optional[str] = None) -> Optional[str]:
    """A word to the person when the context each turn re-reads has grown, once per step."""
    ledger = entry(root, transcript, os.environ)
    context = int(ledger.get("context") or 0)
    try:
        limit = limit if limit is not None else int(os.environ.get(NOTE_TOKENS_ENV) or NOTE_TOKENS)
    except ValueError:
        limit = NOTE_TOKENS
    if not ledger or context < limit:
        return None
    step = limit + ((context - limit) // NOTE_STEP) * NOTE_STEP
    if int(ledger.get("noted") or 0) >= step:
        return None
    ledger["noted"] = step
    _store(root, ledger)
    return (f"This session's context is about {_short(context)} tokens, and every turn re-reads it. "
            "Commit what is done and start a fresh session for the next slice.")


def _short(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def agent(env: Mapping[str, str]) -> Optional[str]:
    """The coding agent whose shell made this commit — only the ones confirmed (gap 11)."""
    return "claude-code" if env.get("CLAUDECODE") else None


def trailers(root: Path, env: Mapping[str, str], amend: bool = False) -> list[str]:
    """`Agent:` and `Agent-Tokens:` for the commit being made. The baseline moves when
    the commit is seen to have landed, not here. Empty when the commit was not made
    from a recognised agent."""
    name = agent(env)
    if name is None:
        return []
    lines = [f"Agent: {name}"]
    item = entry(root, env=env)
    if item.get("transcript") and Path(item["transcript"]).is_file():
        item = read_new(_settle(root, item))
        now = {kind: int(item["totals"].get(kind, 0)) for kind in KINDS}
        # An amend replaces this session's last commit, so it carries what that one did.
        replacing = amend and item.get("last_commit") and item["last_commit"] == _git(root, "rev-parse", "HEAD").strip()
        base = item.get("before_last_commit") if replacing else item.get("at_last_commit")
        first = not base
        before = base or dict.fromkeys(KINDS, 0)
        spent = {kind: max(0, now[kind] - int(before.get(kind, 0))) for kind in KINDS}
        if any(spent.values()):
            line = "Agent-Tokens: " + ", ".join(
                f"{label} {_short(spent[kind])}" for kind, label in
                (("output", "output"), ("input", "new input"), ("cache_read", "cache read"),
                 ("cache_write", "cache write"))) + (
                " (this session so far: its first commit)" if first else " (since this session's previous commit)")
            lines.append(line)
            item["pending"] = {"line": line, "totals": now, "base": base, "at": time.time()}
        _store(root, item)
    return lines


_TRAILER = re.compile(r"^[A-Za-z][A-Za-z0-9-]*: \S")


def add_trailers(message_file: Path, root: Path, env: Mapping[str, str], amend: bool = False) -> list[str]:
    """Written directly, not through `git interpret-trailers`: git matches trailer keys
    by prefix, so `Agent-Tokens` would replace `Agent`. Ours replace only themselves."""
    lines = trailers(root, env, amend)
    if not lines:
        return lines
    body = message_file.read_text(encoding="utf-8").splitlines()
    body = [line for line in body if not line.startswith(("Agent: ", "Agent-Tokens: "))]
    # Git's own comment block, when the message came from an editor, stays last.
    end = len(body)
    while end > 0 and (body[end - 1].startswith("#") or not body[end - 1].strip()):
        end -= 1
    head, tail = body[:end], body[end:]
    # A trailer block is a paragraph after the subject: `docs: notes` alone is a subject.
    if head and not ("" in head and _TRAILER.match(head[-1])):
        head.append("")
    message_file.write_text("\n".join([*head, *lines, *tail]) + "\n", encoding="utf-8")
    return lines


def main(argv: Optional[list[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                               check=False).stdout.strip() or ".")
    amend = "--amend" in args
    args = [arg for arg in args if arg != "--amend"]
    if len(args) == 2 and args[0] == "trailers":
        try:
            add_trailers(Path(args[1]), root, os.environ, amend)
        except Exception:  # fail-open: a commit is never blocked by its own bookkeeping
            pass
        return 0
    if args == ["report"]:
        sessions = load(root).get("sessions") or {}
        if not sessions:
            print("no coding-agent session recorded for this repository")
            return 0
        for item in sessions.values():
            totals = item.get("totals") or {}
            print(f"session transcript: {item.get('transcript')}")
            print("  spent: " + ", ".join(f"{kind.replace('_', ' ')} {_short(int(totals.get(kind, 0)))}"
                                          for kind in KINDS))
            print(f"  context each turn re-reads now: {_short(int(item.get('context') or 0))}")
        return 0
    print(__doc__.split("\n\n", 3)[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
