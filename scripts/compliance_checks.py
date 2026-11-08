"""scripts/compliance_checks.py — what the compliance provider reads in a
repository on a profile. Each returns (result, message): "pass" or "fail".

These read the repository, never the environment, so a verdict does not depend on
the machine it ran on.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlparse

import yaml

Verdict = tuple[str, str]
_SKIP = {".venv", "venv", "node_modules", ".git", "__pycache__", "test", "tests"}
_ARABIC = re.compile("[؀-ۿ]")


def _python_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*.py"):
        if not _SKIP.intersection(path.relative_to(root).parts):
            yield path


def _calls(root: Path) -> Iterator[tuple[Path, ast.Call]]:
    for path in _python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                yield path, node


def _name(call: ast.Call) -> str:
    return call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")


def _yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


_SIDECAR_SOURCE = (".ts", ".tsx", ".js", ".mjs", ".go")
_DIRECT_SDK = re.compile(r"openai|anthropic|generative-ai|langchain|bedrock", re.I)


def _sidecar_sources(root: Path) -> Iterator[tuple[Path, str]]:
    for path in root.rglob("*"):
        if path.suffix in _SIDECAR_SOURCE and path.is_file() and not _SKIP.intersection(path.relative_to(root).parts):
            yield path, path.read_text(encoding="utf-8", errors="ignore")


def _sidecar_wiring(root: Path, wanted: set[str]) -> Verdict:
    """An app with no Python runtime: every listed action asks the sidecar for a gate."""
    sources = list(_sidecar_sources(root))
    asked = [text for _, text in sources if "/v1/gate/request" in text]
    missing = sorted(action for action in wanted if not any(action in text for text in asked))
    if missing:
        return "fail", "no call to /v1/gate/request names: " + ", ".join(missing)
    return "pass", f"{len(wanted)} action(s) ask the sidecar for a gate"


def sidecar_only(root: Path, declared: dict[str, Any]) -> Verdict:
    """An app on the sidecar reaches models only through it."""
    if declared.get("runtime") != "sidecar":
        return "pass", "this app uses the Python runtime"
    for name in ("package.json", "go.mod"):
        manifest = root / name
        if manifest.is_file() and _DIRECT_SDK.search(manifest.read_text(encoding="utf-8")):
            return "fail", f"{name} depends on a model vendor's SDK: call the sidecar instead"
    if not any("/v1/complete" in text for _, text in _sidecar_sources(root)):
        return "fail", "nothing calls the sidecar's /v1/complete"
    return "pass", "model calls go through the sidecar"


def hitl_wiring(root: Path, declared: dict[str, Any]) -> Verdict:
    """Every action the manifest says needs a person reaches a gate that records one."""
    manifest = _yaml(root / ".agent-rfc" / "security" / "agency_manifest.yaml")
    wanted = {a["action"] for a in manifest.get("actions", []) if isinstance(a, dict) and a.get("needs_hitl")}
    if not wanted:
        return "fail", "agency_manifest.yaml lists no action that needs a person"
    if declared.get("runtime") == "sidecar":
        return _sidecar_wiring(root, wanted)
    covered: set[str] = set()
    weak: list[str] = []
    for path, call in _calls(root):
        if _name(call) != "run_with_hitl_gate":
            continue
        strings = {
            n.value
            for arg in [*call.args, *[k.value for k in call.keywords]]
            for n in ast.walk(arg)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        named = any(
            k.arg == "compliance" and isinstance(k.value, ast.Constant) and k.value.value is True for k in call.keywords
        )
        if named:
            covered |= strings
        elif strings & wanted:
            weak.append(f"{path.relative_to(root)}:{call.lineno}")
    missing = sorted(wanted - covered)
    if missing or weak:
        return "fail", "no run_with_hitl_gate(..., compliance=True) reaches: " + ", ".join(missing or weak)
    return "pass", f"{len(wanted)} action(s) reach a named gate"


def agent_owners(root: Path, declared: dict[str, Any]) -> Verdict:
    agents = declared.get("agents") or []
    return (
        ("pass", f"{len(agents)} agent(s) have an owner") if agents else ("fail", "no agent names an accountable owner")
    )


def data_class_usage(root: Path, declared: dict[str, Any]) -> Verdict:
    """A model call that does not say what it carries is treated as classified at run
    time. Requiring it here keeps that a decision and not an accident."""
    if declared.get("runtime") == "sidecar":
        return "pass", "the sidecar refuses a call with no data_class"
    missing = [
        f"{p.relative_to(root)}:{c.lineno}"
        for p, c in _calls(root)
        if _name(c) in ("complete", "complete_stream")
        and isinstance(c.func, ast.Attribute)
        and "gateway" in ast.unparse(c.func.value).lower()
        and not any(k.arg in ("data_class", None) for k in c.keywords)
    ]
    return (
        ("fail", "gateway calls with no data_class: " + ", ".join(missing[:5]))
        if missing
        else ("pass", "every gateway call states its data class")
    )


def _registry(root: Path) -> dict[str, Any]:
    for rel in ("models.yaml", ".agenticframework/models.yaml"):
        if (root / rel).is_file():
            return _yaml(root / rel)
    return {}


def _in_boundary(host: str | None, allowed: list[str]) -> bool:
    from agentsmith.compliance import host_allowed

    return host_allowed(host, allowed)


def residency(root: Path, declared: dict[str, Any]) -> Verdict:
    """This application's own registry and data stores, against its own boundary."""
    from agentsmith.llm_gateway import _roles_from_doc
    from security.runners.sovereign_residency import _violations

    document = _registry(root)
    if not document:
        return "fail", "no models.yaml, so the routes cannot be checked"
    roles = _roles_from_doc(document)
    problems = list(_violations(roles))
    allowed = declared["boundary"]["hosts"]
    for role, cfg in sorted(roles.items()):
        endpoint = str(cfg.get("endpoint") or "")
        # An environment reference is resolved at run time, where the gateway refuses it if it is outside.
        if endpoint and "${" not in endpoint and not _in_boundary(urlparse(endpoint).hostname, allowed):
            problems.append(f"{role}: {endpoint} is outside the boundary")
    for sink, host in sorted(declared["boundary"].get("sinks", {}).items()):
        if not _in_boundary(host, allowed):
            problems.append(f"sink {sink}: {host} is outside the boundary")
    return (
        ("fail", "; ".join(problems[:5]))
        if problems
        else ("pass", f"{len(roles)} route(s) and every sink stay inside the boundary")
    )


def moderation_required(root: Path, declared: dict[str, Any]) -> Verdict:
    moderation = _yaml(root / ".agenticframework" / "tenant.yaml").get("moderation") or {}
    if moderation.get("mode") != "required" or not moderation.get("hook"):
        return "fail", "tenant.yaml must declare moderation.mode: required and a moderation.hook"
    return "pass", "output moderation is required and declared"


def name_scrubber(root: Path, declared: dict[str, Any]) -> Verdict:
    security = _yaml(root / ".agenticframework" / "tenant.yaml").get("security") or {}
    if security.get("input_guardrail") != "custom":
        return (
            "fail",
            "the default scrubbers do not catch names: declare security.input_guardrail: custom and register one",
        )
    return "pass", "a custom guardrail is declared"


def fairness_gate(root: Path, declared: dict[str, Any]) -> Verdict:
    path = root / ".agenticframework" / "providers.json"
    if path.is_file() and re.search(r'"fairness"\s*:\s*"warn"', path.read_text(encoding="utf-8")):
        return "fail", "providers.json lets a fairness failure only warn"
    return "pass", "a fairness failure fails the build"


def arabic_cases(root: Path, declared: dict[str, Any]) -> Verdict:
    if "ar" not in declared.get("languages", []):
        return "pass", "Arabic is not a declared language"
    thin = [
        f.name
        for f in (root / ".agent-rfc" / "fixtures").glob("*evals*.json")
        if not _ARABIC.search(f.read_text(encoding="utf-8"))
    ]
    return (
        ("fail", "no Arabic cases in: " + ", ".join(sorted(thin)))
        if thin
        else ("pass", "the app's suites include Arabic, or it uses the base suites, which do")
    )


def supply_chain(root: Path, declared: dict[str, Any]) -> Verdict:
    from agentsmith import mcp_pin

    if not (root / ".github" / "workflows" / "agentsmith-supply-chain.yml").is_file():
        return "fail", ".github/workflows/agentsmith-supply-chain.yml is missing"
    problems = mcp_pin.static_problems(root)
    return (
        ("fail", "; ".join(problems[:5]))
        if problems
        else ("pass", "the supply-chain job is present and MCP servers are pinned")
    )


def restore_drill(root: Path, declared: dict[str, Any]) -> Verdict:
    """A restore someone actually ran, recently enough for what was declared."""
    period = declared["continuity"]["drill_every_days"]
    newest: datetime | None = None
    for path in (root / ".agenticframework" / "drills").glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("result") == "pass":
            at = datetime.fromisoformat(record["at"].replace("Z", "+00:00"))
            newest = max(newest, at) if newest else at
    if newest is None:
        return "fail", "no passing restore drill: run `agentsmith ops restore-drill`"
    if datetime.now(timezone.utc) - newest > timedelta(days=period):
        return "fail", f"the last restore drill is older than {period} days"
    return "pass", f"restore drill passed {newest.date()}"


def traces_private(root: Path, declared: dict[str, Any]) -> Verdict:
    """A self-hosted Phoenix whose web UI still reports usage has a route out."""
    leaky = []
    for path in [*root.rglob("*.yml"), *root.rglob("*.yaml")]:
        if _SKIP.intersection(path.relative_to(root).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "arizephoenix/phoenix" in text and not re.search(r'PHOENIX_TELEMETRY_ENABLED:\s*"?false', text):
            leaky.append(str(path.relative_to(root)))
    if leaky:
        return "fail", "Phoenix without PHOENIX_TELEMETRY_ENABLED=false: " + ", ".join(leaky)
    return "pass", "no Phoenix reports out"


def declaration_deployed(root: Path, declared: dict[str, Any]) -> Verdict:
    """An image without the declaration has no duties at run time."""
    images = list(root.rglob("Dockerfile"))
    missing = [
        str(p.relative_to(root))
        for p in images
        if not _SKIP.intersection(p.relative_to(root).parts)
        and not re.search(r"^\s*COPY\s+(\.\s|\.agenticframework)", p.read_text(encoding="utf-8"), re.M)
    ]
    if missing:
        return "fail", "these images do not copy .agenticframework/compliance.json: " + ", ".join(missing)
    return "pass", "the declaration ships with the image" if images else "no Dockerfile here"


CHECKS: dict[str, Callable[[Path, dict[str, Any]], Verdict]] = {
    "hitl_wiring": hitl_wiring,
    "agent_owners": agent_owners,
    "data_class_usage": data_class_usage,
    "residency": residency,
    "moderation_required": moderation_required,
    "name_scrubber": name_scrubber,
    "fairness_gate": fairness_gate,
    "arabic_cases": arabic_cases,
    "supply_chain": supply_chain,
    "restore_drill": restore_drill,
    "declaration_deployed": declaration_deployed,
    "sidecar_only": sidecar_only,
    "traces_private": traces_private,
}
