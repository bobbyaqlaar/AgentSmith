"""
scripts/gate_models.py — the governance registry and the records the process
gate reads beyond Problem / Approach / Levers (.agent-rfc/designs/
governance-enforcement.md, G1).

    Registry        templates/governance.json, compiled from
                    templates/agent-rules.yaml by generate-ide-config.py --registry
    ## Pillars       one answer per pillar the registry marks `design`
    ## Deviations    `none`, or entries that each resolve to an owner approval
    approvals.jsonl  written only by `agentsmith approve` (a terminal, never an agent)
    ## Sign-off      the docs/validation-checklist.md Step 4 block, complete

Pydantic V2 (pillar 7). Everything here validates on the receiving side and
returns named errors; process_gate.py decides what blocks.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "Approval",
    "Deviation",
    "Extends",
    "Pillar",
    "Records",
    "Registry",
    "Signoff",
    "ValidationError",
    "check_approvals",
    "check_pillars",
    "check_signoff",
    "parse_approvals",
    "parse_deviations",
]

APPROVALS_FILE = ".agenticframework/approvals.jsonl"
CheckKind = Literal["design", "review", "mechanical"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Pillar(_Frozen):
    id: int = Field(ge=1)
    name: str = Field(min_length=1)
    check: list[CheckKind] = Field(min_length=1)
    design_question: str | None = None
    rule: str | None = None


class Signoff(_Frozen):
    groups: list[str] = Field(min_length=1)
    fields: list[str] = Field(min_length=1)


class Records(_Frozen):
    design_sections: list[str] = Field(min_length=1)
    signoff: Signoff
    # What every IDE rule file tells an agent at the start of a change; the
    # gate does not read it, the generator renders it into six files.
    design_start: list[str] = Field(default_factory=list)


class Extends(_Frozen):
    """A tenant's own additions — `extends` in .agenticframework/process-gates.json.
    Kept apart from the registry so re-syncing the framework never overwrites it."""

    pillars: list[Pillar] = Field(default_factory=list)
    # Only keys something reads live here: a declared key nothing consumes is a
    # rule a tenant believes is in force (`declared-vs-enforced`).
    #   session_start  extra lines in every agent's session-start context (process_gate.py)
    #   rules_extra    repo notes appended to every generated rule file (generate-ide-config.py)
    #   test_command   what those files name as this repo's test command
    session_start: list[str] = Field(default_factory=list)
    rules_extra: list[str] = Field(default_factory=list)
    test_command: str | None = None


class Registry(_Frozen):
    model_config = ConfigDict(frozen=True, extra="ignore")  # "_about" and later sections

    version: str
    pillars: list[Pillar] = Field(min_length=1)
    records: Records

    def pillar_ids(self) -> set[int]:
        return {p.id for p in self.pillars}

    def merged(self, extends: Extends | None) -> Registry:
        if extends is None or not extends.pillars:
            return self
        clash = sorted(self.pillar_ids() & {p.id for p in extends.pillars})
        if clash:
            raise ValueError(
                "extends redefines " + ", ".join(f"P{i}" for i in clash)
                + " — a tenant may add pillars, not replace them"
            )
        return self.model_copy(update={"pillars": [*self.pillars, *extends.pillars]})


# ── ## Deviations ────────────────────────────────────────────────────────────

_DEVIATION_ID = r"(?:[A-Z]+-)?D\d+"
_APPROVAL_ID = r"A-[0-9a-f]{8}"


class Deviation(_Frozen):
    id: str
    text: str
    approval_id: str | None


def parse_deviations(section: str) -> tuple[list[Deviation], list[str]]:
    """-> (active deviations, errors). Struck-through entries are withdrawn."""
    stripped = section.strip()
    if re.match(r"^(?:-\s*)?none\b", stripped, re.I):
        return [], []
    if not stripped:
        return [], ["'## Deviations' is empty — write `none`, or one entry per deviation"]
    found: list[Deviation] = []
    errors: list[str] = []
    for line in stripped.splitlines():
        if re.match(r"^-\s*~~", line):
            continue
        entry = re.match(rf"^-\s*({_DEVIATION_ID})\b(.*)$", line)
        if not entry:
            continue
        ident, rest = entry.group(1), entry.group(2)
        approval = re.search(rf"approval:\s*({_APPROVAL_ID})\b", rest)
        if any(d.id == ident for d in found):
            errors.append(f"deviation {ident} is listed twice")
            continue
        if not approval:
            errors.append(
                f"deviation {ident} has no owner approval — the owner runs `agentsmith approve` in a terminal "
                "and the entry ends `approval: A-xxxxxxxx`"
            )
        found.append(Deviation(id=ident, text=rest.strip(" —-"), approval_id=approval.group(1) if approval else None))
    if not found and not errors:
        errors.append("'## Deviations' lists no entry — write `none`, or `- D1 — rule — what and why — approval: A-…`")
    return found, errors


# ── Approvals ────────────────────────────────────────────────────────────────


class Approval(_Frozen):
    id: str = Field(pattern=rf"^{_APPROVAL_ID}$")
    design: str = Field(min_length=1)
    deviation: str = Field(pattern=rf"^{_DEVIATION_ID}$")
    approver: str = Field(min_length=1)
    approved_at: datetime
    channel: Literal["tty"]
    statement: str = Field(min_length=1)


def parse_approvals(text: str | None) -> tuple[list[Approval], list[str]]:
    approvals: list[Approval] = []
    errors: list[str] = []
    for number, line in enumerate((text or "").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            approvals.append(Approval.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            detail = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else exc.msg
            errors.append(f"{APPROVALS_FILE} line {number} is not an approval record: {detail}")
    return approvals, errors


def check_approvals(deviations: list[Deviation], approvals: list[Approval], design: str) -> list[str]:
    by_id = {a.id: a for a in approvals}
    errors = []
    for deviation in deviations:
        if deviation.approval_id is None:
            continue  # parse_deviations already named it
        approval = by_id.get(deviation.approval_id)
        if approval is None:
            errors.append(
                f"deviation {deviation.id} cites {deviation.approval_id}, which is not in {APPROVALS_FILE} — "
                f"the owner records it with `agentsmith approve {design} {deviation.id}`"
            )
        elif approval.design != design or approval.deviation != deviation.id:
            errors.append(
                f"deviation {deviation.id} cites {approval.id}, which approves {approval.deviation} of "
                f"{approval.design}, not {deviation.id} of {design}"
            )
    return errors


# ── ## Pillars ───────────────────────────────────────────────────────────────

_ANSWER = re.compile(
    r"^-\s*(?P<ids>P\d+(?:\s*,\s*P?\d+)*)\s+(?P<verdict>\*\*[^*]+\*\*|\S+(?:\s+—)?)(?P<rest>.*)$"
)


def _detail(rest: str) -> str:
    return re.sub(r"^\s*[—–-]+\s*", "", rest).strip()


def check_pillars(section: str, registry: Registry, deviations: list[Deviation]) -> list[str]:
    errors: list[str] = []
    answered: set[int] = set()
    known = {p.id: p for p in registry.pillars}
    deviation_ids = {d.id for d in deviations}
    for line in section.splitlines():
        match = _ANSWER.match(line.strip())
        if not match:
            continue
        ids = [int(i) for i in re.findall(r"\d+", match.group("ids"))]
        verdict = match.group("verdict").strip("* ").rstrip(" —")
        detail = _detail(match.group("rest"))
        label = match.group("ids")
        for pid in ids:
            if pid not in known:
                errors.append(f"'## Pillars' answers P{pid}, which the registry does not define")
            answered.add(pid)
        deviation = re.match(rf"^deviation\s+({_DEVIATION_ID})$", verdict)
        if deviation:
            if deviation.group(1) not in deviation_ids:
                errors.append(f"{label} cites deviation {deviation.group(1)}, which '## Deviations' "
                              "does not list as active")
        elif verdict in ("applies", "n/a"):
            if not detail:
                errors.append(f"{label} {verdict} — the answer says why (`{label} {verdict} — how or why`)")
        elif verdict == "gap":
            if not re.search(r"\b[A-Z][A-Z0-9]*-\d+\b", detail):
                errors.append(f"{label} gap — a declared gap names its backlog id (`{label} gap — PB-123`)")
        else:
            errors.append(f"{label} '{verdict}' — each answer is applies, n/a, gap or deviation")
    for pillar in registry.pillars:
        if "design" in pillar.check and pillar.id not in answered:
            errors.append(f"'## Pillars' does not answer P{pillar.id} {pillar.name} — {pillar.design_question}")
    return errors


# ── ## Sign-off ──────────────────────────────────────────────────────────────


def _signoff_section(text: str) -> str | None:
    match = re.search(r"^## Sign-off\b.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1) if match else None


def check_signoff(text: str, registry: Registry) -> list[str]:
    spec = registry.records.signoff
    section = _signoff_section(text)
    if section is None:
        return ["records no '## Sign-off' block (docs/validation-checklist.md Step 4)"]
    errors = []
    for number, group in enumerate(spec.groups, start=1):
        line = re.search(rf"^\s*Group {number}\b.*$", section, re.M)
        if not line:
            errors.append(f"sign-off has no line for Group {number} · {group}")
            continue
        marked = re.findall(r"\[x\]\s*(checked|n/a|gap)\b\s*[:—–-]?\s*([^\[]*)", line.group(0), re.I)
        if len(marked) != 1:
            errors.append(f"sign-off Group {number} · {group} must mark exactly one of "
                          "checked / n/a / gap")
            continue
        verdict, reason = marked[0][0].lower(), marked[0][1].strip()
        if verdict != "checked" and (not reason or set(reason) <= set("_ ")):
            errors.append(f"sign-off Group {number} · {group} is {verdict} without saying why")
    for field in spec.fields:
        line = re.search(rf"^\s*{re.escape(field)}[^:\n]*:\s*(.*)$", section, re.M)
        if not line:
            errors.append(f"sign-off has no '{field}' line")
        elif not line.group(1).strip() or set(line.group(1).strip()) <= set("_ "):
            errors.append(f"sign-off '{field}' is blank")
    return errors
