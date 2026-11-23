"""scripts/agent_tokens.py — what a coding agent's session spends, from its own transcript.

Claude Code writes every response's usage to the session transcript, and its hook
payloads name that transcript (`transcript_path`). The session-start and stop hooks
record it here; the commit hook then writes the agent and what the session spent
since its previous commit onto the commit (.agent-rfc/designs/coding-agent-tokens.md).

Only Claude Code is read: the other agents' payloads and shells are unconfirmed (gap 11).
No measurement is no trailer, never a zero. Counts only — no prompt or response text
leaves the transcript.

One repository may hold several sessions at once, in several worktrees, so the ledger is
in the git directory every worktree shares and keeps one entry per transcript; a commit
is charged to the session whose shell made it (`CLAUDE_CODE_SESSION_ID`), and with
several sessions and no way to tell, it says only which agent. The baseline moves only
once the commit is seen to have landed, on any branch or worktree, so a commit a later
hook refused charges nothing, and `--amend` carries what the commit it replaces did.

    agent_tokens.py trailers [--amend] <message file>    add Agent / Agent-Tokens after the gate allowed
    agent_tokens.py report                     this repository's sessions, as the ledger has them
"""

from __future__ import annotations

import contextlib
import errno
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from collections import deque
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

try:
    import fcntl
except ImportError:  # Windows: the rename below still keeps the file whole
    fcntl = None  # type: ignore[assignment]

LEDGER = "agentsmith/agent-sessions.json"
# The ledger before 2026-11-22, in each checkout's own git directory: one session, or
# (from the 4.1.0 review) one entry per session. Code from before still writes it, so it
# is read, never written: a session it holds and the ledger lacks is taken from it.
LEGACY_LEDGER = "agentsmith/agent-tokens.json"
VERSION = 2
LOCK_SECONDS = 10.0
KINDS = ("output", "input", "cache_read", "cache_write")
_USAGE_KEYS = {"output": "output_tokens", "input": "input_tokens",
               "cache_read": "cache_read_input_tokens", "cache_write": "cache_creation_input_tokens"}
# One response spans several transcript lines that repeat its usage; they are adjacent,
# so a short memory of ids is enough to count each response once.
_RECENT_IDS = 64
NOTE_TOKENS_ENV = "AGENTSMITH_CONTEXT_NOTE_TOKENS"
NOTE_TOKENS = 150_000
NOTE_STEP = 50_000
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
MAX_SESSIONS = 32
_FORGET_AFTER = 14 * 86_400
# Claude Code writes a new session's transcript just after its SessionStart hook, so an
# entry not yet read is kept this long though its transcript is not there yet.
UNREAD_SECONDS = 24 * 60 * 60


def _paths(root: Path) -> Optional[tuple[Path, tuple[Path, ...]]]:
    """The ledger, in the git directory a checkout's worktrees share (the main
    checkout's `.git`), and the legacy ledgers to read beside it: the shared
    directory's and this checkout's own, which differ only in a linked worktree."""
    done = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-dir", "--git-common-dir"],
                          capture_output=True, text=True, check=False)
    lines = done.stdout.splitlines()
    if done.returncode != 0 or len(lines) != 2 or not all(line.strip() for line in lines):
        return None
    own, common = ((path if path.is_absolute() else Path(root) / path).resolve()
                   for path in (Path(line.strip()) for line in lines))
    return common / LEDGER, tuple(dict.fromkeys((common / LEGACY_LEDGER, own / LEGACY_LEDGER)))


# Above this no count is real, and a larger one overflows a float where it is shown.
_COUNT_LIMIT = 2 ** 63


def _int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _count(value: Any) -> bool:
    return _int(value) and value < _COUNT_LIMIT


def _finite(value: Any) -> bool:
    """A number a float can hold: an int too large for one makes `float()` raise."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _counts(value: Any) -> bool:
    return isinstance(value, dict) and all(_count(value.get(kind, 0)) for kind in KINDS)


def _whole(key: Any, entry: Any) -> bool:
    """An entry this code can use as it stands. Any other is left out and the session
    is read again from its transcript's start, rather than stopping every hook and commit."""
    if not (isinstance(key, str) and key and isinstance(entry, dict) and entry.get("transcript") == key
            and (entry.get("ide") is None or isinstance(entry.get("ide"), str))):
        return False
    pending = entry.get("pending")
    recent = entry.get("recent_ids")
    return (_int(entry.get("offset")) and isinstance(recent, list) and all(isinstance(i, str) for i in recent)
            and _counts(entry.get("totals"))
            and all(entry.get(field) is None or _counts(entry.get(field))
                    for field in ("at_last_commit", "before_last_commit"))
            and (entry.get("last_commit") is None or isinstance(entry.get("last_commit"), str))
            and (entry.get("session_id") is None or isinstance(entry.get("session_id"), str))
            and (pending is None or (isinstance(pending, dict) and isinstance(pending.get("line"), str)
                                     and _counts(pending.get("totals"))
                                     and (pending.get("base") is None or _counts(pending.get("base")))
                                     and _finite(pending.get("at"))))
            and _count(entry.get("context") or 0) and _count(entry.get("noted") or 0))


def _there(path: Any) -> bool:
    """Whether a transcript is a file. One this user cannot look at (another user's, in a
    repository shared between users: Claude Code keeps them in 0700 directories) is taken
    as there, not gone: its entry ages out by the fortnight rule instead. `Path.is_file`
    would raise for it before Python 3.13."""
    try:
        return stat.S_ISREG(os.stat(str(path)).st_mode)
    except (FileNotFoundError, NotADirectoryError, ValueError):
        return False
    except OSError:
        return True


def _seen(entry: Mapping[str, Any]) -> float:
    value = entry.get("seen")  # `_clean` keeps only a finite one
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError, RecursionError):
        data = {}
    return data if isinstance(data, dict) else {}


def _sessions(data: dict) -> dict:
    """The usable sessions of a ledger in any shape this code has written: one session,
    or `{"sessions": {transcript: entry}}`."""
    if isinstance(data.get("transcript"), str):
        data = {"sessions": {data["transcript"]: data}}
    sessions = data.get("sessions")
    return {key: _clean(entry)
            for key, entry in (sessions.items() if isinstance(sessions, dict) else ()) if _whole(key, entry)}


def _clean(entry: Mapping[str, Any]) -> dict:
    """The entry rebuilt from what this code writes, at every depth: a field, a count or
    a pending key it does not know is dropped, so nothing a ledger carries in can reach
    the write. (On Python 3.11–3.13 `json.dumps` with `indent` recurses once per level,
    and a value nested a thousand deep would fail every session's write.)"""
    def counts(value: Any) -> Optional[dict]:
        return None if value is None else {kind: value.get(kind, 0) for kind in KINDS}

    pending = entry.get("pending")
    clean = {field: entry[field] for field in _FIELDS if field in entry}
    clean.update(totals=counts(entry["totals"]), at_last_commit=counts(entry.get("at_last_commit")),
                 before_last_commit=counts(entry.get("before_last_commit")),
                 pending=None if pending is None else {"line": pending["line"], "totals": counts(pending["totals"]),
                                                       "base": counts(pending.get("base")), "at": pending["at"]})
    if "seen" in clean and not _finite(clean["seen"]):
        del clean["seen"]
    return clean


def _read(path: Path, legacy: tuple[Path, ...] = ()) -> Optional[dict]:
    """Every session the ledger holds, and any a legacy ledger holds that it lacks (the
    one seen last, and only one `_kept` would keep: the legacy file is never rewritten,
    so the write's rules are applied here). None for a ledger a later version wrote:
    this code neither reads nor rewrites it."""
    data = _json(path)
    version = data.get("version")
    if isinstance(version, int) and not isinstance(version, bool) and version > VERSION:
        return None
    sessions = _sessions(data)
    found: dict = {}
    now = time.time()
    for old in legacy:
        for key, entry in _sessions(_json(old)).items():
            if key not in sessions and _kept(entry, now) and _seen(entry) >= _seen(found.get(key, {})):
                found[key] = entry
    sessions.update(found)
    return {"version": VERSION, "sessions": sessions}


def _kept(entry: Mapping[str, Any], now: float) -> bool:
    """A session read once is dropped when its transcript goes; one never read may simply
    not be written yet. One unused for a fortnight is forgotten; one whose last use is
    unknown (a legacy entry, a malformed `seen`) is kept while its transcript is there."""
    age = now - _seen(entry) if _seen(entry) else None
    if age is not None and age >= _FORGET_AFTER:
        return False
    there = _there(entry.get("transcript"))
    return there or (entry.get("offset") == 0 and age is not None and age < UNREAD_SECONDS)


def _write(path: Path, ledger: dict, mode: int) -> None:
    """Whole or not at all: a temporary file renamed over the ledger, with `mode` (the
    lock file's, so the umask), not the private mode a temporary file starts with."""
    now = time.time()
    sessions = {key: entry for key, entry in ledger["sessions"].items() if _kept(entry, now)}
    kept = sorted(sessions.items(), key=lambda item: _seen(item[1]), reverse=True)[:MAX_SESSIONS]
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".agent-sessions.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(json.dumps({"version": VERSION, "sessions": dict(kept)}, indent=2) + "\n")
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def _locked(lock: Any) -> bool:
    """Take the lock, waiting at most LOCK_SECONDS. A filesystem without locks is used
    unlocked, as before; a lock held that long means skip the bookkeeping, never hang."""
    if fcntl is None:
        return True
    deadline = time.monotonic() + LOCK_SECONDS
    while True:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError as exc:
            if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES):
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


@contextlib.contextmanager
def _ledger(root: Path) -> Iterator[Optional[dict]]:
    """The ledger to read and change, saved on the way out if it changed, under one lock,
    so two sessions' hooks never drop each other's update. None outside a git repository,
    when the lock stays held, or when a later version wrote the ledger."""
    paths = _paths(root)
    if paths is None:
        yield None
        return
    path, legacy = paths
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a+", encoding="utf-8") as lock:
        if not _locked(lock):
            yield None
            return
        ledger = _read(path, legacy)
        if ledger is None:
            yield None
            return
        before = json.dumps(ledger, sort_keys=True)
        yield ledger
        if json.dumps(ledger, sort_keys=True) != before:
            _write(path, ledger, os.fstat(lock.fileno()).st_mode & 0o777)


def load(root: Path) -> dict:
    """The ledger: `{"version": 2, "sessions": {transcript path: entry}}`, with the legacy
    ledgers' sessions it lacks. Empty when no session is recorded."""
    paths = _paths(root)
    ledger = _read(*paths) if paths else None
    return ledger if ledger and ledger["sessions"] else {}


def _session_id(entry: Mapping[str, Any]) -> str:
    return str(entry.get("session_id") or Path(str(entry.get("transcript") or "")).stem)


def _select(sessions: Mapping[str, dict], transcript: Optional[str], env: Optional[Mapping[str, str]]) -> dict:
    """The named transcript, else the committing shell's session, else the only session
    there is. Empty when it cannot be told: a wrong session's count is worse than none."""
    if transcript is not None:
        return sessions.get(transcript) or {}
    wanted = (env or {}).get(SESSION_ENV)
    if wanted:
        return next((entry for entry in sessions.values() if _session_id(entry) == wanted), {})
    return next(iter(sessions.values())) if len(sessions) == 1 else {}


def entry(root: Path, transcript: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> dict:
    """One session's entry, chosen as `_select` does."""
    return _select(load(root).get("sessions") or {}, transcript, env)


def _stamp(entry: dict, sessions: Mapping[str, dict]) -> None:
    """Mark an entry as the newest: later than the clock and than every other entry, so
    the cap's order never rests on a tie or a clock step."""
    entry["seen"] = max(time.time(), max((_seen(other) for other in sessions.values()), default=0.0) + 1e-6)


def _latest(sessions: Mapping[str, dict]) -> dict:
    return max(sessions.values(), key=_seen, default={})


# The fields an entry keeps; anything else in a ledger is dropped as it is read.
_FIELDS = ("ide", "transcript", "session_id", "offset", "recent_ids", "totals", "context", "at_last_commit",
           "before_last_commit", "last_commit", "pending", "noted", "seen")


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
            if int(entry.get("offset") or 0) > os.fstat(handle.fileno()).st_size:
                # Past the end: the transcript was replaced or cut, or the offset is not one.
                # Read it again from its start, as a session this ledger has not seen.
                fresh = _fresh(str(entry.get("ide") or "claude"), entry["transcript"], _session_id(entry))
                entry.clear()
                entry.update(fresh)
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
        # A count no real response has (or a negative one) adds nothing, and a total
        # stops below the limit the ledger's reader holds it to.
        for kind, key in _USAGE_KEYS.items():
            value = usage.get(key)
            totals[kind] = min(_COUNT_LIMIT - 1, totals[kind] + (value if _count(value) else 0))
        context = min(_COUNT_LIMIT - 1, sum(usage[key] for key in ("input_tokens", "cache_read_input_tokens",
                                                                     "cache_creation_input_tokens")
                                            if _count(usage.get(key))))
    entry.update(offset=int(entry.get("offset") or 0) + end + 1, recent_ids=list(recent), totals=totals,
                 context=context)
    return entry


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else ""


def _settle(root: Path, item: dict) -> dict:
    """Move the baseline for a commit this session's hook prepared, once it is seen to
    have landed: a recent commit, on any branch or worktree, whose message carries the
    exact line written. One that never appeared was refused after the trailer step, and
    charged nothing. Every ref, because the hook that settles it may run in another
    worktree than the commit was made in."""
    pending = item.get("pending")
    if not isinstance(pending, dict):
        return item
    item["pending"] = None
    since = max(0, int(float(pending.get("at") or 0)) - 5)
    log = _git(root, "log", "--all", "-n", "50", f"--since={since}", "--format=%H%x00%B%x1e")
    landed = next((record.split("\0", 1)[0].strip() for record in log.split("\x1e")
                   if "\0" in record and pending.get("line") in record.split("\0", 1)[1].splitlines()), None)
    if landed:
        item.update(before_last_commit=pending.get("base"), at_last_commit=pending.get("totals"),
                    last_commit=landed)
    return item


def remember(root: Path, ide: str, payload: Mapping[str, Any]) -> Optional[dict]:
    """Record the session a hook was called from, and bring its totals up to date.
    Other sessions keep their own entries."""
    transcript = payload.get("transcript_path") if ide == "claude" else None
    if not isinstance(transcript, str) or not transcript:
        return None
    with _ledger(root) as ledger:
        if ledger is None:
            return None
        sessions = ledger["sessions"]
        item = sessions.get(transcript) or _fresh(ide, transcript, str(payload.get("session_id") or ""))
        item = read_new(_settle(root, item))
        _stamp(item, sessions)
        sessions[transcript] = item
    return item


def context_note(root: Path, limit: Optional[int] = None, transcript: Optional[str] = None) -> Optional[str]:
    """A word to the person when the context each turn re-reads has grown, once per step.
    `transcript` is the session asking; without it, the shell's session, or the one a
    hook read last."""
    try:
        limit = limit if limit is not None else int(os.environ.get(NOTE_TOKENS_ENV) or NOTE_TOKENS)
    except ValueError:
        limit = NOTE_TOKENS
    with _ledger(root) as ledger:
        if ledger is None:
            return None
        sessions = ledger["sessions"]
        item = (_select(sessions, transcript, os.environ) if transcript or os.environ.get(SESSION_ENV)
                else _latest(sessions))
        context = int(item.get("context") or 0)
        if not item or context < limit:
            return None
        step = limit + ((context - limit) // NOTE_STEP) * NOTE_STEP
        if int(item.get("noted") or 0) >= step:
            return None
        item["noted"] = step
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
    try:
        lines.extend(_spend(root, env, amend))
    except Exception:  # fail-open: a ledger that cannot be read, saved or understood costs the count, never who
        pass
    return lines


def _spend(root: Path, env: Mapping[str, str], amend: bool) -> list[str]:
    """The `Agent-Tokens:` line, if the committing session spent anything, with the
    commit recorded as pending. Nothing when that could not be saved."""
    with _ledger(root) as ledger:
        if ledger is None:
            return []
        item = _select(ledger["sessions"], None, env)
        if not item or not _there(item["transcript"]):
            return []
        item = read_new(_settle(root, item))
        now = {kind: int(item["totals"].get(kind, 0)) for kind in KINDS}
        # An amend replaces this session's last commit, so it carries what that one did.
        replacing = amend and item.get("last_commit") and item["last_commit"] == _git(root, "rev-parse", "HEAD").strip()
        base = item.get("before_last_commit") if replacing else item.get("at_last_commit")
        first = not base
        before = base or dict.fromkeys(KINDS, 0)
        spent = {kind: max(0, now[kind] - int(before.get(kind, 0))) for kind in KINDS}
        lines = []
        if any(spent.values()):
            line = "Agent-Tokens: " + ", ".join(
                f"{label} {_short(spent[kind])}" for kind, label in
                (("output", "output"), ("input", "new input"), ("cache_read", "cache read"),
                 ("cache_write", "cache write"))) + (
                " (this session so far: its first commit)" if first else " (since this session's previous commit)")
            lines.append(line)
            item["pending"] = {"line": line, "totals": now, "base": base, "at": time.time()}
        # A commit is use: the session must outlast the cap, or a legacy copy's older
        # baseline would come back and its spend be reported again.
        _stamp(item, ledger["sessions"])
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
        paths = _paths(root)
        if paths and _read(*paths) is None:
            print(f"{paths[0]} was written by a later AgentSmith release; this one does not read it")
            return 0
        sessions = sorted((load(root).get("sessions") or {}).values(), key=_seen, reverse=True)
        if not sessions:
            print("no coding-agent session recorded for this repository")
            return 0
        for item in sessions:
            totals = item.get("totals") or {}
            print(f"session transcript: {item.get('transcript')}")
            print("  spent: " + ", ".join(f"{kind.replace('_', ' ')} {_short(int(totals.get(kind, 0)))}"
                                          for kind in KINDS))
            print(f"  context each turn re-reads now: {_short(int(item.get('context') or 0))}")
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
