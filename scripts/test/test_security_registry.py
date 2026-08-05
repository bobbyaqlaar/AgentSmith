from __future__ import annotations

from pathlib import Path

import pytest

from security.registry import load_control_registry, ControlSpec


REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "fixtures" / "security" / "control_registry.json"


def test_registry_file_exists() -> None:
    assert REGISTRY.exists(), "control_registry.json missing"


def test_load_control_registry_returns_sec_pii_001() -> None:
    controls = load_control_registry(REGISTRY)
    ids = {c.id for c in controls}
    assert "SEC-PII-001" in ids


def test_every_control_has_framework_tags() -> None:
    controls = load_control_registry(REGISTRY)
    for c in controls:
        assert c.frameworks.owasp or c.frameworks.nist or c.frameworks.atlas or c.frameworks.iso42001


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('[{"id":"SEC-X-001","title":"a","status":"met","owner":"framework","frameworks":{},"runner":"noop","check_type":"unit","mechanism":"x"},{"id":"SEC-X-001","title":"b","status":"met","owner":"framework","frameworks":{},"runner":"noop","check_type":"unit","mechanism":"y"}]')
    with pytest.raises(ValueError, match="duplicate"):
        load_control_registry(bad)


# ── Verification coverage ────────────────────────────────────────────────────


def test_every_registered_runner_name_resolves() -> None:
    """A control naming a runner that does not exist returns `skip`, and skip
    counts as green even under --strict. That is how the harness exited 0 with
    14 of 23 controls unexamined — including SEC-HITL-001, mandatory human
    review, while a live run showed that gate failing open.

    This does not require every control to be implemented; it requires the
    registry not to name a runner that silently resolves to nothing beyond the
    documented, reviewed exceptions below.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from security.runners import RUNNERS

    controls = load_control_registry(REGISTRY)
    # Reviewed and deliberately unbound — each has a rationale in
    # docs/security-framework-map.md "Still unverified".
    known_unbound = {
        "SEC-AUDIT-001", "SEC-RBAC-001", "SEC-DLQ-001",
        "SEC-SOV-001", "SEC-RAG-001", "SEC-AGENCY-001",
    }
    dangling = sorted(
        c.id for c in controls if c.runner not in RUNNERS and c.id not in known_unbound
    )
    assert not dangling, (
        f"controls naming a non-existent runner: {dangling}. These will `skip`, "
        f"and skip passes --strict — the harness would report success without "
        f"checking them. Implement the runner, or add the control to the "
        f"documented exception list with a rationale."
    )


def test_the_documented_unverified_list_matches_reality() -> None:
    """The security map publishes which controls are unverified. If a runner
    lands and the doc still lists it, the map understates coverage; if one is
    removed and the doc does not, it overstates it — the direction that
    matters."""
    import re
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from security.runners import RUNNERS

    doc = (REGISTRY.parents[2] / "docs" / "security-framework-map.md").read_text()
    section = doc.split("### Still unverified", 1)[1]
    listed = set(re.findall(r"\| `(SEC-[A-Z0-9-]+)` \| `", section))
    actual = {c.id for c in load_control_registry(REGISTRY) if c.runner not in RUNNERS}
    assert listed == actual, (
        f"security-framework-map.md 'Still unverified' is stale.\n"
        f"  documented but now verified: {sorted(listed - actual)}\n"
        f"  unverified but undocumented: {sorted(actual - listed)}"
    )


def test_a_tenant_registry_cannot_redefine_a_framework_control(tmp_path) -> None:
    """A registry the graded repo can edit is one where that repo can quietly
    downgrade SEC-HITL-001 to `noop` and keep a green harness. Tenant
    registries are additive; a clash must raise, not silently win."""
    import json

    evil = tmp_path / "control_registry.json"
    evil.write_text(json.dumps([{
        "id": "SEC-HITL-001", "title": "downgraded", "status": "met",
        "owner": "tenant", "runner": "noop", "check_type": "unit",
        "mechanism": "weakened",
    }]))
    with pytest.raises(ValueError, match="additive"):
        load_control_registry(REGISTRY, evil)


def test_a_tenant_registry_adds_controls(tmp_path) -> None:
    import json

    extra = tmp_path / "control_registry.json"
    extra.write_text(json.dumps([{
        "id": "SEC-TENANT-TEST-001", "title": "tenant control", "status": "met",
        "owner": "tenant", "runner": "tenant_suite", "suite": "test/x.py",
        "check_type": "unit", "mechanism": "tenant-owned",
    }]))
    base = {c.id for c in load_control_registry(REGISTRY)}
    merged = {c.id for c in load_control_registry(REGISTRY, extra)}
    assert merged == base | {"SEC-TENANT-TEST-001"}
    added = next(c for c in load_control_registry(REGISTRY, extra)
                 if c.id == "SEC-TENANT-TEST-001")
    assert added.suite == "test/x.py"
