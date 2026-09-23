"""
scripts/test/test_installer_templates.py — an installed machine has every
template the code reads (.agent-rfc/designs/installed-architectures.md).

`install-ai-stack.sh` copies `templates/<name>` into `~/.agent-framework` by
name. `architectures.yaml` was added to the code and not to that list, so
`--architecture` worked only where `AGENTSMITH_DIR` pointed at a checkout —
which is how every test ran it. This reads the names out of the code that loads
them, so the next template added is covered without anyone remembering.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER = (REPO / "install-ai-stack.sh").read_text(encoding="utf-8")
# A `cp` line naming the path — not a mention of it, which a comment satisfies.
_COPIES = [line for line in INSTALLER.splitlines() if line.strip().startswith(("cp ", "cp -r "))]


def _is_copied(fragment: str) -> bool:
    return any(fragment in line for line in _COPIES)

# `templates/<name>.yaml|json` as the code names it, whether written as a path
# or built up ("templates" / "architectures.yaml").
_BY_PATH = re.compile(r"""templates/([A-Za-z0-9_.-]+\.(?:yaml|json))""")
_BY_PARTS = re.compile(r"""["']templates["']\s*/\s*["']([A-Za-z0-9_.-]+\.(?:yaml|json))["']""")
# A `templates/` inside another tree — `fixtures/security/templates/` — belongs
# to that tree, and the installer ships it whole. Only the framework's own
# `templates/`, copied file by file, is this test's business.
_NESTED = ("fixtures", "security", "shared")


def _framework_templates(line: str) -> set[str]:
    if any(part in line for part in _NESTED):
        return set()
    return set(_BY_PATH.findall(line)) | set(_BY_PARTS.findall(line))


def _templates_the_code_reads() -> set[str]:
    names: set[str] = set()
    for source in [*(REPO / "runtime").rglob("*.py"), *(REPO / "scripts").glob("*.py")]:
        if "/test" in source.as_posix():
            continue
        for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
            names |= _framework_templates(line)
    return names


def test_the_code_reads_the_templates_this_test_is_about():
    """A guard on the guard: if the regexes stop matching, the test below passes
    for the wrong reason."""
    found = _templates_the_code_reads()
    assert {"agent-rules.yaml", "governance.json", "architectures.yaml"} <= found, found
    assert "risk_register.yaml" not in found, "fixtures/security/templates/ is shipped whole, not by name"


def test_the_installer_copies_every_template_the_code_reads():
    missing = sorted(name for name in _templates_the_code_reads() if not _is_copied(f"templates/{name}"))
    assert not missing, (
        f"install-ai-stack.sh never copies {missing} into ~/.agent-framework/templates/, so an "
        "installed machine (not a checkout) fails when the code reads it"
    )


# ── The gate's own hooks (.agent-rfc/designs/installed-architectures.md) ─────
# `tenant init` and `tenant adopt` copy .githooks/* out of the framework and arm
# core.hooksPath. An installed machine had no .githooks/ at all, so they armed an
# empty directory: no gates, and not the machine's hooks either.

GATE_HOOKS = ("process-gate", "commit-msg", "pre-commit", "pre-push", "chain")


def test_the_installer_copies_the_gate_hooks():
    assert _is_copied(".githooks"), (
        "install-ai-stack.sh never copies .githooks/ into ~/.agent-framework, so `agentsmith tenant "
        "init`/`adopt` on an installed machine arm an empty hooks directory"
    )


def test_the_release_ships_the_gate_hooks():
    """An install from a release downloads what it cannot copy."""
    release = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "githooks.tar.gz" in release
    assert "githooks.tar.gz" in INSTALLER, "the installer never fetches the archive the release builds"
    assert "/releases/latest/download/githooks.tar.gz" in INSTALLER


def test_every_gate_hook_exists_to_be_copied():
    missing = [h for h in GATE_HOOKS if not (REPO / ".githooks" / h).is_file()]
    assert not missing, missing
