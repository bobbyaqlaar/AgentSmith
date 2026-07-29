"""
scripts/test/test_version_consistency.py — the framework's version is declared
in three places that nothing kept in step.

SPECS.md's header claimed "**Version:** 1.0.0 (matches `install-ai-stack.sh`'s
`FRAMEWORK_VERSION` — the single version source)" while `FRAMEWORK_VERSION` was
`1.1.0` and `pyproject.toml` was `1.1.0`. The parenthetical asserting they match
is what makes this worth a test rather than a one-off correction: the document
told readers the invariant held, so nobody checked it.

A wrong version here is not cosmetic — `ai-stack-upgrade --to <version>` and a
tenant's pinned `agentsmith-runtime @ vX.Y.Z` both resolve against real tags.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_SEMVER = r"(\d+\.\d+\.\d+)"


def _installer_version() -> str:
    m = re.search(rf'^FRAMEWORK_VERSION="{_SEMVER}"', (REPO / "install-ai-stack.sh").read_text(encoding="utf-8"), re.M)
    assert m, "FRAMEWORK_VERSION not found in install-ai-stack.sh"
    return m.group(1)


def _pyproject_version() -> str:
    m = re.search(rf'^version = "{_SEMVER}"', (REPO / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert m, "version not found in pyproject.toml"
    return m.group(1)


def _specs_version() -> str:
    m = re.search(rf"\*\*Version:\*\*\s*{_SEMVER}", (REPO / "SPECS.md").read_text(encoding="utf-8"))
    assert m, "**Version:** header not found in SPECS.md"
    return m.group(1)


def test_installer_and_package_agree() -> None:
    """`pip install agentsmith-runtime` and the shell installer must describe
    the same release, or a tenant's pin and its vendored scripts diverge."""
    assert _installer_version() == _pyproject_version(), (
        f"install-ai-stack.sh FRAMEWORK_VERSION={_installer_version()} but "
        f"pyproject.toml version={_pyproject_version()}"
    )


def test_specs_header_matches_the_installer() -> None:
    """SPECS.md's header explicitly claims to match FRAMEWORK_VERSION."""
    assert _specs_version() == _installer_version(), (
        f"SPECS.md declares {_specs_version()} while FRAMEWORK_VERSION is "
        f"{_installer_version()} — the header claims these match"
    )


def test_changelog_has_an_entry_for_the_current_version() -> None:
    """A version bump with no release notes ships a tag nobody can read."""
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    version = _installer_version()
    assert f"[{version}]" in changelog, (
        f"CHANGELOG.md has no `[{version}]` section for the current "
        f"FRAMEWORK_VERSION — add one before tagging"
    )
