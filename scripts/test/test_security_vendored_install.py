"""
scripts/test/test_security_vendored_install.py — controls that verify the
framework's OWN components are `not applicable` in a vendored tenant, and
still fail in the framework checkout.

Found auditing AqlaarTeleologyStudio (2026-09-13): its strict harness reported
fail=9, and three of those were `missing portal files` (SEC-AUDIT-001,
SEC-RBAC-001, SEC-SSO-001) plus one `hooks/pre-commit: No such file`
(SEC-CHANGE-001). A tenant gets scripts/, runtime/ and fixtures/security/
vendored into its own tree — never portal/ or hooks/ — so those were
structural absences reported as compliance failures. `--mode smoke` includes
SEC-AUDIT-001, so every tenant's eval-security.yml smoke step failed too.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from security.registry import ControlSpec, FrameworkTags
from security.runners import delegating
from security.runners.sso_revocation import run as run_sso


def _control(control_id: str, runner: str) -> ControlSpec:
    return ControlSpec(
        id=control_id,
        title=control_id,
        status="met",
        owner="framework",
        frameworks=FrameworkTags(owasp=[], nist=[], atlas=[], iso42001=[]),
        runner=runner,
        check_type="unit",
        mechanism="portal/",
    )


def _ctx(root: Path) -> dict:
    return {"root": root, "tenant_root": root, "tenant_security": root / ".agent-rfc" / "security"}


@pytest.fixture()
def vendored_tenant(tmp_path: Path) -> Path:
    """What the hook leaves: vendored dirs, and no portal/ or hooks/."""
    for d in ("scripts", "runtime", "fixtures/security"):
        (tmp_path / d).mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def gutted_framework(tmp_path: Path) -> Path:
    """The framework's own checkout with portal/ and hooks/ deleted — the
    regression these controls exist to catch."""
    (tmp_path / "install-ai-stack.sh").write_text("#!/usr/bin/env bash\n")
    (tmp_path / "workflow-templates").mkdir()
    return tmp_path


CASES = [
    ("SEC-RBAC-001", "rbac_matrix", delegating.rbac_matrix),
    ("SEC-SSO-001", "sso_revocation", run_sso),
    ("SEC-CHANGE-001", "change_gates", delegating.change_gates),
]


@pytest.mark.parametrize(("control_id", "runner", "fn"), CASES)
def test_framework_component_controls_are_not_applicable_in_a_vendored_tenant(
    vendored_tenant: Path, control_id: str, runner: str, fn
) -> None:
    result = fn(_control(control_id, runner), _ctx(vendored_tenant))
    assert result.status == "skip", result.message
    assert result.message.startswith("not applicable"), result.message


@pytest.mark.parametrize(("control_id", "runner", "fn"), CASES)
def test_the_same_absence_still_fails_in_the_framework_checkout(
    gutted_framework: Path, control_id: str, runner: str, fn
) -> None:
    result = fn(_control(control_id, runner), _ctx(gutted_framework))
    assert result.status == "fail", result.message
