"""scripts/agent_tokens.py — what a coding agent's session spends, from its own transcript.

Claude Code writes every response's usage to the session transcript, and its hook
payloads name that transcript (`transcript_path`). The session-start and stop hooks
record it here; the commit hook then writes the agent and what the session spent
since its previous commit onto the commit (.agent-rfc/designs/coding-agent-tokens.md).

Only Claude Code is read: the other agents' payloads and shells are unconfirmed (gap 11).
No measurement is no trailer, never a zero. Counts only — no prompt or response text
leaves the transcript.

    agent_tokens.py trailers <message file>    add Agent / Agent-Tokens after the gate allowed
    agent_tokens.py report                     this repository's session, as the ledger has it
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
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


def _git_dir(root: Path) -> Optional[Path]:
    done = subprocess.run(["git", "-C", str(root), "rev-parse", "--absolute-git-dir"],
                          capture_output=True, text=True, check=False)
    return Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else None


def _ledger_path(root: Path) -> Optional[Path]:
    git_dir = _git_dir(root)
    return git_dir / LEDGER if git_dir else None


def load(root: Path) -> dict:
    path = _ledger_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def _save(root: Path, ledger: dict) -> None:
    path = _ledger_path(root)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def _fresh(ide: str, transcript: str) -> dict:
    return {"ide": ide, "transcript": transcript, "offset": 0, "recent_ids": [],
            "totals": dict.fromkeys(KINDS, 0), "context": 0, "at_last_commit": None, "noted": 0}


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
    recent = list(entry.get("recent_ids") or [])
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
            recent = [*recent, message_id][-_RECENT_IDS:]
        for kind, key in _USAGE_KEYS.items():
            value = usage.get(key)
            totals[kind] += value if isinstance(value, int) and value > 0 else 0
        context = sum(usage.get(key) or 0 for key in ("input_tokens", "cache_read_input_tokens",
                                                       "cache_creation_input_tokens")
                      if isinstance(usage.get(key), int))
    entry.update(offset=int(entry.get("offset") or 0) + end + 1, recent_ids=recent, totals=totals, context=context)
    return entry


def remember(root: Path, ide: str, payload: Mapping[str, Any]) -> Optional[dict]:
    """Record the session a hook was called from, and bring its totals up to date."""
    transcript = payload.get("transcript_path") if ide == "claude" else None
    if not isinstance(transcript, str) or not transcript:
        return None
    ledger = load(root)
    if ledger.get("transcript") != transcript:
        ledger = _fresh(ide, transcript)
    ledger = read_new(ledger)
    _save(root, ledger)
    return ledger


def context_note(root: Path, limit: Optional[int] = None) -> Optional[str]:
    """A word to the person when the context each turn re-reads has grown, once per step."""
    ledger = load(root)
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
    _save(root, ledger)
    return (f"This session's context is about {_short(context)} tokens, and every turn re-reads it. "
            "Commit what is done and start a fresh session for the next slice.")


def _short(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def agent(env: Mapping[str, str]) -> Optional[str]:
    """The coding agent whose shell made this commit — only the ones confirmed (gap 11)."""
    return "claude-code" if env.get("CLAUDECODE") else None


def trailers(root: Path, env: Mapping[str, str]) -> list[str]:
    """`Agent:` and `Agent-Tokens:` for the commit being made, updating the session's
    baseline. Empty when the commit was not made from a recognised agent."""
    name = agent(env)
    if name is None:
        return []
    lines = [f"Agent: {name}"]
    ledger = load(root)
    if ledger.get("transcript") and Path(ledger["transcript"]).is_file():
        ledger = read_new(ledger)
        now = {kind: int(ledger["totals"].get(kind, 0)) for kind in KINDS}
        before = ledger.get("at_last_commit") or dict.fromkeys(KINDS, 0)
        spent = {kind: max(0, now[kind] - int(before.get(kind, 0))) for kind in KINDS}
        if any(spent.values()):
            lines.append("Agent-Tokens: " + ", ".join(
                f"{label} {_short(spent[kind])}" for kind, label in
                (("output", "output"), ("input", "new input"), ("cache_read", "cache read"),
                 ("cache_write", "cache write"))) + " (since this session's previous commit)")
        ledger["at_last_commit"] = now
        _save(root, ledger)
    return lines


_TRAILER = re.compile(r"^[A-Za-z][A-Za-z0-9-]*: \S")


def add_trailers(message_file: Path, root: Path, env: Mapping[str, str]) -> list[str]:
    """Written directly, not through `git interpret-trailers`: git matches trailer keys
    by prefix, so `Agent-Tokens` would replace `Agent`. Ours replace only themselves."""
    lines = trailers(root, env)
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
    if len(args) == 2 and args[0] == "trailers":
        try:
            add_trailers(Path(args[1]), root, os.environ)
        except Exception:  # fail-open: a commit is never blocked by its own bookkeeping
            pass
        return 0
    if args == ["report"]:
        ledger = load(root)
        if not ledger:
            print("no coding-agent session recorded for this repository")
            return 0
        totals = ledger.get("totals") or {}
        print(f"session transcript: {ledger.get('transcript')}")
        print("spent: " + ", ".join(f"{kind.replace('_', ' ')} {_short(int(totals.get(kind, 0)))}" for kind in KINDS))
        print(f"context each turn re-reads now: {_short(int(ledger.get('context') or 0))}")
        return 0
    print(__doc__.split("\n\n", 3)[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
