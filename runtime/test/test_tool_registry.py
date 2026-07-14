from __future__ import annotations

from pathlib import Path

import pytest

from runtime.tool_registry import (
    ToolNotAllowedError,
    ToolRegistry,
    load_allowlist,
    tool,
)


def test_register_and_invoke_tool() -> None:
    registry = ToolRegistry()

    @tool(name="add", description="Add two numbers", registry=registry)
    def add(a: int, b: int) -> int:
        return a + b

    assert "add" in registry.names()
    schema = registry.get_schema("add")
    assert schema["name"] == "add"
    assert "a" in schema["parameters"]["properties"]
    assert registry.invoke("add", {"a": 2, "b": 3}) == 5


def test_allowlist_permits_listed_tool(tmp_path: Path) -> None:
    allow = tmp_path / "tool_allowlist.yaml"
    allow.write_text(
        "version: 1\ntools:\n  - name: echo\n    allowed: true\n",
        encoding="utf-8",
    )
    registry = ToolRegistry(allowlist_path=allow, strict=True)

    @tool(name="echo", description="Echo text", registry=registry)
    def echo(text: str) -> str:
        return text

    assert registry.invoke("echo", {"text": "hi"}) == "hi"


def test_allowlist_denies_unlisted_tool_in_strict(tmp_path: Path) -> None:
    allow = tmp_path / "tool_allowlist.yaml"
    allow.write_text(
        "version: 1\ntools:\n  - name: echo\n    allowed: true\n",
        encoding="utf-8",
    )
    registry = ToolRegistry(allowlist_path=allow, strict=True)

    @tool(name="secret_tool", description="Should be denied", registry=registry)
    def secret_tool() -> str:
        return "nope"

    with pytest.raises(ToolNotAllowedError):
        registry.invoke("secret_tool", {})


def test_load_allowlist_reads_template() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "fixtures" / "security" / "templates" / "tool_allowlist.yaml"
    names = load_allowlist(path)
    assert "example_tool" in names
