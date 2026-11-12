"""agentsmith/compliance.py — the runtime side of a compliance profile.

A repository opts in with `.agenticframework/compliance.json` (written by
`agentsmith compliance enable`, contract/compliance/v1/protocol.md). Without that
file every function here reports "no profile" and nothing in the runtime changes.

On a profile, a function that cannot do its duty refuses: it raises
`ComplianceRefused`, naming the obligation. Only that function stops. The rest of
the application keeps running.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentsmith.version import app_commit

DECLARATION_FILE = ".agenticframework/compliance.json"
ATTESTATIONS_FILE = ".agenticframework/attestations.jsonl"
PATH_ENV = "AGENTSMITH_COMPLIANCE_FILE"
PROFILE_ENV = "COMPLIANCE_PROFILE"
PLACEHOLDER = "REPLACE_ME"
PROFILES = ("dubai-gov",)


class ComplianceRefused(RuntimeError):
    """A function refused because a compliance duty could not be met."""

    def __init__(self, obligation: str, reason: str) -> None:
        super().__init__(f"Refused by the compliance profile ({obligation}): {reason}")
        self.obligation = obligation
        self.reason = reason


class ComplianceUnreadable(RuntimeError):
    """The declaration exists and cannot be read. Never treated as no profile."""


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hosts: list[str] = Field(min_length=1, description="Hosts data may reach. `*.example.ae` matches subdomains.")
    sinks: dict[str, str] = Field(
        default_factory=dict, description="Each data store, by name, and the host it runs on."
    )


class Session(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idle_minutes: int = Field(gt=0)
    absolute_hours: int = Field(gt=0)


class Continuity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rpo_minutes: int = Field(gt=0)
    rto_minutes: int = Field(gt=0)
    drill_every_days: int = Field(gt=0)
    backup_host: str


class Agent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    accountable_owner: str = Field(min_length=1)


class Declaration(BaseModel):
    """`.agenticframework/compliance.json`."""

    model_config = ConfigDict(extra="forbid")
    profile: Literal["dubai-gov"]
    app_owner: str = Field(min_length=1)
    data_classes: list[str] = Field(min_length=1, description="From least to most sensitive.")
    classified_from: str = Field(description="The first class treated as classified.")
    boundary: Boundary
    session: Session
    retention_days: dict[str, int] = Field(description="Days kept, per store: audit, runs, traces.")
    continuity: Continuity
    languages: list[str] = Field(min_length=1)
    agents: list[Agent] = Field(default_factory=list)
    user_calls_per_minute: Optional[int] = Field(default=None, gt=0)
    runtime: Literal["python", "sidecar"] = Field(default="python", description="How the app reaches the guards.")

    def is_classified(self, data_class: str) -> bool:
        """True from `classified_from` upward. An unknown class is classified: the safe reading."""
        if data_class not in self.data_classes or self.classified_from not in self.data_classes:
            return True
        return self.data_classes.index(data_class) >= self.data_classes.index(self.classified_from)


def _find(root: Optional[Path]) -> Optional[Path]:
    explicit = os.environ.get(PATH_ENV, "").strip()
    if explicit:
        return Path(explicit)
    here = Path(root or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        candidate = folder / DECLARATION_FILE
        if candidate.is_file():
            return candidate
    # A deployment that says it is on a profile and has lost the file must not
    # read as having no profile: every duty would switch off without a sound.
    if os.environ.get(PROFILE_ENV, "").strip():
        raise ComplianceUnreadable(f"{PROFILE_ENV} is set and {DECLARATION_FILE} is not in this deployment")
    return None


def load_declaration(root: Optional[Path] = None) -> Optional[Declaration]:
    """The declaration, or None when this application has no profile.

    A file that exists and cannot be read raises: reading it as "no profile"
    would switch every duty off because of a typo.
    """
    path = _find(root)
    if path is None:
        return None
    try:
        return Declaration.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        raise ComplianceUnreadable(f"{path} cannot be read as a compliance declaration: {exc}") from exc


def profile_active(root: Optional[Path] = None) -> bool:
    return _find(root) is not None


# ── The catalogue and the records of who signed ──────────────────────────────


class Refs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    desc_isr: list[str] = Field(default_factory=list)
    nist_ai_rmf: list[str] = Field(default_factory=list)
    iso42001_theme: list[int] = Field(default_factory=list)
    uae_charter: list[str] = Field(default_factory=list)
    dubai_ethics: list[str] = Field(default_factory=list)
    owasp_llm: list[str] = Field(default_factory=list)
    uae_law: list[str] = Field(default_factory=list)


class Obligation(BaseModel):
    """One row of fixtures/compliance/catalogue.json."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str = Field(pattern=r"^OB-[A-Z0-9-]+$")
    title: str = Field(min_length=1)
    refs: Refs
    layer: Literal["provider", "app", "org"]
    kind: Literal["enforced", "verified", "attested"] = Field(alias="class")
    phases: list[Literal["design", "build", "deploy", "operate"]] = Field(min_length=1)
    mechanism: Optional[str] = None
    owner_role: str = Field(min_length=1)
    recurrence_days: Optional[int] = Field(default=None, gt=0)
    instructions: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    blocks: list[Literal["ci", "production"]] = Field(default_factory=list)
    profiles: list[str] = Field(min_length=1)


class Attestation(BaseModel):
    """One signature: appended to attestations.jsonl, or stored by the portal."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    obligation: str = Field(pattern=r"^OB-[A-Z0-9-]+$")
    actor: str = Field(min_length=1, max_length=320)
    role: str = Field(min_length=1, max_length=64)
    evidence: str = Field(min_length=1, max_length=2000)
    attested_at: str
    expires_at: Optional[str] = None
    note: str = Field(default="", max_length=2000)
    channel: Literal["tty", "portal"]


def parse_attestations(text: str) -> list[Attestation]:
    """Every record of an attestations.jsonl. A bad line raises: a file nobody can
    read must not read as nothing signed and then, one edit later, as all signed."""
    records = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            try:
                records.append(Attestation.model_validate_json(line))
            except ValidationError as exc:
                raise ComplianceUnreadable(f"{ATTESTATIONS_FILE} line {number} is not an attestation: {exc}") from exc
    return records


# ── The record comes first ───────────────────────────────────────────────────
#
# The owner's rule: the portal may be down as long as the record reaches the
# database. So a record goes to the database the worker already uses, and a
# forwarder drains it to the portal when the portal is up. If the write fails, the
# function that needed it refuses: no record, no action.

RECORD_KEY_ENV = "COMPLIANCE_RECORD_KEY"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS compliance_outbox (
        record_id    BIGSERIAL PRIMARY KEY,
        tenant_id    TEXT NOT NULL,
        kind         TEXT NOT NULL,
        payload      JSONB NOT NULL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        prev_hash    TEXT NOT NULL,
        record_hash  TEXT NOT NULL,
        forwarded_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_compliance_outbox_unsent ON compliance_outbox (record_id) "
    "WHERE forwarded_at IS NULL",
    """
    CREATE OR REPLACE FUNCTION compliance_outbox_guard() RETURNS trigger AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'compliance_outbox is append-only: DELETE is not permitted';
        END IF;
        IF (to_jsonb(NEW) - 'forwarded_at') IS DISTINCT FROM (to_jsonb(OLD) - 'forwarded_at') THEN
            RAISE EXCEPTION 'compliance_outbox is append-only: only forwarded_at may change';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS compliance_outbox_guard_row ON compliance_outbox",
    """
    CREATE TRIGGER compliance_outbox_guard_row BEFORE UPDATE OR DELETE ON compliance_outbox
        FOR EACH ROW EXECUTE FUNCTION compliance_outbox_guard()
    """,
    """
    CREATE TABLE IF NOT EXISTS compliance_stop (
        tenant_id  TEXT NOT NULL,
        scope      TEXT NOT NULL,
        reason     TEXT NOT NULL,
        set_by     TEXT NOT NULL,
        set_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, scope)
    )
    """,
]
GENESIS = "genesis"
APP_SCOPE = "*"
# Every kind the framework writes itself. The sidecar refuses them from an app, so an
# app cannot forge one (agentsmith/runtime_server.py); one list, so a new kind is
# reserved where it is born (the 4.1.0 release review, R21).
FRAMEWORK_KINDS = frozenset({"hitl_pending", "hitl_decision", "hitl_timeout", "stop_control", "model_call",
                             "model_result", "retention_purge"})


def _connect(dsn: Optional[str] = None):
    from agentsmith.pg_pool import connect, ensure_schema

    resolved = dsn or os.environ.get("DATABASE_URL", "")
    if not resolved:
        raise ComplianceRefused("OB-RECORD", "DATABASE_URL is not set, so no record can be written")
    ensure_schema(resolved, _DDL, key="compliance_outbox")
    return connect(resolved)


def _digest(key: str, tenant_id: str, kind: str, payload_json: str, prev_hash: str) -> str:
    message = "\n".join((tenant_id, kind, payload_json, prev_hash)).encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _record_key() -> str:
    key = os.environ.get(RECORD_KEY_ENV, "")
    if not key:
        raise ComplianceRefused("OB-RECORD", f"{RECORD_KEY_ENV} is not set, so no record can be signed")
    return key


def _append(cursor: Any, key: str, tenant_id: str, kind: str, payload: dict[str, Any]) -> int:
    """Append one record inside the caller's transaction, chained to the one before."""
    body = _canonical(payload)
    # One writer per tenant at a time, or two records would share a parent.
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (tenant_id,))
    cursor.execute(
        "SELECT record_hash FROM compliance_outbox WHERE tenant_id = %s ORDER BY record_id DESC LIMIT 1",
        (tenant_id,),
    )
    row = cursor.fetchone()
    previous = row[0] if row else GENESIS
    digest = _digest(key, tenant_id, kind, body, previous)
    cursor.execute(
        "INSERT INTO compliance_outbox (tenant_id, kind, payload, prev_hash, record_hash) "
        "VALUES (%s, %s, %s::jsonb, %s, %s) RETURNING record_id",
        (tenant_id, kind, body, previous, digest),
    )
    return int(cursor.fetchone()[0])


def record(tenant_id: str, kind: str, payload: dict[str, Any], *, dsn: Optional[str] = None) -> Optional[int]:
    """Write one record, chained to the one before it. Returns its id.

    Without a profile this does nothing and returns None. On a profile, a record
    that cannot be written raises `ComplianceRefused`: the caller must not act.
    """
    if not profile_active():
        return None
    key = _record_key()
    try:
        connection = _connect(dsn)
        try:
            with connection.cursor() as cursor:
                record_id = _append(cursor, key, tenant_id, kind, payload)
            connection.commit()
            return record_id
        finally:
            connection.close()
    except ComplianceRefused:
        raise
    except Exception as exc:
        raise ComplianceRefused("OB-RECORD", f"the record could not be written ({type(exc).__name__})") from exc


def _recorded_change(tenant_id: str, kind: str, payload: Any, change: Any, dsn: Optional[str]) -> Any:
    """Make a change and its record in one transaction: both, or neither (R13).
    `payload` may be a function of what `change` returns. Without a profile, the
    change alone."""
    key = _record_key() if profile_active() else ""
    try:
        connection = _connect(dsn)
        try:
            with connection.cursor() as cursor:
                result = change(cursor)
                if key:
                    _append(cursor, key, tenant_id, kind, payload(result) if callable(payload) else payload)
            connection.commit()
            return result
        finally:
            connection.close()
    except ComplianceRefused:
        raise
    except Exception as exc:
        if not key:
            raise
        raise ComplianceRefused("OB-RECORD", f"the change and its record could not be written "
                                             f"({type(exc).__name__}); neither was") from exc


def purge_runs(tenant_id: str, *, apply: bool = False, dsn: Optional[str] = None) -> int:
    """Run history older than the declared retention. Audit and outbox records are
    append-only and are not touched: they are exported, never purged here."""
    declaration = load_declaration()
    if declaration is None:
        raise ComplianceRefused("OB-SUBJECT", "this repository has no compliance profile")
    days = declaration.retention_days.get("runs")
    if not days:
        raise ComplianceRefused("OB-SUBJECT", "retention_days.runs is not declared")
    bounds = (tenant_id, days)

    def count(cursor: Any) -> int:
        cursor.execute(
            "SELECT count(*) FROM agent_runs WHERE tenant_id = %s AND started_at < now() - make_interval(days => %s)",
            bounds,
        )
        return int(cursor.fetchone()[0])

    if not apply:
        connection = _connect(dsn)
        try:
            with connection.cursor() as cursor:
                return count(cursor)
        finally:
            connection.close()

    def purge(cursor: Any) -> int:
        found = count(cursor)
        cursor.execute(
            "DELETE FROM agent_runs WHERE tenant_id = %s AND started_at < now() - make_interval(days => %s)", bounds
        )
        return found

    # The record is appended in the same transaction as the delete, so history is
    # never gone without a record saying so (the 4.1.0 release review, R13).
    return int(_recorded_change(tenant_id, "retention_purge",
                                lambda deleted: {"store": "runs", "days": days, "deleted": deleted}, purge, dsn))


def restore_drill(tenant_id: str, restored_dsn: str, root: Path, *, dsn: Optional[str] = None) -> list[str]:
    """Compare a restored database with the live one and record the result.
    The operator restores the backup first; this proves the copy is usable."""
    problems = [f"restored copy: {p}" for p in verify_chain(tenant_id, dsn=restored_dsn)]
    counts: list[int] = []
    for target in (dsn or os.environ.get("DATABASE_URL", ""), restored_dsn):
        connection = _connect(target)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM compliance_outbox WHERE tenant_id = %s", (tenant_id,))
                counts.append(int(cursor.fetchone()[0]))
        finally:
            connection.close()
    if counts[1] == 0:
        problems.append("the restored copy holds no records for this app")
    at = datetime.now(timezone.utc)
    folder = root / ".agenticframework" / "drills"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{at.strftime('%Y%m%dT%H%M%S')}.json").write_text(
        json.dumps(
            {
                "at": at.isoformat(),
                "result": "fail" if problems else "pass",
                "live_records": counts[0],
                "restored_records": counts[1],
                "problems": problems,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return problems


def verify_chain(tenant_id: str, *, dsn: Optional[str] = None) -> list[str]:
    """Every break in this tenant's chain: an altered record, or one removed."""
    key = os.environ.get(RECORD_KEY_ENV, "")
    if not key:
        return [f"{RECORD_KEY_ENV} is not set"]
    connection = _connect(dsn)
    problems: list[str] = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT record_id, kind, payload, prev_hash, record_hash FROM compliance_outbox "
                "WHERE tenant_id = %s ORDER BY record_id",
                (tenant_id,),
            )
            previous = GENESIS
            for record_id, kind, payload, prev_hash, record_hash in cursor.fetchall():
                if prev_hash != previous:
                    problems.append(f"record {record_id}: the chain is broken before it")
                if not hmac.compare_digest(_digest(key, tenant_id, kind, _canonical(payload), prev_hash), record_hash):
                    problems.append(f"record {record_id}: its content does not match its hash")
                previous = record_hash
    finally:
        connection.close()
    return problems


def forward(tenant_id: str, limit: int = 200, *, dsn: Optional[str] = None) -> tuple[int, str]:
    """Send unsent records to the portal, in order. -> (sent, why it stopped).
    A portal that is down costs nothing: the records wait."""
    from agentsmith import ops_contract

    connection = _connect(dsn)
    sent = 0
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT record_id, kind, payload, created_at, prev_hash, record_hash FROM compliance_outbox "
                "WHERE tenant_id = %s AND forwarded_at IS NULL ORDER BY record_id LIMIT %s",
                (tenant_id, limit),
            )
            rows = cursor.fetchall()
        for record_id, kind, payload, created_at, prev_hash, record_hash in rows:
            status = ops_contract.send(
                ops_contract.ComplianceRecordMessage(
                    record_id=record_id,
                    record_kind=kind,
                    payload=payload,
                    created_at=created_at.isoformat(),
                    prev_hash=prev_hash,
                    record_hash=record_hash,
                )
            )
            if status != 200:
                return sent, f"the portal answered {status}" if status else "the portal did not answer"
            with connection.cursor() as cursor:
                cursor.execute("UPDATE compliance_outbox SET forwarded_at = now() WHERE record_id = %s", (record_id,))
            connection.commit()
            sent += 1
    finally:
        connection.close()
    return sent, ""


def set_stop(tenant_id: str, scope: str, reason: str, actor: str, *, dsn: Optional[str] = None) -> None:
    """Stop a run (its workflow id) or the whole app (`*`), and record who did, in one
    transaction: a stop nobody can account for is not set."""

    def stop(cursor: Any) -> None:
        cursor.execute(
            "INSERT INTO compliance_stop (tenant_id, scope, reason, set_by) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, scope) DO UPDATE SET reason = EXCLUDED.reason, set_by = EXCLUDED.set_by, "
            "set_at = now()",
            (tenant_id, scope, reason, actor),
        )

    _recorded_change(tenant_id, "stop_control",
                     {"action": "stop", "scope": scope, "reason": reason, "actor": actor}, stop, dsn)


def clear_stop(tenant_id: str, scope: str, actor: str, *, dsn: Optional[str] = None) -> None:
    """Resume a run or the app, and record who did, in one transaction: a resume that
    cannot be recorded does not happen, and a record never says "resumed" for an app
    that is still stopped (P2-R15)."""

    def resume(cursor: Any) -> None:
        cursor.execute("DELETE FROM compliance_stop WHERE tenant_id = %s AND scope = %s", (tenant_id, scope))

    _recorded_change(tenant_id, "stop_control", {"action": "resume", "scope": scope, "actor": actor}, resume, dsn)


def require_running(tenant_id: str, workflow_id: Optional[str] = None, *, dsn: Optional[str] = None) -> None:
    """Raise if this app or this run has been stopped, or if nobody can tell."""
    if not profile_active():
        return
    try:
        connection = _connect(dsn)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT scope, reason FROM compliance_stop WHERE tenant_id = %s AND scope = ANY(%s)",
                    (tenant_id, [APP_SCOPE, workflow_id or APP_SCOPE]),
                )
                row = cursor.fetchone()
        finally:
            connection.close()
    except ComplianceRefused:
        raise
    except Exception as exc:
        raise ComplianceRefused("OB-STOP", f"the stop flag could not be read ({type(exc).__name__})") from exc
    if row:
        raise ComplianceRefused("OB-STOP", f"stopped ({row[0]}): {row[1]}")


class HumanDecision(BaseModel):
    """Who decided a human gate. Arrives signed through the replay webhook."""

    model_config = ConfigDict(extra="forbid")
    gate_id: str = Field(min_length=1, max_length=200)
    workflow_id: str = Field(min_length=1, max_length=200)
    approved: bool
    actor: str = Field(min_length=1, max_length=320)
    role: str = Field(min_length=1, max_length=64)
    rationale: str = Field(min_length=1, max_length=4000)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decided_at: str
    # The `hitl_pending` record the reviewer was shown. Two requests can show one input,
    # so the digest alone could not say which one a decision answers (the 4.1.0 review's
    # second pass, P2-R14).
    request_record_id: int = Field(ge=1)


def find_decision(
    tenant_id: str, workflow_id: str, gate_id: str, *, dsn: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """The named decision on one gate, for an application with no Temporal workflow to
    signal. Only a decision that names the latest request, and the digest of the input
    that request showed, answers it: a gate asked again is not answered by a decision on
    an earlier request, even one with the same input (P2-R14)."""
    gate = "tenant_id = %s AND kind = %s AND payload->>'workflow_id' = %s AND payload->>'gate_id' = %s"
    latest_request = (f"SELECT record_id, payload FROM compliance_outbox WHERE {gate} "  # nosec B608
                      "ORDER BY record_id DESC LIMIT 1")
    its_decision = (f"SELECT payload FROM compliance_outbox WHERE {gate} "  # nosec B608
                    "AND payload->>'request_record_id' = %s ORDER BY record_id DESC LIMIT 1")
    connection = _connect(dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute(latest_request, (tenant_id, "hitl_pending", workflow_id, gate_id))
            request = cursor.fetchone()
            if not request:
                return None
            cursor.execute(its_decision, (tenant_id, "hitl_decision", workflow_id, gate_id, str(request[0])))
            decision = cursor.fetchone()
    finally:
        connection.close()
    if not decision or decision[0].get("payload_sha256") != request[1].get("input_sha256"):
        return None
    return decision[0]


MARKING_SPEC = "agentsmith-ai-marking/1"


def ai_marking(text: str, model: str) -> dict[str, Any]:
    """Machine-readable provenance for one generated answer (EU AI Act Article 50(2)):
    what made it and a digest of it, signed when a key is set."""
    mark: dict[str, Any] = {
        "spec": MARKING_SPEC,
        "ai_generated": True,
        "generator": "agentsmith-gateway",
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
    key = os.environ.get(RECORD_KEY_ENV, "")
    if key:
        mark["signature"] = hmac.new(key.encode(), _canonical(mark).encode(), hashlib.sha256).hexdigest()
    return mark


def verify_marking(text: str, mark: dict[str, Any], require_signature: Optional[bool] = None) -> bool:
    """Is this mark about this text, and unaltered? Where marks are signed (a key is
    set) an unsigned mark proves nothing: anyone can recompute a digest (R19)."""
    if require_signature is None:
        require_signature = bool(os.environ.get(RECORD_KEY_ENV, ""))
    if mark.get("content_sha256") != hashlib.sha256(text.encode()).hexdigest():
        return False
    signature = mark.get("signature")
    if signature is None:
        return not require_signature
    unsigned = {k: v for k, v in mark.items() if k != "signature"}
    key = os.environ.get(RECORD_KEY_ENV, "")
    expected = hmac.new(key.encode(), _canonical(unsigned).encode(), hashlib.sha256).hexdigest()
    return bool(key) and hmac.compare_digest(expected, signature)


def marking_headers(mark: dict[str, Any]) -> dict[str, str]:
    """The mark as HTTP headers, for an application serving the answer over the web."""
    return {"X-AI-Generated": "true", "X-AI-Provenance": _canonical(mark)}


def payload_digest(payload: Any) -> str:
    """What a reviewer approved, so the record proves it was this and not something else."""
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def host_allowed(host: Optional[str], allowed: list[str]) -> bool:
    """`*.example.ae` matches subdomains; anything else matches exactly."""
    if not host:
        return False
    host = host.lower()
    for pattern in (p.lower() for p in allowed):
        if pattern.startswith("*.") and host.endswith(pattern[1:]):
            return True
        if host == pattern:
            return True
    return False


_LEAK_WORDS = 8
_LEAK_MIN_WORDS = 3  # shorter, and a match is a common phrase, not a leak
_user_calls: dict[str, deque[float]] = {}


def _check_user_limit(
    tenant_id: str, user_id: Optional[str], limit: Optional[int], now: Optional[float] = None
) -> None:
    """Calls per user per minute, per worker process. Tenant budgets are separate."""
    if not limit or not user_id:
        return
    moment = time.monotonic() if now is None else now
    calls = _user_calls.setdefault(f"{tenant_id}:{user_id}", deque())
    while calls and moment - calls[0] > 60:
        calls.popleft()
    if len(calls) >= limit:
        raise ComplianceRefused("OB-USER-LIMIT", f"more than {limit} calls in a minute for this user")
    calls.append(moment)


def leaks_system_prompt(messages: list, text: str) -> bool:
    """True if the answer repeats a run of words from a system message."""
    answer = " ".join(text.lower().split())
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            words = str(message.get("content", "")).lower().split()
            # A prompt shorter than the window is compared whole: the loop below never
            # ran for one, so a seven-word secret was never caught (R19).
            window = min(_LEAK_WORDS, len(words))
            if window < _LEAK_MIN_WORDS:
                continue
            for start in range(len(words) - window + 1):
                if " ".join(words[start : start + window]) in answer:
                    return True
    return False


def guard_output(tenant_id: str, workflow_id: Optional[str], messages: list, text: str, model: str) -> None:
    """After a model call on a profile: withhold a leak, then record what was asked and answered."""
    if leaks_system_prompt(messages, text):
        raise ComplianceRefused("OB-PROMPT-LEAK", "the answer repeats the system prompt")
    record(
        tenant_id,
        "model_result",
        {
            "workflow_id": workflow_id,
            "model": model,
            "prompt_sha256": payload_digest(messages),
            "output_sha256": payload_digest(text),
            "commit": app_commit() or "unknown",
        },
    )


def require_inside_boundary(base_url: str) -> None:
    """For the paths that do not go through the gateway: the developer pipeline and
    the eval judge. Without a profile, nothing. With one, the endpoint must be on
    this machine or inside the declared boundary, whatever keys are set."""
    declaration = load_declaration()
    if declaration is None:
        return
    host = urlparse(base_url).hostname
    if host in ("localhost", "127.0.0.1", "::1") or host_allowed(host, declaration.boundary.hosts):
        return
    raise ComplianceRefused("OB-RESIDENCY", f"endpoint {host!r} is outside the declared boundary")


def outbound_allowed(url: str) -> bool:
    """For best-effort sends (a webhook, a status report): skip rather than raise.
    Everything is allowed without a profile."""
    try:
        require_inside_boundary(url)
    except ComplianceRefused:
        return False
    return True


def guard_model_call(
    tenant_id: str,
    workflow_id: Optional[str],
    data_class: Optional[str],
    base_url: str,
    model: str,
    user_id: Optional[str] = None,
) -> None:
    """Before a model call on a profile: is the app running, and for classified
    data, is the endpoint inside the boundary and is the call on the record?
    A missing `data_class` reads as classified."""
    declaration = load_declaration()
    if declaration is None:
        return
    require_running(tenant_id, workflow_id)
    _check_user_limit(tenant_id, user_id, declaration.user_calls_per_minute)
    if not declaration.is_classified(data_class or ""):
        return
    host = urlparse(base_url).hostname
    if not host_allowed(host, declaration.boundary.hosts):
        raise ComplianceRefused(
            "OB-RESIDENCY", f"model endpoint {host!r} is outside the declared boundary for classified data"
        )
    record(
        tenant_id,
        "model_call",
        {"model": model, "host": host, "data_class": data_class or "unstated", "workflow_id": workflow_id},
    )
