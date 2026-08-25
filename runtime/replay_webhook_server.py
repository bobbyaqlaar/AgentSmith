"""
runtime/replay_webhook_server.py — reference HTTP receiver for the Ops
Portal's "Replay with edits" DLQ action.

Why this exists: the Ops Portal (Next.js) has no Temporal client and
never will — runtime/dead_letter.py's replay_handler is deliberately
engine-agnostic, and the portal is meant to stay backend/orchestrator-
agnostic too (a tenant could run Celery, not Temporal). So when a human
edits a failing payload in the portal's DLQ view and clicks Replay, the
portal can't signal a live workflow directly — it POSTs the edit to
THIS tenant-run receiver instead, which DOES have a Temporal client
(it runs alongside the worker) and calls DeadLetterQueue.replay() for real.

This also keeps HITL routing tenant-specific by construction: each tenant
configures their OWN replay_webhook_url (synced from
.agenticframework/tenant.yaml, see OPERATIONS.md), so a human-in-the-loop
fix for tenant A's DLQ entry is delivered to tenant A's own
receiver/team — never a shared, cross-tenant endpoint.

This is a PATTERN, not a hardened production server — it's deliberately
built on the stdlib (http.server) so it has no new dependency beyond
what's already in requirements.txt, the same "reference, not
prescription" posture as base_workflow.py and worker.py. Tenants are
expected to copy/adapt this into their actual web framework (FastAPI,
Flask, etc.) — see worker.py's TENANT_WORKER_MODULE for the equivalent
pattern on the worker side.

Required env vars:
  DATABASE_URL              — same Postgres the worker's DeadLetterQueue uses
  REPLAY_WEBHOOK_SECRET      — shared secret; must match what's configured
                               in the portal for this tenant (sent back via
                               .agenticframework/tenant.yaml -> sync, see
                               OPERATIONS.md "Wire your platform")
  TEMPORAL_ADDRESS           — e.g. "localhost:7233" (default if unset)

Run: python3 replay_webhook_server.py [port, default 8090]
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# The framework ROOT (not runtime/ itself), so the imports inside _replay
# resolve as proper `runtime.X` package members. At module scope, ONCE: this
# ran inside the request handler, so every replay prepended another copy and
# sys.path grew for the life of the process.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.dead_letter import AlreadyResolvedError

logger = logging.getLogger(__name__)

# A replay body is a task id and an edited payload — kilobytes. The handler
# used to trust Content-Length and read exactly that many bytes, so any caller
# able to reach the port could declare a gigabyte and have it allocated. This
# receiver is a reference, and a reference that models an unbounded read is the
# version a tenant copies into production.
MAX_BODY_BYTES = 1 * 1024 * 1024


def _verify_signature(secret: str, body: bytes, signature_header: str) -> bool:
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = signature_header[len("sha256=") :]
    return hmac.compare_digest(expected, provided)


class ReplayWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (http.server's required method name)
        if self.path != "/replay":
            self._json(404, {"error": "not found"})
            return

        secret = os.environ.get("REPLAY_WEBHOOK_SECRET", "")
        if not secret:
            logger.error("REPLAY_WEBHOOK_SECRET not set — refusing all requests")
            self._json(503, {"error": "REPLAY_WEBHOOK_SECRET is not configured"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            # A non-numeric Content-Length used to raise out of do_POST, which
            # http.server answers with a traceback and a dropped connection
            # rather than a status a caller can act on.
            self._json(400, {"error": "invalid Content-Length"})
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(413, {"error": f"body must be 0..{MAX_BODY_BYTES} bytes"})
            return
        body = self.rfile.read(length)
        signature = self.headers.get("X-Replay-Signature", "")
        if not _verify_signature(secret, body, signature):
            self._json(401, {"error": "invalid signature"})
            return

        try:
            data = json.loads(body)
            task_id = data["taskId"]
            payload = data["payload"]
        except (json.JSONDecodeError, KeyError) as exc:
            self._json(400, {"error": f"bad request: {exc}"})
            return

        try:
            self._replay(task_id, payload)
        except KeyError:
            # No such entry. Distinct from the case below, which is why
            # dead_letter.py raises two different exceptions for them.
            self._json(404, {"error": f"no DLQ entry with task_id {task_id}"})
            return
        except AlreadyResolvedError as exc:
            # 409, not 500: nothing failed. The entry was already replayed or
            # discarded, and the operator needs to know that rather than see
            # "replay failed" for a replay that already happened.
            logger.info("Replay refused for task_id=%s: %s", task_id, exc)
            self._json(409, {"error": str(exc)})
            return
        except Exception as exc:
            logger.exception("Replay failed for task_id=%s", task_id)
            self._json(500, {"error": str(exc)})
            return

        self._json(200, {"ok": True})

    def _json(self, status: int, body: dict) -> None:
        """One place that writes a response, so every path sets a content type.

        Every branch above hand-rolled send_response/end_headers/write, and the
        error paths wrote a JSON body without ever declaring one — the portal
        parses these with `resp.json()`.
        """
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _replay(self, task_id: str, payload: dict) -> None:
        from runtime.dead_letter import DeadLetterQueue
        from runtime.temporal_replay import make_temporal_replay_handler

        async def _connect():
            # runtime/temporal_client.connect owns the address default, the
            # TEMPORAL_TLS parsing and this bounded timeout. The timeout
            # reasoning originated here — an unreachable server otherwise hangs
            # for the OS TCP timeout, often 2+ minutes, and reads as "the
            # portal is stuck" rather than "Temporal is down" — and the other
            # six call sites never inherited it.
            from runtime.temporal_client import connect

            return await connect()

        client = asyncio.run(_connect())
        dlq = DeadLetterQueue(replay_handler=make_temporal_replay_handler(client))
        dlq.replay(task_id, override_payload=payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        logger.info("%s - %s", self.address_string(), format % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    server = ThreadingHTTPServer(("0.0.0.0", port), ReplayWebhookHandler)
    logger.info("replay_webhook_server listening on :%d (POST /replay)", port)
    server.serve_forever()


if __name__ == "__main__":
    main()
