"""
runtime/sync.py — `agentsmith sync`: bring a tenant's copies of this framework
up to date (.agent-rfc/designs/framework-sync.md).

    plan_sync(root)     what is stale, without writing
    sync(plan)          write it; returns the paths it wrote
    commit_command(...) the commit, which the tenant's own gates accept

A tenant holds the gate hooks, the IDE hook configs, the generated rule files
and — vendored tenants — the framework's own code. `agentsmith upgrade`
refreshed the last group only, so the rest drifted silently: the gate hooks
changed six times in 90 days and no tenant saw any of it.

Everything here writes what THIS framework owns and nothing else. The tenant's
code, its CI beyond the gates workflow, and its documents are not touched, which
is what lets the commit be reviewed by hash rather than by hand.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SYNC_DESIGN = ".agent-rfc/designs/adoption.md"
MANIFEST = ".agenticframework/scaffold.json"
GENERATED_BY = "agentsmith sync"


class SyncError(ValueError):
    """This repository is not one `sync` can bring up to date."""


@dataclass
class Plan:
    root: Path
    tenant_id: str
    stack: str
    vendored: bool
    framework: Path
    version: str
    stale: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _manifest(root: Path) -> dict:
    try:
        return json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def is_adopted(root: Path) -> bool:
    """A repository `tenant adopt` brought in: never vendored into, by either
    path (`agentsmith sync` and `agentsmith upgrade` both read this)."""
    return str(_manifest(root).get("generated_by", "")).endswith("tenant adopt")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_sync(root: Path, *, tenant_id: Optional[str] = None, framework: Optional[Path] = None) -> Plan:
    """What `sync` would refresh here. Writes nothing.

    `framework` names the copy to sync FROM; the default is the one this
    install resolves. A tenant is stale when the framework moved on, so the two
    are deliberately separate."""
    from runtime.cli import _default_framework_version, _framework_dir, missing_gate_hooks

    root = Path(root)
    if not (root / ".agenticframework" / "process-gates.json").is_file():
        raise SyncError(f"{root} is not under the gates — `agentsmith tenant adopt` brings a repository in")
    framework = Path(framework) if framework is not None else _framework_dir()
    if framework is None:
        raise SyncError("AgentSmith's scripts are not in $AGENTSMITH_DIR, ~/.agent-framework or this "
                        "checkout — run install-ai-stack.sh")
    missing = missing_gate_hooks(framework)
    if missing:
        raise SyncError(f"{framework}/.githooks/ has no {', '.join(missing)} — this install cannot arm the "
                        "gates, and a sync from it would disarm this repository. Re-run install-ai-stack.sh")

    manifest = _manifest(root)
    plan = Plan(root=root, tenant_id=tenant_id or str(manifest.get("tenant") or root.name),
                stack=str(manifest.get("stack") or "python-fastapi"), vendored=not is_adopted(root),
                framework=framework, version=_default_framework_version())
    # Stale: a file this framework owns whose copy here differs from the
    # framework's. Only files it already wrote — a sync adds nothing new to a
    # repository that did not ask for it.
    for hook in (framework / ".githooks").iterdir():
        here = root / ".githooks" / hook.name
        if here.is_file() and hook.is_file() and _digest(here) != _digest(hook):
            plan.stale.append(f".githooks/{hook.name}")
    if plan.vendored:
        plan.notes.append("vendored tenant: scripts/, runtime/, templates/ and fixtures/ are refreshed too")
    else:
        plan.notes.append("adopted repository: nothing is vendored into it")
    return plan


def describe(plan: Plan) -> str:
    lines = [f"Syncing {plan.root} with AgentSmith {plan.version}", ""]
    lines += [f"  stale   {path}" for path in plan.stale] or ["  nothing stale in what this framework owns"]
    lines += [f"\n  ! {note}" for note in plan.notes]
    return "\n".join(lines)


def sync(plan: Plan) -> list[str]:
    """Refresh what this framework owns here. Returns the paths written."""
    from runtime.adopt import PROVIDERS, providers_declaration
    from runtime.cli import install_gate_hooks, write_scaffold_records

    root, written = plan.root, []

    # The hooks, from the one implementation `init` and `adopt` use. `force`,
    # because refreshing a stale copy is the point.
    install_gate_hooks(root, plan.framework, force=True, provisioning=False)
    written += plan.stale
    if not (root / PROVIDERS).exists():
        (root / PROVIDERS).write_text(providers_declaration(), encoding="utf-8")
        written.append(PROVIDERS)

    if plan.vendored:
        from runtime.machine.upgrade import upgrade

        upgrade(root, plan.version, out=lambda _line: None)

    # Only what actually moved: `install_gate_hooks` rewrites every hook, and a
    # commit listing files whose bytes did not change is noise a reviewer reads
    # past — and a manifest entry nobody needed.
    written = [path for path in dict.fromkeys(written) if _changed(root, path)]
    if not written:
        return []
    written += write_scaffold_records(root, plan.tenant_id, plan.stack, None, False, written,
                                      force=True, design=SYNC_DESIGN, adopted=not plan.vendored,
                                      generated_by=GENERATED_BY)
    return written


def _changed(root: Path, rel: str) -> bool:
    """Is this path different from what the repository has committed?"""
    done = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", rel],
                          capture_output=True, text=True, check=False)
    return bool(done.stdout.strip())


def commit_command(written: list[str], version: str) -> str:
    paths = " ".join(shlex.quote(path) for path in written)
    return (f"git add -- {paths} && git commit -m \"chore(framework): sync AgentSmith {version}\" "
            f"-m \"Design: {SYNC_DESIGN}\" -m \"Review: n/a: framework sync {version}\"")
