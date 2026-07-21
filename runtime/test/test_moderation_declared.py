"""
runtime/test/test_moderation_declared.py — declared moderation hook
(TestbedFeedback-2026-07-21 G10).

`MODERATION_HOOK=required` used to be unsatisfiable: the SEC-MOD-001 harness
runs in a different process from the worker, so an imperative
register_output_moderator() call was invisible to it and `required` failed
unconditionally — the one setting regulated tenants are told to use.

A committed declaration fixes that, but only if the RUNTIME loads the same
declaration the harness checks; otherwise CI would certify a config key
production ignores. These tests pin that binding.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime import moderation as mod  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    mod.reset_output_moderator()
    yield
    mod.reset_output_moderator()


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    """A tenant repo on sys.path with an importable classifier module."""
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / "tenant_mod.py").write_text(
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

            not_callable = "oops"
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _declare(repo: Path, hook: str) -> None:
    (repo / ".agenticframework" / "tenant.yaml").write_text(
        f"tenant:\n  id: t\nmoderation:\n  hook: \"{hook}\"\n"
    )


# ── declaration resolution ───────────────────────────────────────────────────


def test_undeclared_returns_none(tenant, monkeypatch):
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    assert mod.declared_hook_path() is None
    assert mod.load_declared_moderator() is None


def test_declared_in_tenant_yaml(tenant, monkeypatch):
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    _declare(tenant, "tenant_mod:classify")
    assert mod.declared_hook_path() == "tenant_mod:classify"
    assert mod.load_declared_moderator()("clean").allowed is True


def test_env_overrides_tenant_yaml(tenant, monkeypatch):
    _declare(tenant, "tenant_mod:classify")
    monkeypatch.setenv("MODERATION_HOOK_PATH", "tenant_mod:blocks_everything")
    assert mod.declared_hook_path() == "tenant_mod:blocks_everything"


@pytest.mark.parametrize(
    "hook,fragment",
    [
        ("tenant_mod.classify", "module.path:callable"),   # missing colon
        ("tenant_mod:missing", "has no attribute"),
        ("tenant_mod:not_callable", "not callable"),
        ("no_such_module:fn", "cannot import"),
    ],
)
def test_broken_declaration_is_loud(tenant, monkeypatch, hook, fragment):
    """A broken hook must never degrade to a silent skip — that would be a
    regulated tenant running unmoderated while CI looked green."""
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    _declare(tenant, hook)
    with pytest.raises(mod.ModerationHookImportError, match=fragment):
        mod.load_declared_moderator()


# ── runtime binds to the same declaration ────────────────────────────────────


def test_runtime_auto_registers_the_declared_hook(tenant, monkeypatch):
    """The binding that makes the harness check meaningful."""
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    monkeypatch.setenv("MODERATION_HOOK", "required")
    _declare(tenant, "tenant_mod:classify")

    assert mod.get_output_moderator() is None            # nothing imperative
    result = mod.apply_output_moderation("forbidden content")
    assert result.allowed is False                        # declared hook ran
    assert mod.get_output_moderator() is not None         # and stayed registered


def test_required_still_raises_without_a_declaration(tenant, monkeypatch):
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    monkeypatch.setenv("MODERATION_HOOK", "required")
    with pytest.raises(mod.ModerationHookRequiredError):
        mod.apply_output_moderation("anything")


def test_use_declared_false_isolates_the_harness_assertion(tenant, monkeypatch):
    """The runner proves `required` rejects a hook-less tenant; that check
    must not be defeated by a tenant that HAS declared one."""
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    _declare(tenant, "tenant_mod:classify")
    with pytest.raises(mod.ModerationHookRequiredError):
        mod.apply_output_moderation("x", mode="required", use_declared=False)


def test_imperative_registration_wins(tenant, monkeypatch):
    """A worker that registers explicitly is not overridden by config."""
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    _declare(tenant, "tenant_mod:blocks_everything")
    mod.register_output_moderator(
        lambda t: mod.ModerationResult(allowed=True, reasons=[])
    )
    assert mod.apply_output_moderation("forbidden").allowed is True


def test_off_mode_never_loads_the_declaration(tenant, monkeypatch):
    monkeypatch.delenv("MODERATION_HOOK_PATH", raising=False)
    monkeypatch.setenv("MODERATION_HOOK", "off")
    _declare(tenant, "tenant_mod:blocks_everything")
    assert mod.apply_output_moderation("forbidden").allowed is True
    assert mod.get_output_moderator() is None
