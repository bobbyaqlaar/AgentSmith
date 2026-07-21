"""
runtime/tool_registry.py — tool decorator + allowlist (SEC-TOOL-001).

Deny-by-default when strict=True and an allowlist is loaded.
"""

from __future__ import annotations

import inspect
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, get_args, get_origin, get_type_hints

import yaml

_PYTHON_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


class ToolNotAllowedError(PermissionError):
    """Raised when invoking a tool that is not on the allowlist (strict mode)."""


class ToolNotFoundError(KeyError):
    """Raised when invoking an unregistered tool name."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    fn: Callable[..., Any]
    parameters: dict[str, Any]


def _json_type(annotation: Any) -> dict[str, Any]:
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        item = _json_type(args[0]) if args else {}
        return {"type": "array", "items": item or {}}
    if origin is Optional or (origin is getattr(__import__("typing"), "Union", None)):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _json_type(args[0])
    if annotation in _PYTHON_TO_JSON:
        return {"type": _PYTHON_TO_JSON[annotation]}
    if isinstance(annotation, type) and annotation in _PYTHON_TO_JSON:
        return {"type": _PYTHON_TO_JSON[annotation]}
    return {}


def _schema_from_fn(fn: Callable[..., Any]) -> dict[str, Any]:
    hints = get_type_hints(fn) if getattr(fn, "__annotations__", None) else {}
    props: dict[str, Any] = {}
    required: list[str] = []
    sig = inspect.signature(fn)
    for name, param in sig.parameters.items():
        if name in {"self", "cls"}:
            continue
        ann = hints.get(name, param.annotation)
        prop = _json_type(ann)
        props[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def load_allowlist(path: Path) -> set[str]:
    """Return tool names marked allowed:true from YAML allowlist."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tools = data.get("tools") or []
    allowed: set[str] = set()
    for row in tools:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if name and row.get("allowed", True):
            allowed.add(str(name))
    return allowed


def default_allowlist_path() -> Optional[Path]:
    env = os.environ.get("TOOL_ALLOWLIST_PATH", "").strip()
    if env:
        return Path(env)
    candidate = Path(".agent-rfc") / "security" / "tool_allowlist.yaml"
    if candidate.exists():
        return candidate
    return None


class ToolRegistry:
    def __init__(
        self,
        allowlist_path: Optional[Path] = None,
        strict: Optional[bool] = None,
    ) -> None:
        self._tools: dict[str, ToolSpec] = {}
        path = allowlist_path if allowlist_path is not None else default_allowlist_path()
        self._allowlist: Optional[set[str]] = (
            load_allowlist(path) if path is not None and path.exists() else None
        )
        if strict is None:
            strict = os.environ.get("TOOL_ALLOWLIST_STRICT", "").strip() == "1"
        self._strict = bool(strict)

    def register(
        self,
        fn: Callable[..., Any],
        *,
        name: str,
        description: str = "",
    ) -> Callable[..., Any]:
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        spec = ToolSpec(
            name=name,
            description=description,
            fn=fn,
            parameters=_schema_from_fn(fn),
        )
        self._tools[name] = spec
        return fn

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get_schema(self, name: str) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolNotFoundError(name)
        return {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        }

    def _assert_allowed(self, name: str) -> None:
        if not self._strict:
            return
        if self._allowlist is None:
            raise ToolNotAllowedError(
                f"strict allowlist enabled but no allowlist loaded; denying {name!r}"
            )
        if name not in self._allowlist:
            raise ToolNotAllowedError(f"tool not allowlisted: {name}")

    def invoke(self, name: str, args: dict[str, Any]) -> Any:
        # Every tool call annotates the active span with its name, allow/deny
        # outcome, duration and any error (TestbedFeedback-2026-07-21 G8) —
        # the "every tool call streamed to Phoenix" claim required this and
        # nothing delivered it. record_tool_call no-ops without OTel, so the
        # allow/deny path below is unchanged when tracing is off.
        import time

        from runtime.tracing import record_tool_call

        start = time.perf_counter()
        try:
            self._assert_allowed(name)
            spec = self._tools.get(name)
            if spec is None:
                raise ToolNotFoundError(name)
            result = spec.fn(**args)
        except Exception as exc:
            record_tool_call(
                name,
                allowed=not isinstance(exc, ToolNotAllowedError),
                duration_ms=(time.perf_counter() - start) * 1000,
                error=type(exc).__name__,
            )
            raise
        record_tool_call(
            name, allowed=True, duration_ms=(time.perf_counter() - start) * 1000
        )
        return result


_DEFAULT_REGISTRY = ToolRegistry(strict=False)


def tool(
    name: str,
    description: str = "",
    registry: Optional[ToolRegistry] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a function as an invocable tool."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        reg = registry if registry is not None else _DEFAULT_REGISTRY
        reg.register(fn, name=name, description=description)
        return fn

    return decorator
