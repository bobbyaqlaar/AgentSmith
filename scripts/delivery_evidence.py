"""
scripts/delivery_evidence.py — promote-time evidence pack (JSON + Markdown).

Collects Delivery Model artifacts (eval scorecard, fairness, redaction notes,
guardrail/HITL pointers) into:
  .agent-rfc/fixtures/delivery_evidence.json
  .agent-rfc/fixtures/delivery_evidence.md

Usage:
    python3 scripts/delivery_evidence.py
    python3 scripts/delivery_evidence.py --root /path/to/tenant

Exit 0 always — missing optional items are marked "missing" in the manifest
(soft evidence, not a hard gate). Pair with verify_system.py --check-delivery-model.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _shared import _repo_root  # noqa: E402


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _item(
    item_id: str,
    label: str,
    status: str,
    path: str | None = None,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "status": status,  # present | missing | skipped | note
        "path": path,
        "detail": detail,
    }


def collect_evidence(root: Path) -> dict[str, Any]:
    fixtures = root / ".agent-rfc" / "fixtures"
    items: list[dict[str, Any]] = []

    eval_path = fixtures / "eval_results.json"
    if eval_path.exists():
        try:
            data = json.loads(eval_path.read_text())
            passed = data.get("passed")
            detail = f"avg_score={data.get('avg_score')} passed={passed}"
            items.append(
                _item(
                    "eval_scorecard",
                    "Golden eval scorecard",
                    "present",
                    str(eval_path.relative_to(root)),
                    detail,
                )
            )
        except Exception as exc:
            items.append(
                _item(
                    "eval_scorecard",
                    "Golden eval scorecard",
                    "missing",
                    str(eval_path.relative_to(root)),
                    f"unreadable: {exc}",
                )
            )
    else:
        items.append(
            _item(
                "eval_scorecard",
                "Golden eval scorecard",
                "missing",
                ".agent-rfc/fixtures/eval_results.json",
                "Run: python3 scripts/run-evals.py --fail-below 0.80",
            )
        )

    fair_path = fixtures / "fairness_eval_results.json"
    if fair_path.exists():
        try:
            data = json.loads(fair_path.read_text())
            items.append(
                _item(
                    "fairness_scorecard",
                    "Fairness eval scorecard",
                    "present",
                    str(fair_path.relative_to(root)),
                    f"avg_score={data.get('avg_score')} pair_parity={data.get('avg_pair_parity')}",
                )
            )
        except Exception as exc:
            items.append(
                _item(
                    "fairness_scorecard",
                    "Fairness eval scorecard",
                    "missing",
                    str(fair_path.relative_to(root)),
                    f"unreadable: {exc}",
                )
            )
    else:
        items.append(
            _item(
                "fairness_scorecard",
                "Fairness eval scorecard",
                "missing",
                ".agent-rfc/fixtures/fairness_eval_results.json",
                "Optional: python3 scripts/run-evals.py --suite fairness",
            )
        )

    # Redaction: note how to produce evidence (CI runs verify_system --check-redaction)
    env = os.environ.get("ENVIRONMENT", "").strip() or "(unset)"
    items.append(
        _item(
            "redaction_check",
            "Trace redaction compliance",
            "note",
            None,
            f"ENVIRONMENT={env}. Produce via: "
            "ENVIRONMENT=staging|production python3 scripts/verify_system.py --check-redaction",
        )
    )

    guardrail = os.environ.get("INPUT_GUARDRAIL", "").strip() or "(unset → env default)"
    items.append(
        _item(
            "input_guardrail",
            "Pre-call PII guardrail mode",
            "note",
            "runtime/input_guardrail.py",
            f"INPUT_GUARDRAIL={guardrail}",
        )
    )

    org_policy = root / ".agenticframework" / "org-policy.yaml"
    items.append(
        _item(
            "org_policy",
            "Org delivery policy",
            "present" if org_policy.exists() else "missing",
            ".agenticframework/org-policy.yaml" if org_policy.exists() else None,
            "Copy templates/delivery-model/org-policy.example.yaml" if not org_policy.exists() else "",
        )
    )

    tenant = root / ".agenticframework" / "tenant.yaml"
    items.append(
        _item(
            "tenant_yaml",
            "Tenant config",
            "present" if tenant.exists() else "missing",
            ".agenticframework/tenant.yaml" if tenant.exists() else None,
            "Set delivery.platform + delivery.data_access_pattern",
        )
    )

    items.append(
        _item(
            "hitl_audit",
            "HITL / audit trail",
            "note",
            None,
            "Export Ops Portal GET /api/audit and Phoenix HITL annotations for high-impact flows",
        )
    )

    present = sum(1 for i in items if i["status"] == "present")
    missing = sum(1 for i in items if i["status"] == "missing")

    return {
        "timestamp": _iso_now(),
        "root": str(root),
        "summary": {"present": present, "missing": missing, "notes": len(items) - present - missing},
        "items": items,
    }


def render_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Delivery Model — promote evidence pack",
        "",
        f"Generated: `{manifest.get('timestamp')}`",
        "",
        f"Summary: **{manifest['summary']['present']}** present, "
        f"**{manifest['summary']['missing']}** missing, "
        f"**{manifest['summary']['notes']}** notes.",
        "",
        "| ID | Status | Path / detail |",
        "|---|---|---|",
    ]
    for item in manifest["items"]:
        path = item.get("path") or "—"
        detail = (item.get("detail") or "").replace("|", "\\|")
        lines.append(
            f"| `{item['id']}` | **{item['status']}** | {path}<br>{detail} |"
        )
    lines.extend(
        [
            "",
            "## How to refresh",
            "",
            "```bash",
            "python3 scripts/run-evals.py --fail-below 0.80",
            "python3 scripts/run-evals.py --suite fairness --fail-below 0.80  # optional",
            "ENVIRONMENT=staging python3 scripts/verify_system.py --check-redaction",
            "python3 scripts/verify_system.py --check-delivery-model",
            "python3 scripts/delivery_evidence.py",
            "```",
            "",
            "See `docs/delivery-model.md` and `docs/iso-42001-control-map.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_evidence_pack(root: Path, manifest: dict[str, Any] | None = None) -> dict[str, Path]:
    if manifest is None:
        manifest = collect_evidence(root)
    fixtures = root / ".agent-rfc" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    json_path = fixtures / "delivery_evidence.json"
    md_path = fixtures / "delivery_evidence.md"
    json_path.write_text(json.dumps(manifest, indent=2) + "\n")
    md_path.write_text(render_markdown(manifest))
    return {"json": json_path, "md": md_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Delivery Model evidence pack")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Tenant/repo root (default: git root / cwd)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else _repo_root()
    paths = write_evidence_pack(root)
    print(f"Wrote {paths['json']}")
    print(f"Wrote {paths['md']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
