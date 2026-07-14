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
