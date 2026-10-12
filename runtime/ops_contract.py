"""
runtime/ops_contract.py — what a running tenant tells its portal, and what the
portal sends back (contract/ops/v1/protocol.md, .agent-rfc/designs/ops-contract.md).

    RunMessage, DeadLetterMessage, SettingsMessage   the three messages a tenant sends
    ReplayRequest                                    what the portal sends back
    send(message)                                    one message to the configured Ops ingest
    settings_from_tenant_yaml(root)                  the settings a repository declares

A wire contract: a tenant sends data and runs nothing of a provider's. The
receiver's Ops token alone decides whose data a message is — no message names a
tenant. Failure is open, and said: a worker never fails a request over its
report; it warns once per process and carries on.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

logger = logging.getLogger(__name__)

OPS_CONTRACT = 1
URL_ENV = "OPS_PORTAL_URL"
TOKEN_ENV = "OPS_PORTAL_TOKEN"
INGEST_PATH = "/api/ops/ingest"
# Text limits a receiver may enforce; the schema states them.
TEXT_LIMIT = 4000
ID_LIMIT = 200

RUN_STATUSES = ("running", "success", "degraded", "failed")
DEAD_LETTER_REASONS = ("validation_error", "tool_call_error", "hitl_timeout", "hitl_rejected", "infra_error")


class _Message(BaseModel):
    """Keys a receiver does not read are dropped by it, so a sender may add one."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_version: Literal[1] = Field(default=1, alias="schema")


RunStatus = Literal["running", "success", "degraded", "failed"]


class RunMessage(_Message):
    """One run's status. Usage is absent, never zero, when the provider reported none."""

    kind: Literal["run"] = "run"
    run_id: str = Field(min_length=1, max_length=ID_LIMIT)
    status: RunStatus
    workflow_id: Optional[str] = Field(default=None, max_length=ID_LIMIT)
    # W3C trace id; all-zero is the id the spec reserves as invalid.
    trace_id: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{32}$",
                                    json_schema_extra={"not": {"const": "0" * 32}})
    error_summary: Optional[str] = Field(default=None, max_length=TEXT_LIMIT)
    input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)
    cost_usd: Optional[float] = Field(default=None, ge=0)
    framework_version: Optional[str] = Field(default=None, max_length=64)

    @field_validator("trace_id")
    @classmethod
    def _not_the_invalid_trace(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and set(value) == {"0"}:
            raise ValueError("the all-zero trace id is the one W3C reserves as invalid")
        return value


class DeadLetterMessage(_Message):
    """A task that needs a human, or an engineer, before it can go on."""

    kind: Literal["dead_letter"] = "dead_letter"
    task_id: str = Field(min_length=1, max_length=ID_LIMIT)
    error: str = Field(min_length=1, max_length=TEXT_LIMIT)
    payload: Any
    # A category, open: DEAD_LETTER_REASONS are the ones AgentSmith's own callers
    # use, and a receiver shows one it does not know as it is.
    reason: Optional[str] = Field(default=None, min_length=1, max_length=64)
    workflow_id: Optional[str] = Field(default=None, max_length=ID_LIMIT)
    gate_id: Optional[str] = Field(default=None, max_length=ID_LIMIT)


class SettingsMessage(_Message):
    """What the tenant declares the portal should know. Never a secret: the
    replay key is the portal's to issue."""

    # The one key a receiver refuses rather than drops: a secret here would be
    # a tenant setting the key the portal signs its replays with.
    model_config = ConfigDict(json_schema_extra={"not": {"required": ["replay_webhook_secret"]}})

    kind: Literal["settings"] = "settings"
    budget_cap_usd: Optional[float] = Field(default=None, ge=0)
    replay_webhook_url: Optional[str] = Field(default=None, pattern=r"^https://", max_length=2000)

    @model_validator(mode="after")
    def _no_secret(self) -> "SettingsMessage":
        if "replay_webhook_secret" in (self.model_extra or {}):
            raise ValueError("a settings message carries no secret — the replay key is issued by the portal")
        return self


Message = Annotated[Union[RunMessage, DeadLetterMessage, SettingsMessage], Field(discriminator="kind")]
MESSAGE: TypeAdapter[Message] = TypeAdapter(Message)


class ReplayRequest(_Message):
    """What the portal POSTs to the tenant's replay webhook, signed with the
    application's replay key: `X-Replay-Timestamp`, and `X-Replay-Signature-V2:
    sha256=<hex HMAC-SHA256 over "<timestamp>.<body>">`. `taskId` keeps the name
    receivers already deployed read."""

    task_id: str = Field(min_length=1, max_length=ID_LIMIT, alias="taskId")
    payload: Any


# ── Sending ──────────────────────────────────────────────────────────────────

_warned: set[str] = set()


def _say_once(key: str, text: str) -> None:
    """A warning once per process, debug after: a worker reports on every call,
    and a portal that is down must not fill its log."""
    if key in _warned:
        logger.debug(text)
        return
    _warned.add(key)
    logger.warning(text)


def configured() -> bool:
    return bool(os.environ.get(URL_ENV, "").strip() and os.environ.get(TOKEN_ENV, "").strip())


def send(message: BaseModel, *, headers: Optional[dict[str, str]] = None) -> Optional[int]:
    """POST one message to the configured Ops ingest. Returns the status, or None
    when nothing was sent (not configured, or no answer). Never raises, never
    follows a redirect: a client that follows one copies the token to wherever
    the redirect points."""
    url, token = os.environ.get(URL_ENV, "").strip(), os.environ.get(TOKEN_ENV, "").strip()
    if not url or not token:
        return None
    try:
        import httpx

        response = httpx.post(
            url.rstrip("/") + INGEST_PATH,
            content=message.model_dump_json(by_alias=True, exclude_none=True),
            headers={**(headers or {}), "Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            follow_redirects=False,
            timeout=httpx.Timeout(connect=1.0, read=2.0, write=2.0, pool=1.0),
        )
    except Exception as exc:  # fail-open: the report never fails the work it reports on
        _say_once(f"down:{url}", f"Ops ingest at {url} did not answer ({type(exc).__name__}) — "
                                 "reports are not reaching the portal")
        return None
    status = response.status_code
    if 300 <= status < 400:
        _say_once("redirect", f"Ops ingest answered {status} — a redirect is never followed; nothing was stored")
    elif status == 401:
        _say_once("401", f"Ops ingest refused {TOKEN_ENV} (401) — issue an Ops token for this app in the portal")
    elif status >= 400:
        _say_once(f"{status}", f"Ops ingest refused a {getattr(message, 'kind', 'message')} message ({status})")
    return status


# ── What a repository declares ──────────────────────────────────────────────


def settings_from_tenant_yaml(root: Path) -> tuple[SettingsMessage, list[str]]:
    """The settings `.agenticframework/tenant.yaml` declares, and what was
    left out and why. `budget.monthly_usd_cap` is the key the gateway enforces;
    `gateway.budget_cap_usd` is its older name. A replay secret written there is
    never sent — it belongs in the worker's REPLAY_WEBHOOK_SECRET, issued by the
    portal."""
    import yaml

    notes: list[str] = []
    path = root / ".agenticframework" / "tenant.yaml"
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, yaml.YAMLError) as exc:
        return SettingsMessage(), [f"{path} does not parse ({exc}) — no settings sent"]
    doc = doc if isinstance(doc, dict) else {}
    budget = (doc.get("budget") or {}).get("monthly_usd_cap")
    if budget is None:
        budget = (doc.get("gateway") or {}).get("budget_cap_usd")
    hitl = doc.get("hitl") or {}
    if hitl.get("replay_webhook_secret"):
        notes.append("tenant.yaml declares hitl.replay_webhook_secret — a secret in a committed file. It is not "
                     "sent: remove it, issue a replay key in the portal, and set REPLAY_WEBHOOK_SECRET on the worker")
    url = hitl.get("replay_webhook_url")
    fields: dict[str, Any] = {}
    if isinstance(budget, (int, float)) and not isinstance(budget, bool):
        fields["budget_cap_usd"] = float(budget)
    elif budget is not None:
        notes.append(f"the budget cap {budget!r} is not a number — not sent")
    if isinstance(url, str) and url.startswith("https://"):
        fields["replay_webhook_url"] = url
    elif url:
        notes.append(f"hitl.replay_webhook_url {url!r} is not an https URL — not sent")
    return SettingsMessage(**fields), notes
