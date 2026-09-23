"""
scripts/test/test_gate_contract.py — AgentSmith satisfies its own gate contract
(.agent-rfc/designs/gate-port.md).

The contract is only worth as much as the suite that proves it, and the first
provider it must hold for is this one. `agentsmith gate <event>` is the adapter:
the neutral profile over the same decision path every IDE dialect goes through.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")

# In a real tenant this is the installed `agentsmith gate` on PATH. Here it is
# this checkout's CLI, run the same way: from the fixture repository's
# directory, so the provider must not depend on where it was started.
PROVIDER = f"{sys.executable} -m runtime.cli gate"


def test_agentsmith_passes_its_own_conformance_suite(tmp_path, monkeypatch):
    from runtime import conformance

    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("PYTHONPATH", str(REPO))  # what an installed `agentsmith` gets from PATH

    report = conformance.run(PROVIDER, tmp_path / "work")

    assert report.passed, report.render()


def test_the_neutral_decision_matches_what_the_ide_adapters_are_given():
    """The neutral profile renders the same decision an IDE dialect renders, so
    a provider cannot answer one thing to Claude Code and another to a tenant."""
    import gate_ides as gi

    assert "neutral" in gi.ADAPTERS
    assert "neutral" not in gi.IDES, "the neutral profile is a contract, not an IDE"
    rendered = json.loads(gi.render("neutral", "deny", "because the design says so"))
    assert rendered == {"decision": "deny", "text": "because the design says so"}


def test_the_published_schemas_match_the_models_they_describe():
    """The schemas are generated from the Pydantic models, not written twice."""
    import gate_models as gm

    event_schema = json.loads((REPO / "contract/gate/v1/event.schema.json").read_text())
    assert set(event_schema["properties"]) == set(gm.GateEvent.model_fields)
    decision_schema = json.loads((REPO / "contract/gate/v1/decision.schema.json").read_text())
    assert set(decision_schema["properties"]) == {"decision", "text"}
    assert set(decision_schema["properties"]["decision"]["enum"]) == {"allow", "deny", "block", "context"}
