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
    """The schemas are generated from the Pydantic models, not written twice.

    Both sides are READ. The event half always was; the decision half compared
    against `{"decision", "text"}` and `{"allow", "deny", "block", "context"}`
    written out here — a third copy of the catalogue, which
    `pin-unremovable-duplicates` names exactly: "a test that hardcodes the second
    copy is just a third copy". `Decision` could have gained a field, or a fifth
    verdict, and the published contract a third party implements against could
    have gone stale with this test green
    (.agent-rfc/designs/gate-tag-coverage.md).
    """
    import typing

    import gate_models as gm

    event_schema = json.loads((REPO / "contract/gate/v1/event.schema.json").read_text())
    assert set(event_schema["properties"]) == set(gm.GateEvent.model_fields)

    decision_schema = json.loads((REPO / "contract/gate/v1/decision.schema.json").read_text())
    assert set(decision_schema["properties"]) == set(gm.Decision.model_fields)

    verdicts = set(typing.get_args(gm.Decision.model_fields["decision"].annotation))
    assert verdicts, "Decision.decision is no longer a Literal — read its values another way"
    assert set(decision_schema["properties"]["decision"]["enum"]) == verdicts


def test_what_adopt_writes_validates_against_the_published_providers_schema():
    """`contract/gate/v1/providers.schema.json` was referenced by no test.

    It is published so a third party can write a conforming declaration, and
    `agentsmith tenant adopt` writes one — with nothing checking the two agree.
    A field renamed on either side would have shipped a schema that rejects the
    framework's own output (.agent-rfc/designs/gate-tag-coverage.md).
    """
    import jsonschema

    from runtime.adopt import providers_declaration

    # adopt writes gate contract 2 since .agent-rfc/designs/gate-contract-ci.md; a
    # contract-1 declaration still validates against v1's schema
    # (test_gate_contract_v2.py::test_a_version_1_declaration_still_reads_as_version_1).
    schema = json.loads((REPO / "contract/gate/v2/providers.schema.json").read_text(encoding="utf-8"))
    written = json.loads(providers_declaration())
    jsonschema.validate(written, schema)

    # And the declaration a repository uses to opt OUT must conform too, since
    # `"gate": "none"` is the one value the launcher must never override.
    ungoverned = {**written, "providers": {"gate": "none"}}
    jsonschema.validate(ungoverned, schema)


def test_the_providers_schema_rejects_a_declaration_the_launcher_cannot_read():
    """A schema that accepts anything pins nothing."""
    import jsonschema
    import pytest as _pytest

    schema = json.loads((REPO / "contract/gate/v1/providers.schema.json").read_text(encoding="utf-8"))
    for bad, why in (
        ({"providers": {"gate": {"command": "x"}}}, "no contract version"),
        ({"contract": 1, "providers": {"gate": {}}}, "a gate provider with no command"),
        ({"contract": "one", "providers": {"gate": "none"}}, "a contract version that is not a number"),
    ):
        with _pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
            raise AssertionError(f"the schema accepted a declaration with {why}")
