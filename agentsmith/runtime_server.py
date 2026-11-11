"""agentsmith/runtime_server.py — the compliance guards over localhost, for an
application not written in Python (contract/runtime/v1/protocol.md).

One implementation of the guards, so a TypeScript or Go application gets the same
refusals as a Python one. Run beside the application:

    AGENTSMITH_RUNTIME_TOKEN=... agentsmith runtime serve

It binds to loopback only and refuses a request without the token. Standard library
only, as `replay_webhook_server.py` is. A non-2xx answer means the application must
not act.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hmac
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional

from agentsmith import compliance
from agentsmith.llm_gateway import BudgetExceededError
from agentsmith.moderation import ModerationBlockedError
from agentsmith.prompt_guard import PromptGuardBlockedError

logger = logging.getLogger(__name__)

TOKEN_ENV = "AGENTSMITH_RUNTIME_TOKEN"
HOST = "127.0.0.1"
MAX_BODY_BYTES = 2 * 1024 * 1024
FORWARD_EVERY_SECONDS = 15
# Written by the framework itself, so an application cannot forge one.
RESERVED_KINDS = compliance.FRAMEWORK_KINDS


class BadRequest(ValueError):
    pass


def _text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BadRequest(f"{key} is required")
    return value


_gateways: dict[str, Any] = {}
_gateways_lock = threading.Lock()


def _gateway(tenant: str) -> Any:
    """One per app: an in-process budget lives on it, so one per request would never add up."""
    from agentsmith.llm_gateway import LLMGateway

    with _gateways_lock:
        if tenant not in _gateways:
            _gateways[tenant] = LLMGateway(tenant_id=tenant)
        return _gateways[tenant]


def _complete(tenant: str, body: dict[str, Any]) -> dict[str, Any]:
    result = asyncio.run(
        _gateway(tenant).complete(
            body.get("prompt") or _text(body, "prompt"),
            model_hint=str(body.get("model_hint") or "developer"),
            workflow_id=body.get("workflow_id"),
            max_tokens=int(body.get("max_tokens") or 4096),
            temperature=float(body.get("temperature", 0.2) or 0.0),
            data_class=_text(body, "data_class"),
            user_id=body.get("user_id"),
        )
    )
    return dataclasses.asdict(result)


def _running(tenant: str, body: dict[str, Any]) -> dict[str, Any]:
    compliance.require_running(tenant, body.get("workflow_id"))
    return {"running": True}


def _record(tenant: str, body: dict[str, Any]) -> dict[str, Any]:
    kind = _text(body, "kind")
    if kind in RESERVED_KINDS:
        raise BadRequest(f"{kind} is written by the framework")
    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise BadRequest("payload must be an object")
    return {"record_id": compliance.record(tenant, kind, payload)}


def _gate_request(tenant: str, body: dict[str, Any]) -> dict[str, Any]:
    workflow_id, gate_id = _text(body, "workflow_id"), _text(body, "gate_id")
    action, requested_by = _text(body, "action"), _text(body, "requested_by")
    compliance.require_running(tenant, workflow_id)
    record_id = compliance.record(
        tenant,
        "hitl_pending",
        {
            "gate_id": gate_id,
            "workflow_id": workflow_id,
            "action": action,
            "input": body.get("input"),
            "requested_by": requested_by,
            "input_sha256": compliance.payload_digest(body.get("input")),
        },
    )
    return {"record_id": record_id, "status": "pending"}


def _gate_status(tenant: str, body: dict[str, Any]) -> dict[str, Any]:
    decision = compliance.find_decision(tenant, _text(body, "workflow_id"), _text(body, "gate_id"))
    if decision is None:
        return {"status": "pending"}
    return {"status": "approved" if decision["approved"] else "rejected", "decision": decision}


def _gate_timeout(tenant: str, body: dict[str, Any]) -> dict[str, Any]:
    payload = {"workflow_id": _text(body, "workflow_id"), "gate_id": _text(body, "gate_id")}
    return {"record_id": compliance.record(tenant, "hitl_timeout", payload)}


ROUTES: dict[str, Callable[[str, dict[str, Any]], dict[str, Any]]] = {
    "/v1/complete": _complete,
    "/v1/running": _running,
    "/v1/record": _record,
    "/v1/gate/request": _gate_request,
    "/v1/gate/status": _gate_status,
    "/v1/gate/timeout": _gate_timeout,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "agentsmith-runtime/1"
    tenant = ""
    token = ""

    def _json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # http.server's required method name
        if self.path == "/healthz":
            self._json(200, {"ok": True, "profile": compliance.profile_active()})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # http.server's required method name
        given = self.headers.get("Authorization", "")
        if not hmac.compare_digest(given.encode(), f"Bearer {self.token}".encode()):
            self._json(401, {"error": "a valid bearer token is required"})
            return
        route = ROUTES.get(self.path)
        if route is None:
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(413, {"error": "the body is missing or too large"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise BadRequest("the body must be an object")
            self._json(200, route(self.tenant, body))
        except (BadRequest, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except compliance.ComplianceRefused as exc:
            self._json(403, {"refused": True, "obligation": exc.obligation, "reason": exc.reason})
        except (PromptGuardBlockedError, ModerationBlockedError, BudgetExceededError) as exc:
            self._json(422, {"blocked": True, "kind": type(exc).__name__, "reason": str(exc)})
        except compliance.ComplianceUnreadable as exc:
            self._json(503, {"refused": True, "reason": str(exc)})
        except Exception as exc:  # the caller must not act; the detail stays in this log
            logger.exception("runtime request failed")
            self._json(500, {"error": type(exc).__name__})

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s", format % args)


def _forward_forever(tenant: str, stop: threading.Event) -> None:
    while not stop.wait(FORWARD_EVERY_SECONDS):
        try:
            compliance.forward(tenant)
        except Exception as exc:  # fail-open: records wait in the database
            logger.warning("compliance records not forwarded yet: %s", type(exc).__name__)


def make_server(tenant: str, token: str, port: int) -> ThreadingHTTPServer:
    if not token:
        raise SystemExit(f"{TOKEN_ENV} is not set: this server refuses to run without one")
    handler = type("BoundHandler", (Handler,), {"tenant": tenant, "token": token})
    return ThreadingHTTPServer((HOST, port), handler)


def serve(tenant: str, port: int, token: Optional[str] = None) -> int:
    server = make_server(tenant, token if token is not None else os.environ.get(TOKEN_ENV, ""), port)
    stop = threading.Event()
    threading.Thread(target=_forward_forever, args=(tenant, stop), daemon=True).start()
    print(f"agentsmith runtime for {tenant} on http://{HOST}:{port} at {time.strftime('%H:%M:%S')}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # fail-open: Ctrl-C is how a person stops this server
        pass
    finally:
        stop.set()
        server.server_close()
    return 0
