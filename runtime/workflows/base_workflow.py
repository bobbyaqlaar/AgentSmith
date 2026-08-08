"""
runtime/workflows/base_workflow.py — Reference Temporal workflow base class.

Demonstrates the durable-execution pattern described in SPECS.md §25:
  - Activities call runtime/llm_gateway.py (never cost_router.py)
  - HITL pause/resume via workflow signal, with a timeout that routes to the DLQ
  - A generalized recoverable-step pattern (run_with_recoverable_step) where
    ANY activity failure — not just an explicit "needs review" gate — parks
    the workflow alive and waits for a human to edit the failing payload in
    the Ops Portal and replay it, e.g. a tool call that hallucinated a field
    name ({"account_status": "active"} when the schema expects "status")
    gets corrected and resumed in place, instead of failing the request and
    dead-lettering a payload nothing can act on
  - All spans carry tenant.id, workflow.id, workflow.run_id

This is a PATTERN, not a deployable workflow. Tenant repos copy and adapt this
shape into their own workflow files — see examples/oil-price-agent/workflows/
for a concrete domain example built on top of it. Framework workflows are
never deployed directly as tenant production code (§25).

Requires: pip install temporalio
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Optional

try:
    from temporalio import activity, workflow
    from temporalio.common import RetryPolicy

    _HAS_TEMPORAL = True
except ImportError:
    _HAS_TEMPORAL = False
    RetryPolicy = None  # type: ignore

    class _Workflow:
        """No-op stand-in so this module is importable without temporalio installed."""

        def signal(self, fn=None, **_k):
            return fn if fn is not None else (lambda f: f)

    workflow = _Workflow()  # type: ignore
    activity = None  # type: ignore


HITL_SIGNAL_TIMEOUT = timedelta(hours=24)

# Bounds run_with_recoverable_step's retry loop — a human repeatedly
# submitting a fix that still fails (or fixing the wrong field) shouldn't
# keep a workflow parked forever; after this many failed attempts it
# dead-letters terminally even if a human is still actively trying.
RECOVERABLE_STEP_MAX_ATTEMPTS = 5


if _HAS_TEMPORAL:

    @activity.defn
    async def dlq_enqueue_activity(input: dict) -> dict:
        """Generic DLQ enqueue activity — wraps DeadLetterQueue.enqueue() so
        workflow code (which must stay deterministic/side-effect-free) never
        touches Postgres directly. Shared by run_with_recoverable_step;
        domain-specific dead-letter activities (e.g.
        examples/oil-price-agent/workflows/activities.py's
        dead_letter_activity) remain separate since they may carry
        domain-specific payload shaping the generic version shouldn't
        assume.
        """
        import inspect

        from runtime.dead_letter import DeadLetterQueue

        # Validate the SHAPE before touching Postgres. A caller passing the
        # legacy FLATTENED payload (`{**payload, "error": ...}`) to this generic
        # activity is a contract error, and it should not need a database
        # connection to surface — this path runs only when a gate has already
        # failed, so a second, unrelated failure there costs a debugging
        # session. The accepted names come from `enqueue`'s own signature
        # rather than being restated here, so they cannot drift.
        accepted = set(inspect.signature(DeadLetterQueue.enqueue).parameters) - {"self"}
        unexpected = sorted(set(input) - accepted)
        if unexpected:
            raise ValueError(
                f"dlq_enqueue_activity expects the dead_letter_envelope shape "
                f"({', '.join(sorted(accepted))}); got unexpected key(s) "
                f"{unexpected}. A tenant activity that expects the payload's "
                f"fields inline should be named in dead_letter_activity_name "
                f"instead of the generic dlq_enqueue_activity."
            )

        dlq = DeadLetterQueue()
        # `enqueue` takes exactly the keys `dead_letter_envelope` produces, so
        # unpacking keeps the field names in one module instead of restating
        # them at every activity boundary.
        entry = dlq.enqueue(**input)
        return {"task_id": entry.task_id}


    @activity.defn
    async def self_correct_payload_activity(input: dict) -> Any:
        """Activity boundary for LLM-driven payload correction.

        Kept outside workflow code because gateway calls are network I/O and
        therefore non-deterministic from Temporal's point of view.
        """
        from runtime.llm_gateway import LLMGateway
        from runtime.self_correction import propose_corrected_payload

        gateway = LLMGateway(tenant_id=input["tenant_id"])
        return await propose_corrected_payload(
            gateway,
            input["payload"],
            input["error"],
            model_hint=input.get("model_hint", "developer"),
        )


@dataclass
class AgentWorkflowInput:
    tenant_id: str
    task: str
    spec: str
    workflow_run_id: str


@dataclass
class AgentWorkflowResult:
    status: str  # "success" | "failed" | "dead_letter"
    plan: str = ""
    code: str = ""
    validation: str = ""


class BaseAgentWorkflow:
    """
    Reference three-node pattern: Architect -> Developer -> Validator, with an
    optional HITL pause before a destructive/low-confidence step.

    Subclass and override `activities()` to bind domain-specific activity
    functions (e.g. IngestionActivity, PredictionActivity, DecisionActivity
    for the oil-price example) while keeping the HITL/DLQ control flow here.
    """

    def __init__(self) -> None:
        self._hitl_approved: Optional[bool] = None
        self._gate_fixes: Dict[str, Any] = {}

    if _HAS_TEMPORAL:

        @workflow.signal
        def hitl_approved(self, approved: bool) -> None:
            """External signal fired by the Phoenix annotation -> Ops Portal bridge on HITL review."""
            self._hitl_approved = approved

        @workflow.signal
        def human_fix_payload(self, gate_id: str, fix: Any) -> None:
            """Fired by the Ops Portal's DLQ "Replay with edits" action
            (via the tenant's own replay-webhook receiver — see
            runtime/temporal_replay.py) when a human corrects a failing
            payload and clicks Replay: the CRM example's
            {"account_status": "active"} -> {"status": "active"} fix.
            Keyed by gate_id, not a single shared field, so multiple
            recoverable steps in one workflow (sequential or concurrent)
            don't clobber each other's pending fix.
            """
            self._gate_fixes[gate_id] = fix

    async def run_with_hitl_gate(
        self,
        gate_activity_name: Optional[str],
        gate_input: Any,
        resume_activity_name: str,
        resume_input: Any,
        dead_letter_activity_name: str,
        *,
        gate_result: Optional[dict] = None,
        tenant_id: Optional[str] = None,
        gate_id: str = "hitl-gate",
    ) -> AgentWorkflowResult:
        """
        Decide whether a step needs human review; if it does, wait on the
        `hitl_approved` signal up to HITL_SIGNAL_TIMEOUT. On timeout, route to
        the dead-letter activity instead of blocking the workflow forever.

        The `needs_hitl` decision comes from EITHER end of the gate — pass
        exactly one:

        - `gate_activity_name` — this method executes it and reads
          `needs_hitl` off the result. Use when the gate is a cheap, dedicated
          check the workflow has not run yet.
        - `gate_result` — a result the caller already has. Use when the
          preceding step ALREADY produced `needs_hitl`, which is the common
          shape: re-running that step here would (a) pay for its work twice
          and (b) let a non-deterministic re-run return `needs_hitl=False`,
          at which point this method would run the resume activity with no
          human approval at all. That is a silent HITL bypass on exactly the
          high-impact action the gate exists to protect, so the caller now
          hands over the decision it already made instead.

        `tenant_id` selects the dead-letter payload shape. With it, the
        timeout path emits the generic `dlq_enqueue_activity` envelope
        (`payload` / `error` / `tenant_id` / `reason` / `gate_id`) that
        `run_with_recoverable_step` uses. Without it, the legacy flattened
        `{**gate_input, "error": "hitl_timeout"}` shape is kept for tenants
        whose own dead-letter activity expects the payload's fields inline
        (see examples/oil-price-agent's `dead_letter_activity`). Passing
        `dead_letter_activity_name="dlq_enqueue_activity"` WITHOUT a
        `tenant_id` raises a ValueError inside that activity naming the
        expected envelope keys, since the flattened shape carries none of
        them.
        """
        if (gate_activity_name is None) == (gate_result is None):
            raise ValueError(
                "run_with_hitl_gate needs exactly one of gate_activity_name "
                "(run the gate here) or gate_result (the caller already has "
                "the needs_hitl decision) — got "
                + ("both" if gate_activity_name is not None else "neither")
            )

        if not _HAS_TEMPORAL:
            raise RuntimeError(
                "temporalio is not installed. Run: pip install temporalio. "
                "See SPECS.md §25 for the production runtime spec."
            )

        if gate_result is None:
            gate_result = await workflow.execute_activity(
                gate_activity_name,
                gate_input,
                start_to_close_timeout=timedelta(minutes=10),
            )

        if not gate_result.get("needs_hitl"):
            return await workflow.execute_activity(
                resume_activity_name,
                resume_input,
                start_to_close_timeout=timedelta(minutes=10),
            )

        try:
            await workflow.wait_condition(
                lambda: self._hitl_approved is not None,
                timeout=HITL_SIGNAL_TIMEOUT,
            )
        except TimeoutError:
            if tenant_id is None:
                dead_letter_input: Any = {**gate_input, "error": "hitl_timeout"}
            else:
                from runtime.dead_letter import dead_letter_envelope

                dead_letter_input = dead_letter_envelope(
                    payload=gate_input,
                    error="hitl_timeout",
                    tenant_id=tenant_id,
                    reason="hitl_timeout",
                    workflow_id=workflow.info().workflow_id,
                    gate_id=gate_id,
                )
            await workflow.execute_activity(
                dead_letter_activity_name,
                dead_letter_input,
                start_to_close_timeout=timedelta(minutes=5),
            )
            return AgentWorkflowResult(status="dead_letter")

        if not self._hitl_approved:
            return AgentWorkflowResult(status="failed")

        return await workflow.execute_activity(
            resume_activity_name,
            resume_input,
            start_to_close_timeout=timedelta(minutes=10),
        )

    async def run_with_self_correction(
        self,
        activity_name: str,
        payload: Any,
        tenant_id: str,
        gate_id: str,
        reason: str = "validation_error",
        timeout: timedelta = HITL_SIGNAL_TIMEOUT,
        max_attempts: int = RECOVERABLE_STEP_MAX_ATTEMPTS,
        max_self_correction_attempts: int = 1,
        model_hint: str = "developer",
    ) -> Any:
        """
        Run `activity_name` with `payload`. On failure, ask the gateway for a
        corrected JSON payload and retry before falling through to the
        existing human recoverable-step path.
        """
        if not _HAS_TEMPORAL:
            raise RuntimeError(
                "temporalio is not installed. Run: pip install temporalio. "
                "See SPECS.md §25 for the production runtime spec."
            )

        current_payload = payload
        last_error = ""

        try:
            return await workflow.execute_activity(
                activity_name,
                current_payload,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        except Exception as exc:
            last_error = str(exc)[:500]

        for _ in range(max_self_correction_attempts):
            current_payload = await workflow.execute_activity(
                self_correct_payload_activity,
                {
                    "payload": current_payload,
                    "error": last_error,
                    "tenant_id": tenant_id,
                    "model_hint": model_hint,
                },
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            try:
                return await workflow.execute_activity(
                    activity_name,
                    current_payload,
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            except Exception as exc:
                last_error = str(exc)[:500]

        return await self.run_with_recoverable_step(
            activity_name=activity_name,
            payload=current_payload,
            tenant_id=tenant_id,
            gate_id=gate_id,
            reason=reason,
            timeout=timeout,
            max_attempts=max_attempts,
        )

    async def run_with_recoverable_step(
        self,
        activity_name: str,
        payload: Any,
        tenant_id: str,
        gate_id: str,
        reason: str = "validation_error",
        timeout: timedelta = HITL_SIGNAL_TIMEOUT,
        max_attempts: int = RECOVERABLE_STEP_MAX_ATTEMPTS,
    ) -> Any:
        """
        Run `activity_name` with `payload`. On ANY activity failure — not
        just an explicit "needs review" gate, e.g. a tool call that
        hallucinated a field name the way the CRM example does
        ({"account_status": "active"} where the schema expects "status")
        — this workflow stays ALIVE (it does not return/terminate) and
        parks on a per-gate signal up to `timeout`, waiting for a human to
        fix the payload via the Ops Portal's editable DLQ view.

        On a human_fix_payload signal for this gate_id: retries
        `activity_name` with the corrected payload. If that also fails,
        loops (new DLQ entry, waits again) up to `max_attempts` before
        giving up and dead-lettering terminally — bounds how long a
        workflow stays parked if a human keeps submitting fixes that
        don't actually fix the problem.

        On timeout with no fix at all: dead-letters terminally, same
        fallback behavior as run_with_hitl_gate.
        """
        if not _HAS_TEMPORAL:
            raise RuntimeError(
                "temporalio is not installed. Run: pip install temporalio. "
                "See SPECS.md §25 for the production runtime spec."
            )

        workflow_id = workflow.info().workflow_id
        current_payload = payload

        for attempt in range(max_attempts):
            try:
                return await workflow.execute_activity(
                    activity_name,
                    current_payload,
                    start_to_close_timeout=timedelta(minutes=10),
                    # maximum_attempts=1: Temporal's default retry policy
                    # retries indefinitely (with backoff) until
                    # start_to_close_timeout — pointless and slow for a
                    # validation/tool-call error, which won't succeed on
                    # retry without a different payload. THIS method's own
                    # for-loop is the retry mechanism (only after a human
                    # supplies a corrected payload), not Temporal's.
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            except Exception as exc:
                error_text = str(exc)[:500]

            self._gate_fixes.pop(gate_id, None)
            # Same builder the HITL timeout path uses. Written out by hand here
            # until now, which is the duplication dead_letter_envelope exists to
            # remove: two producers restating the same six keys is exactly how
            # the HITL path drifted into a shape the consumer could not read.
            from runtime.dead_letter import dead_letter_envelope

            await workflow.execute_activity(
                dlq_enqueue_activity,
                dead_letter_envelope(
                    payload=current_payload,
                    error=error_text,
                    tenant_id=tenant_id,
                    reason=reason,
                    workflow_id=workflow_id,
                    gate_id=gate_id,
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )

            if attempt == max_attempts - 1:
                break

            try:
                await workflow.wait_condition(
                    lambda: gate_id in self._gate_fixes, timeout=timeout
                )
            except TimeoutError:
                return AgentWorkflowResult(status="dead_letter")

            current_payload = self._gate_fixes.pop(gate_id)

        return AgentWorkflowResult(status="dead_letter")
