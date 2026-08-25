"""
scripts/test/test_no_orphaned_entrypoints.py — a public function nothing calls
is a feature that does not exist.

Three of these in one session, which is why it is now a test rather than a
habit:

  * `runtime.metrics.configure_metrics()` — no caller in the framework, the
    tenant, or the example. Every counter in that module wrote into a
    `_ProxyMeter` that was never resolved, so the error rate and cache hit ratio
    the observability audit asked for were computable in no deployment. The
    call sites were all correct; the installation never happened.
  * `IdempotencyStore.purge_expired()` — no caller, while its table grew one row
    per gateway call, forever.
  * `tool_registry._DEFAULT_REGISTRY` — private, with no accessor, so a tool
    registered through the documented `@tool(name=...)` decorator could not be
    invoked by anything.

They are invisible to ordinary review because everything you would inspect looks
right — correct code, correct tests, correct attributes. And a component that
no-ops when it is not installed, which is the correct choice for telemetry,
cannot tell you it was never installed.

REFERENCES ARE COLLECTED FROM THE AST, not by grepping text: a function named in
a docstring is not a caller, and this test exists precisely to catch the case
where the prose is right and the wiring is absent. Non-Python files are searched
too, because a CI workflow invoking `python3 scripts/verify_system.py
--check-kg` is a real call site that no Python AST contains.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Entry points a deployment or a human invokes by name, not by import.
_INVOKED_BY_NAME = {"main", "run", "sync", "promote"}


def _tracked(pattern: str) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", pattern], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.split()
    return [ROOT / p for p in out]


def _public_defs() -> dict[str, list[Path]]:
    """Module-level public functions in the two shipped packages."""
    found: dict[str, list[Path]] = {}
    for path in _tracked("runtime/*.py") + _tracked("scripts/*.py"):
        if "test" in path.name:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                if node.name in _INVOKED_BY_NAME:
                    continue
                found.setdefault(node.name, []).append(path)
    return found


def _referenced_names() -> set[str]:
    """Every name USED anywhere — from the AST for Python, text for the rest."""
    used: set[str] = set()
    for path in _tracked("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                used.update(a.name for a in node.names)
    # A workflow step or a Makefile target is a call site with no Python in it.
    word = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
    for pattern in (".github/workflows/*.yml", "*.sh", "Makefile", "workflow-templates/*.yml"):
        for path in _tracked(pattern):
            try:
                used.update(word.findall(path.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
    return used


def test_the_sweep_reads_something() -> None:
    """A sweep that matches nothing passes for the wrong reason (lever 6.5)."""
    defs = _public_defs()
    assert len(defs) > 100, f"the sweep found almost no definitions: {len(defs)}"
    refs = _referenced_names()
    assert len(refs) > 1000, f"the sweep found almost no references: {len(refs)}"


@pytest.mark.parametrize("known_caller", ["configure_tracing", "resolve_tenant_id", "agent_span"])
def test_the_sweep_can_see_a_real_caller(known_caller: str) -> None:
    """The control. These three are unambiguously called; if the reference
    collector cannot see them, an empty orphan list proves nothing."""
    assert known_caller in _referenced_names()


def test_every_public_function_has_a_caller() -> None:
    defs = _public_defs()
    refs = _referenced_names()

    orphans = {
        name: [str(p.relative_to(ROOT)) for p in paths]
        for name, paths in defs.items()
        if name not in refs
    }
    assert not orphans, (
        "these are defined and never referenced — built, and reachable by "
        "nothing:\n  "
        + "\n  ".join(f"{n}: {', '.join(f)}" for n, f in sorted(orphans.items()))
    )


def test_configure_metrics_specifically_is_reachable() -> None:
    """Named on its own because it is the one that cost the most to find, and
    because 'reachable' for it means something stricter than 'referenced': a
    worker entrypoint has to install a MeterProvider, not merely import one."""
    refs = _referenced_names()
    assert "configure_metrics" in refs
    worker = (ROOT / "runtime" / "worker.py").read_text(encoding="utf-8")
    assert "configure_telemetry()" in worker
