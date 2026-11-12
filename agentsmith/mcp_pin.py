"""agentsmith/mcp_pin.py — pin a repository's MCP servers and their tool definitions.

A changed tool description is how a poisoned MCP server reaches an agent, so what a
repository trusted is written down and checked:

    agentsmith compliance mcp-pin      ask each server for its tools and record hashes
    agentsmith compliance mcp-verify   ask again, and fail on any difference

`static_problems` needs no server, so the compliance check can run it anywhere.

Servers are read from every file an agent or editor in this repository reads them
from (`SERVER_FILES`), and every page of `tools/list` is pinned. Servers an app
starts from its own code are not seen; the pass message says which files were read
(the 4.1.0 release review, R26).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SERVERS_FILE = ".mcp.json"
# Each file an agent or editor reads servers from, and the key it keeps them under.
# A server outside the root file is named `<file>#<name>`, so two files may reuse a name.
SERVER_FILES = ((SERVERS_FILE, "mcpServers"), (".cursor/mcp.json", "mcpServers"), (".vscode/mcp.json", "servers"),
                (".gemini/settings.json", "mcpServers"), (".codex/config.toml", "mcp_servers"))
# What a client shows a model about a tool, and so what a poisoned server could change.
TOOL_FIELDS = ("name", "title", "description", "inputSchema", "outputSchema", "annotations")
MAX_PAGES = 100
ALLOWLIST_FILE = ".agenticframework/mcp-allowlist.json"
TIMEOUT_SECONDS = 30
_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "agentsmith-mcp-pin", "version": "1"},
    },
}
_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def _list_request(number: int, cursor: Any) -> dict[str, Any]:
    request: dict[str, Any] = {"jsonrpc": "2.0", "id": number, "method": "tools/list"}
    if cursor is not None:
        request["params"] = {"cursor": cursor}
    return request


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _without_comments(text: str) -> str:
    """JSONC as editors write it (VS Code's mcp.json allows it): `//` and `/* */` comments
    and trailing commas removed, outside strings."""
    out, i, quoted = [], 0, False
    while i < len(text):
        ch = text[i]
        if quoted:
            out.append(ch)
            if ch == "\\":
                out.append(text[i + 1:i + 2])
                i += 1
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif text.startswith("//", i):
            i = text.find("\n", i)
            i = len(text) if i < 0 else i
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        else:
            out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _read(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".toml":
        import tomllib

        return tomllib.loads(text)
    return json.loads(_without_comments(text))


def _servers_and_problems(root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Every declared server, and every server file that could not be read. A file that
    cannot be read is named, never raised: one comment used to stop the whole check
    (the 4.1.0 review's second pass, P2-R11)."""
    found: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for rel, key in SERVER_FILES:
        path = root / rel
        if not path.is_file():
            continue
        try:
            document = _read(path)
        except Exception as exc:  # named in the result: a server we cannot read is not pinned
            problems.append(f"{rel} cannot be read ({type(exc).__name__}), so its MCP servers cannot be pinned")
            continue
        declared = document.get(key) if isinstance(document, dict) else None
        for name, server in declared.items() if isinstance(declared, dict) else []:
            if isinstance(server, dict):
                found[name if rel == SERVERS_FILE else f"{rel}#{name}"] = server
    return found, problems


def _servers(root: Path) -> dict[str, dict[str, Any]]:
    return _servers_and_problems(root)[0]


def scope_note(root: Path) -> str:
    """What the pin covers, for a pass message: the files read, and what is not seen."""
    read = [rel for rel, _key in SERVER_FILES if (root / rel).is_file()]
    where = ", ".join(read) if read else "none of " + ", ".join(rel for rel, _key in SERVER_FILES)
    count = len(_servers(root))
    return (f"{count} MCP server(s) are pinned (read: {where}; servers an app starts from its own code are not seen)"
            if count else f"no MCP server is declared (read: {where}; servers an app starts from its own code are "
                          "not seen)")


def _pages(ask: Any) -> list[dict[str, Any]]:
    """Every page of tools/list. `ask(number, cursor)` returns one reply's result."""
    tools: list[dict[str, Any]] = []
    cursor: Any = None
    for page in range(MAX_PAGES):
        result = ask(2 + page, cursor)
        tools += result.get("tools") or []
        cursor = result.get("nextCursor")
        if not cursor:
            return tools
    raise ValueError(f"the server gave more than {MAX_PAGES} pages of tools")


def _allowlist(root: Path) -> dict[str, Any]:
    path = root / ALLOWLIST_FILE
    return json.loads(path.read_text(encoding="utf-8")).get("servers", {}) if path.is_file() else {}


def config_hash(server: dict[str, Any]) -> str:
    """The server's identity. Environment names only: their values may be secrets."""
    return _digest(
        {
            "command": server.get("command"),
            "args": server.get("args", []),
            "url": server.get("url"),
            "env": sorted(server.get("env", {})),
        }
    )


def tool_hashes(tools: list[dict[str, Any]]) -> dict[str, str]:
    """A tool's whole definition as a model sees it: a changed `title` or `annotations`
    (`readOnlyHint`) passed before (P2-R11)."""
    return {t["name"]: _digest({k: t.get(k) for k in TOOL_FIELDS}) for t in tools}


def _read_reply(process: subprocess.Popen[bytes], wanted: int, deadline: float) -> dict[str, Any]:
    assert process.stdout is not None
    buffer = b""
    descriptor = process.stdout.fileno()
    while True:
        while b"\n" not in buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([descriptor], [], [], remaining)[0]:
                raise TimeoutError("the server did not answer")
            chunk = os.read(descriptor, 65536)
            if not chunk:
                raise ConnectionError("the server closed its output")
            buffer += chunk
        line, buffer = buffer.split(b"\n", 1)
        if line.strip():
            message = json.loads(line)
            if message.get("id") == wanted:
                return message


def _fetch_stdio(server: dict[str, Any]) -> list[dict[str, Any]]:
    env = {**os.environ, **{k: os.path.expandvars(str(v)) for k, v in server.get("env", {}).items()}}
    process = subprocess.Popen(
        [server["command"], *server.get("args", [])],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    assert process.stdin is not None
    deadline = time.monotonic() + TIMEOUT_SECONDS
    try:
        process.stdin.write((json.dumps(_INITIALIZE) + "\n").encode())
        process.stdin.flush()
        _read_reply(process, 1, deadline)
        process.stdin.write((json.dumps(_INITIALIZED) + "\n").encode())

        def ask(number: int, cursor: Any) -> dict[str, Any]:
            assert process.stdin is not None
            process.stdin.write((json.dumps(_list_request(number, cursor)) + "\n").encode())
            process.stdin.flush()
            return _read_reply(process, number, deadline)["result"]

        return _pages(ask)
    finally:
        process.kill()
        process.wait()


def _http_reply(response: Any) -> dict[str, Any]:
    if "text/event-stream" in response.headers.get("content-type", ""):
        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:])
        raise ValueError("no event in the server's reply")
    return response.json()


def _fetch_http(server: dict[str, Any]) -> list[dict[str, Any]]:
    import httpx

    headers = {"Accept": "application/json, text/event-stream", **server.get("headers", {})}
    with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
        first = client.post(server["url"], json=_INITIALIZE, headers=headers)
        first.raise_for_status()
        session = first.headers.get("mcp-session-id")
        if session:
            headers["Mcp-Session-Id"] = session
        client.post(server["url"], json=_INITIALIZED, headers=headers)

        def ask(number: int, cursor: Any) -> dict[str, Any]:
            reply = client.post(server["url"], json=_list_request(number, cursor), headers=headers)
            reply.raise_for_status()
            return _http_reply(reply)["result"]

        return _pages(ask)


def fetch_tools(server: dict[str, Any]) -> list[dict[str, Any]]:
    return _fetch_http(server) if server.get("url") else _fetch_stdio(server)


def static_problems(root: Path) -> list[str]:
    """What can be judged without running anything."""
    servers, problems = _servers_and_problems(root)
    pinned = _allowlist(root)
    for name, server in sorted(servers.items()):
        entry = pinned.get(name)
        if not isinstance(entry, dict):
            problems.append(f"MCP server {name} is not pinned: run `agentsmith compliance mcp-pin`")
        elif entry.get("config_sha256") != config_hash(server):
            problems.append(f"MCP server {name} changed since it was pinned")
        elif not entry.get("tools"):
            problems.append(f"MCP server {name} has no pinned tool definitions")
    return problems


def pin(root: Path) -> int:
    servers, unreadable = _servers_and_problems(root)
    if unreadable:
        for problem in unreadable:
            print(f"mcp-pin: {problem}", file=sys.stderr)
        return 1
    if not servers:
        print(f"mcp-pin: {scope_note(root)} — nothing to pin.")
        return 0
    entries: dict[str, Any] = {}
    for name, server in sorted(servers.items()):
        try:
            tools = tool_hashes(fetch_tools(server))
        except Exception as exc:  # named: a server that cannot be asked is not pinned
            print(f"mcp-pin: could not ask {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        entries[name] = {"config_sha256": config_hash(server), "tools": tools}
        print(f"mcp-pin: {name}: {len(tools)} tool(s)")
    target = root / ALLOWLIST_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"servers": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"mcp-pin: wrote {ALLOWLIST_FILE}. Review it before committing.")
    return 0


def verify(root: Path) -> int:
    problems = static_problems(root)
    pinned = _allowlist(root)
    for name, server in sorted(_servers(root).items()):
        if not isinstance(pinned.get(name), dict):
            continue
        try:
            current = tool_hashes(fetch_tools(server))
        except Exception as exc:  # a server that cannot be asked has not been verified
            problems.append(f"could not ask {name}: {type(exc).__name__}")
            continue
        expected = pinned[name].get("tools", {})
        for tool in sorted(set(current) | set(expected)):
            if current.get(tool) != expected.get(tool):
                problems.append(f"{name}.{tool} differs from what was pinned")
    for problem in problems:
        print(f"mcp-verify: {problem}", file=sys.stderr)
    print("mcp-verify: every server matches what was pinned." if not problems else "mcp-verify: failed.")
    return 1 if problems else 0
