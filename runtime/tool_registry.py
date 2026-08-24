"""
runtime/tool_registry.py — tool decorator + allowlist (SEC-TOOL-001).

Deny-by-default when strict=True and an allowlist is loaded.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, get_args, get_origin, get_type_hints

from runtime.security_paths import security_artefact_path

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
    return security_artefact_path("TOOL_ALLOWLIST_PATH", "tool_allowlist.yaml")


def _resolved_tenant_or_none() -> Optional[str]:
    """The tenant, or None. Never fatal — a tool registry with no tenant still
    works; its spans are simply attributed by the identity processor instead."""
    try:
        from runtime.tenancy import resolve_tenant_id

        return resolve_tenant_id()
    except Exception:
        return None


class ToolRegistry:
    def __init__(
        self,
        allowlist_path: Optional[Path] = None,
        strict: Optional[bool] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        # Stamped onto every tool span. Without it the `agent.tool.*` spans
        # G8 added were the only spans in the system with no `tenant.id`, so
        # filtering a shared Phoenix instance to one tenant showed that
        # tenant's steps and LLM calls but none of its tool calls — the
        # "every tool call streamed to Phoenix, attributed" claim held for
        # the span and failed for the attribution.
        #
        # Largely vestigial now: AgentIdentityProcessor stamps tenant.id onto
        # every span from the bound context, so a registry constructed without
        # one is still attributed. Kept as an override, resolved rather than
        # read from a single hardcoded variable — this was the sixth place in
        # the codebase reading the tenant name its own way.
        self._tenant_id = tenant_id or _resolved_tenant_or_none()
        self._tools: dict[str, ToolSpec] = {}
        path = allowlist_path if allowlist_path is not None else default_allowlist_path()
        self._allowlist: Optional[set[str]] = (
            load_allowlist(path) if path is not None and path.exists() else None
        )
        if strict is None:
            # security.tool_allowlist_strict in tenant.yaml, TOOL_ALLOWLIST_STRICT
            # overriding. Deny-by-default enforcement is tenant policy an auditor
            # reads; it was reachable only through an environment variable.
            from runtime.config import as_bool, resolve

            strict = as_bool(
                resolve(
                    "security.tool_allowlist_strict",
                    env_var="TOOL_ALLOWLIST_STRICT",
                    default=False,
                )
            )
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
                tenant_id=self._tenant_id,
            )
            raise
        record_tool_call(
            name,
            allowed=True,
            duration_ms=(time.perf_counter() - start) * 1000,
            tenant_id=self._tenant_id,
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
