"""
scripts/test/test_security_moderation_declared.py — SEC-MOD-001 accepts a
declared tenant classifier (TestbedFeedback-2026-07-21 G10).

`MODERATION_HOOK=required` used to fail unconditionally, so the guidance
telling regulated tenants to set it pointed at the one value that made
their strict CI un-passable. The runner now imports the declared hook and
smoke-tests the tenant's OWN classifier — turning the control from "the
framework API exists" into "this tenant has a working classifier".
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from runtime import moderation as mod  # noqa: E402
from security.registry import ControlSpec, FrameworkTags  # noqa: E402
from security.runners.moderation_hook import run as run_moderation  # noqa: E402


def _control() -> ControlSpec:
    return ControlSpec(
        id="SEC-MOD-001",
        title="Output moderation hook",
        status="met",
        owner="tenant",
        frameworks=FrameworkTags(owasp=["LLM01"], nist=["MAP 2.6"], atlas=[], iso42001=[9]),
        runner="moderation_hook",
        check_type="unit",
        mechanism="runtime/moderation.py",
    )


@pytest.fixture(autouse=True)
def _clean():
    mod.reset_output_moderator()
    yield
    mod.reset_output_moderator()


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / "tenant_clf.py").write_text(
        textwrap.dedent(
            """
            from runtime.moderation import ModerationResult

            def classify(text: str) -> ModerationResult:
                bad = "forbidden" in text.lower()
                return ModerationResult(allowed=not bad, reasons=["policy"] if bad else [])

            def blocks_everything(text: str) -> ModerationResult:
                return ModerationResult(allowed=False, reasons=["always"])

            def explodes(text: str) -> ModerationResult:
                raise RuntimeError("classifier is broken")

            def wrong_shape(text: str):
                return True
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    monkeypatch.setenv("MODERATION_HOOK", "required")
    return tmp_path


def _declare(repo: Path, hook: str) -> None:
    (repo / ".agenticframework" / "tenant.yaml").write_text(
        f"tenant:\n  id: t\nmoderation:\n  hook: \"{hook}\"\n"
    )


def test_required_passes_with_a_working_declared_classifier(tenant):
    _declare(tenant, "tenant_clf:classify")
    result = run_moderation(_control(), {"root": REPO})
    assert result.status == "pass"
    assert "tenant_clf:classify" in result.message
    assert result.evidence["hook"] == "tenant_clf:classify"


def test_required_fails_when_nothing_is_declared(tenant):
    result = run_moderation(_control(), {"root": REPO})
    assert result.status == "fail"
    assert "no hook declared" in result.message


def test_required_fails_on_an_unimportable_hook(tenant):
    _declare(tenant, "nope:missing")
    result = run_moderation(_control(), {"root": REPO})
    assert result.status == "fail"
    assert "unusable" in result.message


def test_required_fails_when_the_classifier_raises(tenant):
    _declare(tenant, "tenant_clf:explodes")
    result = run_moderation(_control(), {"root": REPO})
    assert result.status == "fail"
    assert "raised on benign text" in result.message


def test_required_fails_a_classifier_that_blocks_everything(tenant):
    """A block-everything stub would otherwise 'pass' the control while
    making the app unusable — that is not evidence of moderation."""
    _declare(tenant, "tenant_clf:blocks_everything")
    result = run_moderation(_control(), {"root": REPO})
    assert result.status == "fail"
    assert "blocked benign text" in result.message


def test_required_fails_on_wrong_return_shape(tenant):
    _declare(tenant, "tenant_clf:wrong_shape")
    result = run_moderation(_control(), {"root": REPO})
    assert result.status == "fail"


def test_optional_still_passes_without_a_declaration(tenant, monkeypatch):
    monkeypatch.setenv("MODERATION_HOOK", "optional")
    assert run_moderation(_control(), {"root": REPO}).status == "pass"


def test_runner_leaves_no_moderator_registered(tenant):
    """The runner must not leak its imported classifier into the process
    that runs the remaining controls."""
    _declare(tenant, "tenant_clf:classify")
    run_moderation(_control(), {"root": REPO})
    assert mod.get_output_moderator() is None
