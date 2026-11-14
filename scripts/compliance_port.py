#!/usr/bin/env python3
"""scripts/compliance_port.py — AgentSmith as a compliance provider
(contract/compliance/v1/protocol.md).

    check --stage ci|production   one result on stdout; the caller decides what it means
    status                        the same, for a person
    export [--out PATH]           write the checklist document
    sync                          exchange attestations with the portal
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Optional

FRAMEWORK = Path(__file__).resolve().parents[1]
for _entry in (str(FRAMEWORK), str(FRAMEWORK / "scripts")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from agentsmith import compliance as c  # noqa: E402

CATALOGUE = FRAMEWORK / "fixtures" / "compliance" / "catalogue.json"
CHECKLIST = "docs/compliance-checklist.md"
SYNC_PATH = "/api/compliance/sync"
SCHEMA = 1
DECLARATION_TEMPLATE = FRAMEWORK / "templates" / "compliance" / "dubai-gov" / "compliance.json"
PROVIDER_EVIDENCE = ("AgentSmith's own evidence: `scripts/compliance_port.py provider-evidence`, run by its "
                     "Self-Test and attached to each release")
# Provider obligations AgentSmith does not yet prove, named so the evidence step can
# publish them and still fail on anything new. Adding one is the owner's decision
# (2026-11-12, the 4.1.0 review's second pass, P2-R22); a gap that starts passing must
# leave this list, or the step fails.
KNOWN_PROVIDER_GAPS = {
    "OB-AUDIT-COVERAGE": "it cites a route file, not a test; a test that every sign-in and human action is "
                         "audited is open work (docs/PRODUCT_BACKLOG.md)",
}


def load_catalogue(path: Path = CATALOGUE) -> list[c.Obligation]:
    return [c.Obligation.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))]


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def expires(record: c.Attestation, recurrence_days: Optional[int]) -> Optional[datetime]:
    """When a signature stops counting. A recurring obligation's period comes from the
    catalogue: a later or missing `expires_at` does not stretch it (the 4.1.0 release
    review, R15)."""
    given = _parse(record.expires_at) if record.expires_at else None
    if not recurrence_days:
        return given
    due = _parse(record.attested_at) + timedelta(days=recurrence_days)
    return min(due, given) if given else due


def latest_valid(records: list[c.Attestation], obligation: str, now: datetime,
                 recurrence_days: Optional[int] = None) -> Optional[c.Attestation]:
    """The newest record for this obligation that is signed, not dated in the future,
    and not expired."""
    def live(record: c.Attestation) -> bool:
        if record.obligation != obligation or _parse(record.attested_at) > now + timedelta(minutes=5):
            return False
        until = expires(record, recurrence_days)
        return until is None or until > now

    found = [r for r in records if live(r)]
    return max(found, key=lambda r: _parse(r.attested_at)) if found else None


def _declared_path(document: dict[str, Any], dotted: str) -> Any:
    value: Any = document
    for part in dotted.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _has_placeholder(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_placeholder(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_placeholder(v) for v in value)
    return value == c.PLACEHOLDER


def _security_rows(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    """-> (control id → row, why it could not run)."""
    done = subprocess.run(
        [sys.executable, str(FRAMEWORK / "scripts" / "security_port.py"), "check"],
        input="{}",
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )
    try:
        return {row["id"]: row for row in json.loads(done.stdout)["controls"]}, ""
    except (ValueError, KeyError, TypeError):
        return {}, f"the security provider gave no answer (exit {done.returncode})"


def _not_run_by_ci(cited: str) -> str:
    """Why this file is not a test AgentSmith's CI runs, or "" when it is. A file that
    exists is not evidence; a test nothing runs passes while broken (the 4.1.0 release
    review, R23). Pytest collects `test_*.py` under the two test folders; the portal's
    tests run only when `npm test` or `npm run test:db` names them."""
    path = PurePosixPath(cited)
    pytest_folders = ("agentsmith/test", "scripts/test")
    if path.suffix == ".py" and path.name.startswith("test_") and str(path.parent) in pytest_folders:
        return ""
    if str(path.parent) == "portal/test" and path.name.endswith(".test.ts"):
        scripts = json.loads((FRAMEWORK / "portal" / "package.json").read_text(encoding="utf-8")).get("scripts", {})
        if any(f"test/{path.name}" in str(scripts.get(name, "")) for name in ("test", "test:db")):
            return ""
        return f"{cited} is in neither `npm test` nor `npm run test:db`, so CI never runs it"
    return f"{cited} is not a test CI runs, so it is not evidence"


def _judge_mechanism(
    root: Path,
    row: c.Obligation,
    declared: dict[str, Any],
    security: dict[str, dict[str, Any]],
    security_error: str,
    gate: dict[str, Any],
    own: bool,
) -> tuple[str, str]:
    mechanism = row.mechanism or ""
    if row.layer == "provider" and not own:
        if row.id in KNOWN_PROVIDER_GAPS:
            return "pending", f"AgentSmith does not yet prove this: {KNOWN_PROVIDER_GAPS[row.id]}"
        return "not_applicable", PROVIDER_EVIDENCE
    if mechanism.startswith("check:"):
        import compliance_checks

        check = compliance_checks.CHECKS.get(mechanism.split(":", 1)[1])
        if check is None:
            return "fail", f"mechanism {mechanism!r} is not one this provider knows"
        try:
            return check(root, declared)
        except Exception as exc:  # a check that could not run has not passed
            return "fail", f"{mechanism} could not run: {type(exc).__name__}: {exc}"
    if mechanism.startswith("release:"):
        cited = mechanism.split(":", 1)[1]
        if not (FRAMEWORK / cited).is_file():
            return "fail", f"{mechanism} does not exist"
        why = _not_run_by_ci(cited)
        return ("fail", why) if why else ("pass", f"{cited} runs in AgentSmith's own CI")
    if mechanism == "declaration:complete":
        return (
            ("fail", f"{c.DECLARATION_FILE} still holds {c.PLACEHOLDER}")
            if _has_placeholder(declared)
            else ("pass", "declared in full")
        )
    if mechanism.startswith("declaration:"):
        value = _declared_path(declared, mechanism.split(":", 1)[1])
        return ("pass", "declared") if value not in (None, "", [], {}) else ("fail", f"{mechanism} is not declared")
    if mechanism == "config:enforce":
        return (
            ("pass", "the profile is enforced")
            if gate.get("mode") == "enforce"
            else ("fail", "process-gates.json does not enforce the profile")
        )
    if mechanism.startswith("SEC-"):
        if security_error:
            return "fail", security_error
        found = security.get(mechanism)
        if found is None:
            return "fail", f"{mechanism} is not a control this provider checks"
        result = found["result"]
        if result == "pass":
            return "pass", found.get("message", "")
        if result == "not_applicable":
            return "not_applicable", found.get("message", "")
        return "fail", f"{mechanism}: {result}: {found.get('message', '')}"
    return "fail", f"mechanism {mechanism!r} is not one this provider knows"


def evaluate(
    root: Path,
    stage: str,
    now: datetime,
    records: list[c.Attestation],
    security: Optional[dict[str, dict[str, Any]]] = None,
    security_error: str = "",
    catalogue: Optional[list[c.Obligation]] = None,
) -> dict[str, Any]:
    """The verdict. Only rows that block this stage can fail it; the rest read `pending`."""
    declaration = c.load_declaration(root)
    if declaration is None:
        config_path = root / ".agenticframework" / "process-gates.json"
        try:
            enforced = json.loads(config_path.read_text(encoding="utf-8")).get("compliance", {}).get("mode")
        except (OSError, ValueError, AttributeError):
            enforced = None
        if enforced == "enforce":  # left by deleting a file, not on the record (R24)
            return {"schema": SCHEMA, "verdict": "fail", "rows": [], "counts": {},
                    "reason": "process-gates.json enforces a profile and .agenticframework/compliance.json is missing: "
                              "restore it, or leave the profile on the record (agentsmith approve)"}
        return {"schema": SCHEMA, "verdict": "no_profile", "reason": "no compliance.json", "rows": [], "counts": {}}
    declared = json.loads((root / c.DECLARATION_FILE).read_text(encoding="utf-8"))
    config_path = root / ".agenticframework" / "process-gates.json"
    gate = json.loads(config_path.read_text(encoding="utf-8")).get("compliance", {}) if config_path.is_file() else {}
    own = root.resolve() == FRAMEWORK.resolve()
    if security is None:
        security, security_error = _security_rows(root)
    rows = []
    for row in catalogue if catalogue is not None else load_catalogue():
        if declaration.profile not in row.profiles:
            continue
        signed = None
        if row.kind == "attested":
            signed = latest_valid(records, row.id, now, row.recurrence_days)
            result, message = (
                ("pass", f"signed by {signed.actor} ({signed.role})")
                if signed
                else ("fail", "no valid signature: " + row.instructions)
            )
        else:
            result, message = _judge_mechanism(root, row, declared, security, security_error, gate, own)
        if result == "fail" and stage not in row.blocks:
            result = "pending"
        rows.append(
            {
                "id": row.id,
                "title": row.title,
                "class": row.kind,
                "layer": row.layer,
                "phases": row.phases,
                "owner_role": row.owner_role,
                "refs": row.refs.model_dump(),
                "result": result,
                "message": message,
                "expires_at": (until.isoformat() if signed and (until := expires(signed, row.recurrence_days))
                               else None),
            }
        )
    counts: dict[str, int] = {}
    for item in rows:
        counts[item["result"]] = counts.get(item["result"], 0) + 1
    failed = counts.get("fail", 0)
    return {
        "schema": SCHEMA,
        "verdict": "fail" if failed else "pass",
        "stage": stage,
        "profile": declaration.profile,
        "reason": f"{failed} obligation(s) not met for {stage}" if failed else "",
        "rows": rows,
        "counts": counts,
    }


def provider_evidence(catalogue: Optional[list[c.Obligation]] = None) -> dict[str, Any]:
    """AgentSmith's own evidence for the obligations a tenant reads as `not_applicable`.
    Each tenant's provider rows point here, so it must be produced: by Self-Test and by
    the release (the 4.1.0 review's second pass, P2-R22). The verdict fails on a failing
    row that is not a named known gap, and on a known gap that has started to pass."""
    declared = json.loads(DECLARATION_TEMPLATE.read_text(encoding="utf-8"))
    rows, unexpected, stale = [], [], []
    for row in catalogue if catalogue is not None else load_catalogue():
        if row.layer != "provider":
            continue
        if row.kind == "attested":
            result, message = "fail", "a provider obligation is proved by AgentSmith's CI, not by a signature"
        else:
            result, message = _judge_mechanism(FRAMEWORK, row, declared, {}, "", {}, own=True)
        known = row.id in KNOWN_PROVIDER_GAPS
        if result == "fail" and not known:
            unexpected.append(row.id)
        if result != "fail" and known:
            stale.append(row.id)
        rows.append({"id": row.id, "title": row.title, "mechanism": row.mechanism, "result": result,
                     "message": message, "known_gap": result == "fail" and known,
                     **({"gap": KNOWN_PROVIDER_GAPS[row.id]} if known else {})})
    reasons = ([f"failing: {', '.join(unexpected)}"] if unexpected else []) + (
        [f"no longer failing, so remove from KNOWN_PROVIDER_GAPS: {', '.join(stale)}"] if stale else [])
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "fail" if reasons else "pass",
        "reason": "; ".join(reasons),
        "known_gaps": [r["id"] for r in rows if r["known_gap"]],
        "rows": rows,
    }


def repo_records(root: Path) -> list[c.Attestation]:
    path = root / c.ATTESTATIONS_FILE
    return c.parse_attestations(path.read_text(encoding="utf-8")) if path.is_file() else []


def exchange(records: list[c.Attestation]) -> tuple[list[c.Attestation], str]:
    """Send this repository's signatures to the portal; get the portal's back.
    -> (the portal's records, why not). Never follows a redirect, so a token is
    not copied to wherever one points."""
    url, token = os.environ.get("OPS_PORTAL_URL", "").strip(), os.environ.get("OPS_PORTAL_TOKEN", "").strip()
    if not url or not token:
        return [], "OPS_PORTAL_URL and OPS_PORTAL_TOKEN are not set"
    if not c.outbound_allowed(url):
        return [], "OPS_PORTAL_URL is outside the declared boundary"
    import httpx

    try:
        response = httpx.post(
            url.rstrip("/") + SYNC_PATH,
            json={"attestations": [r.model_dump() for r in records]},
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
            timeout=10.0,
        )
        if response.status_code != 200:
            return [], f"the portal answered {response.status_code}"
        return [c.Attestation.model_validate(r) for r in response.json()["attestations"]], ""
    except Exception as exc:  # the caller reports it; an unreachable portal signs nothing
        return [], f"the portal did not answer ({type(exc).__name__})"


def all_records(root: Path) -> tuple[list[c.Attestation], str]:
    mine = repo_records(root)
    theirs, why = exchange(mine)
    return mine + theirs, why


def _refs_text(refs: dict[str, Any]) -> str:
    names = {
        "desc_isr": "ISR",
        "nist_ai_rmf": "NIST",
        "iso42001_theme": "ISO theme",
        "uae_charter": "Charter",
        "dubai_ethics": "Digital Dubai",
        "owasp_llm": "OWASP",
        "uae_law": "Law",
    }
    return "; ".join(f"{names[k]} {', '.join(str(x) for x in v)}" for k, v in refs.items() if v) or "—"


def render_catalogue(catalogue: list[c.Obligation]) -> str:
    """The catalogue as a table, for the manual. No state: that is per application."""
    lines = [
        "| Obligation | Reference | Class | Layer | Phase | Owner | Repeat (days) | What to do |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in catalogue:
        lines.append(
            f"| `{r.id}` {r.title} | {_refs_text(r.refs.model_dump())} | {r.kind} | {r.layer} | {', '.join(r.phases)} "
            f"| {r.owner_role} | {r.recurrence_days or '—'} | {r.instructions} |"
        )
    return "\n".join(lines) + "\n"


def render_checklist(result: dict[str, Any], catalogue: list[c.Obligation], now: datetime) -> str:
    by_id = {r.id: r for r in catalogue}
    lines = [
        "# Compliance checklist",
        "",
        "Generated by `agentsmith compliance export`. Do not edit: sign at a terminal with "
        "`agentsmith attest`, or in the portal.",
        "",
        f"Profile `{result['profile']}`, checked for `{result['stage']}` on "
        f"{now.strftime('%Y-%m-%d')}. Verdict: **{result['verdict']}**.",
        "",
        "Not legal advice and not a certificate. It records the controls and evidence an assessor asks for.",
        "",
    ]
    for phase in ("design", "build", "deploy", "operate"):
        lines += [
            f"## {phase.capitalize()}",
            "",
            "| | Obligation | Reference | Class | Owner | Expires | What to do | Evidence |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in result["rows"]:
            if row["phases"][0] != phase:
                continue
            mark = {"pass": "✅", "fail": "❌", "pending": "⏳", "not_applicable": "—"}[row["result"]]
            o = by_id[row["id"]]
            lines.append(
                f"| {mark} | `{row['id']}` {row['title']} | {_refs_text(row['refs'])} | {row['class']} "
                f"| {row['owner_role']} "
                f"| {(row['expires_at'] or '—')[:10]} | {o.instructions} | {o.evidence} |"
            )
        lines.append("")
    return "\n".join(lines)


EVIDENCE_FILES = {
    "desc_isr": ("dubai_isr.md", "DESC Information Security Regulation"),
    "uae_charter": ("uae_charter.md", "UAE AI Charter"),
    "dubai_ethics": ("dubai_ethics.md", "Digital Dubai AI ethics"),
    "nist_ai_rmf": ("nist_ai_rmf.md", "NIST AI RMF and AI 600-1"),
    "owasp_llm": ("owasp_llm.md", "OWASP LLM Top 10 (2025)"),
    "uae_law": ("uae_law.md", "UAE and Dubai law"),
    "iso42001_theme": ("iso42001_themes.md", "ISO/IEC 42001 themes"),
}


def write_evidence(out: Path, result: dict[str, Any]) -> None:
    """The result, by clause of each instrument: what an assessor reads."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "compliance_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for key, (name, title) in EVIDENCE_FILES.items():
        clauses: dict[str, list[dict[str, Any]]] = {}
        for row in result["rows"]:
            for clause in row["refs"][key]:
                clauses.setdefault(str(clause), []).append(row)
        lines = [
            f"# {title}",
            "",
            "Not legal advice and not a certificate.",
            "",
            "| Clause | Obligation | Class | Result | Note |",
            "|---|---|---|---|---|",
        ]
        for clause in sorted(clauses, key=lambda c: [int(p) if p.isdigit() else 0 for p in c.split(".")]):
            lines += [
                f"| {clause} | `{r['id']}` {r['title']} | {r['class']} | {r['result']} "
                f"| {' '.join(r['message'].split())[:200]} |"
                for r in clauses[clause]
            ]
        (out / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="verb", required=True)
    check = sub.add_parser("check")
    check.add_argument("--stage", choices=("ci", "production"), required=True)
    status = sub.add_parser("status")
    status.add_argument("--stage", choices=("ci", "production"), default="production")
    export = sub.add_parser("export")
    export.add_argument("--stage", choices=("ci", "production"), default="production")
    export.add_argument("--out", default=CHECKLIST)
    export.add_argument("--evidence-dir", default=None, help="also write the report by clause here")
    sub.add_parser("sync")
    evidence = sub.add_parser("provider-evidence", help="AgentSmith's own evidence for its provider obligations")
    evidence.add_argument("--out", default=None, help="also write the document here")
    args = parser.parse_args(argv)
    if args.verb == "provider-evidence":
        document = provider_evidence()
        if args.out:
            Path(args.out).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        for row in document["rows"]:
            mark = "known gap" if row["known_gap"] else row["result"]
            print(f"  {mark:<15}{row['id']:<24}{row['message'][:110]}", file=sys.stderr)
        print(f"provider evidence: {document['verdict']}{': ' + document['reason'] if document['reason'] else ''}",
              file=sys.stderr)
        return 0 if document["verdict"] == "pass" else 1
    root, now = Path.cwd(), datetime.now(timezone.utc)
    try:
        if args.verb == "sync":
            records, why = exchange(repo_records(root))
            print(f"sync: {why}" if why else f"sync: the portal holds {len(records)} attestation(s)", file=sys.stderr)
            return 1 if why else 0
        records, why = all_records(root)
        result = evaluate(root, args.stage, now, records)
    except c.ComplianceUnreadable as exc:
        print(json.dumps({"schema": SCHEMA, "verdict": "fail", "reason": str(exc), "rows": [], "counts": {}}))
        return 0
    if why:
        result["portal"] = why
    if args.verb == "check":
        print(json.dumps(result))
        return 0
    if args.verb == "export":
        if result["verdict"] == "no_profile":
            print("export: this repository has no compliance profile", file=sys.stderr)
            return 2
        out = root / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_checklist(result, load_catalogue(), now), encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
        if args.evidence_dir:
            write_evidence(Path(args.evidence_dir), result)
        return 0
    print(f"{result['verdict']}: {result.get('reason') or result['counts']}")
    if why:
        print(f"portal: {why}")
    for row in result["rows"]:
        print(f"  {row['result']:<15}{row['id']:<24}{row['message'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
