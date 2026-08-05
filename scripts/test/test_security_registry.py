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
    # A control with no runner must DECLARE itself a gap. The exception list is
    # gone: the registry's own `status` field now carries that fact, so there is
    # no second list to drift. An undeclared gap fails --strict.
    lying = sorted(
        c.id for c in controls if c.runner not in RUNNERS and c.status != "gap"
    )
    assert not lying, (
        f"controls claiming met/partial with no runner: {lying}. Nothing "
        f"verifies them, so the map overstates coverage. Implement the runner "
        f"or set status to 'gap'."
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


def test_an_undeclared_gap_fails_strict_but_a_declared_one_does_not() -> None:
    """The distinction step 1 turns on.

    `skip` and `warn` each carried two opposite meanings and the harness could
    not tell them apart, so a control claiming `met` with no runner passed
    `--strict` — how 14 of 23 controls reported green while never being
    examined.

    Strict now punishes the LIE, not the acknowledged gap. Blocking on declared
    gaps would make --strict unusable and create an incentive to relabel a gap
    as `met`, which is exactly the failure being fixed.
    """
    from _shared import load_script

    rsc = load_script("run-security-checks")
    from security.report import ControlResult
    from security.runners._shared import DECLARED_GAP, NOT_APPLICABLE

    declared = ControlResult("SEC-X", "warn", f"{DECLARED_GAP} — not yet implemented", {})
    undeclared = ControlResult("SEC-Y", "warn", "declared 'met' but runner missing", {})
    n_a = ControlResult("SEC-Z", "skip", f"{NOT_APPLICABLE} — no dataset here", {})

    assert rsc._resolve_exit([declared], strict=True) == 0, "a declared gap must not block"
    assert rsc._resolve_exit([n_a], strict=True) == 0, "not-applicable must not block"
    assert rsc._resolve_exit([undeclared], strict=True) == 1, "an undeclared gap must block"
    # Non-strict stays permissive for all three.
    assert rsc._resolve_exit([declared, undeclared, n_a], strict=False) == 0


# ── Reuse guard ──────────────────────────────────────────────────────────────


def test_scripts_has_exactly_one_script_loader() -> None:
    """`_shared.load_script` is the only place that loads a hyphen-named script.

    Thirteen files hand-rolled the same importlib dance and three had
    independently reinvented caching around it. Caching is not cosmetic here:
    `run-evals.py` resolves the model registry and reads .env at import, and
    the security harness loaded it once per eval control.

    Matched by AST rather than text, so a file that merely NAMES the function —
    this test does — is not counted. runtime/ is exempt by design: it is
    vendored independently and must not import scripts/.
    """
    import ast
    import subprocess

    repo = REGISTRY.parents[2]
    files = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "scripts/*.py"],
        capture_output=True, text=True,
    ).stdout.split()

    offenders = []
    for rel in files:
        path = repo / rel
        if not path.exists():
            continue
        for node in ast.walk(ast.parse(path.read_text(errors="ignore"))):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "spec_from_file_location":
                offenders.append(rel)
                break

    assert offenders == ["scripts/_shared.py"], (
        f"hand-rolled script loaders outside _shared: "
        f"{[f for f in offenders if f != 'scripts/_shared.py']}. "
        f"Use `from _shared import load_script`."
    )
