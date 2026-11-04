"""
scripts/test/test_package_name.py — the package imports as `agentsmith`, and
nothing tracked still imports the old name (.agent-rfc/designs/package-agentsmith.md).

Two things keep the word `runtime`, on purpose, and are held here too: the
OpenTelemetry scope is a wire value, and a pre-3.0.0 tenant holds a `runtime/`
directory, which detection has to keep finding.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OLD = "run" + "time"  # so this file does not match itself
_CODE_SUFFIXES = (".py", ".sh", ".yml", ".yaml", ".toml", ".ini", ".txt", ".j2")
_STALE = re.compile(rf"^\s*(?:from|import)\s+{OLD}\b|-m\s+{OLD}\b|\b{OLD}\.cli\b", re.MULTILINE)
# A recording of a retired install, kept byte for byte.
_HISTORY = {"scripts/test/fixtures/legacy_profile_block.zshrc"}


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def test_no_tracked_code_imports_the_old_name():
    stale = []
    for name in _tracked():
        path = REPO / name
        if name in _HISTORY or not name.endswith(_CODE_SUFFIXES) or not path.is_file():
            continue
        if _STALE.search(path.read_text(encoding="utf-8", errors="replace")):
            stale.append(name)
    assert not stale, f"still importing `{OLD}`: {stale}"


def test_the_package_declares_the_new_name():
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["name"] == "agentsmith-runtime"
    assert project["project"]["scripts"]["agentsmith"] == "agentsmith.cli:main"
    packages = project["tool"]["setuptools"]["packages"]
    assert "agentsmith" in packages
    assert not any(p == OLD or p.startswith(f"{OLD}.") for p in packages)
    assert not (REPO / OLD).exists()


def test_the_wire_scope_keeps_its_value():
    """`agentsmith.runtime` is what a tenant's dashboards filter on, not an import."""
    fixture = json.loads((REPO / "contract/telemetry/v1/fixture.json").read_text(encoding="utf-8"))
    assert f"agentsmith.{OLD}" in json.dumps(fixture)
    assert f'get_tracer("agentsmith.{OLD}")' in (REPO / "agentsmith/tracing.py").read_text(encoding="utf-8")


def test_detection_still_finds_what_a_pre_3_tenant_holds():
    source = (REPO / "agentsmith/adopt.py").read_text(encoding="utf-8")
    assert f'"{OLD}": "llm_gateway.py"' in source
