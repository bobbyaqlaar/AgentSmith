"""
scripts/test/test_hook_visibility_override.py — AGENTSMITH_TENANT_VISIBILITY
declares what the caller knows the repository to be, and the hook believes it.

The scratch tenants were flipped public on 2026-09-27 so their CI would run on
free standard-runner minutes. The hook then correctly gitignored CLAUDE.md,
.cursorrules and friends — leaving five fixtures on the opposite branch of the
visibility decision from every tenant they stand in for, since a real tenant is
private and tracks those files. Declaring the visibility keeps the fixture
faithful without tying it to where it is hosted
(.agent-rfc/designs/tenant-visibility-override.md).

Both directions are asserted: an override that only ever suppressed the append
would pass a private-only test while being indistinguishable from deleting the
feature.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "hooks" / "post-checkout"
BUILD = REPO / ".github" / "scratch-tenants" / "build.sh"
MARKER = "# AgentSmith — IDE configs (system prompt content)"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="git and bash required"
)


def _tenant(tmp_path: Path, monkeypatch, gh_visibility: str) -> Path:
    """A provisionable repo with a github.com remote and a `gh` that answers
    `gh_visibility` — so a test states the answer the hook would detect, and the
    override is proven to win over it rather than merely to agree with it."""
    home = tmp_path / "home"
    (home / ".agent-framework").mkdir(parents=True)
    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "gh").write_text(f'#!/bin/sh\necho "{gh_visibility}"\n')
    (shim / "gh").chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)
    monkeypatch.delenv("AGENTSMITH_TENANT_VISIBILITY", raising=False)

    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/example/tenant.git"],
        check=True,
    )
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "enabled").touch()
    return repo


def _run(repo: Path) -> str:
    result = subprocess.run(
        ["bash", str(HOOK)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize("declared", ["private", "PRIVATE", "internal", "INTERNAL"])
def test_declared_private_keeps_ide_configs_tracked_on_a_public_repo(tmp_path, monkeypatch, declared):
    """The scratch-tenant case: gh says PUBLIC, the caller says private, and the
    IDE config files stay tracked. Fails before the override existed.

    `internal` is accepted and counts as private, as it does in `gh repo view`;
    it is parametrised here because docs/UserManual.md documents it, and a
    documented value with nothing reading it is the gap this repo keeps finding.
    """
    repo = _tenant(tmp_path, monkeypatch, "PUBLIC")
    monkeypatch.setenv("AGENTSMITH_TENANT_VISIBILITY", declared)
    out = _run(repo)
    assert not (repo / ".gitignore").exists(), "declared private must not create a .gitignore"
    assert f"Visibility declared {declared}" in out, "the override must say it took effect"


def test_declared_public_appends_on_a_private_repo(tmp_path, monkeypatch):
    """The other direction, so the override cannot pass as a no-op: gh says
    PRIVATE, the caller says public, and the block is appended."""
    repo = _tenant(tmp_path, monkeypatch, "PRIVATE")
    monkeypatch.setenv("AGENTSMITH_TENANT_VISIBILITY", "public")
    out = _run(repo)
    assert MARKER in (repo / ".gitignore").read_text()
    assert "Visibility declared public" in out


def test_unrecognised_value_warns_and_falls_back_to_detection(tmp_path, monkeypatch):
    """Neither silently private nor silently public. The ⚠️ starts in column 0,
    which is what .github/scratch-tenants/build.sh fails the build on."""
    repo = _tenant(tmp_path, monkeypatch, "PRIVATE")
    monkeypatch.setenv("AGENTSMITH_TENANT_VISIBILITY", "privte")
    out = _run(repo)
    assert any(line.startswith("⚠️") and "AGENTSMITH_TENANT_VISIBILITY" in line for line in out.splitlines()), out
    # Fell back to detection, which said PRIVATE — not to a guess.
    assert not (repo / ".gitignore").exists()


def test_confirmed_public_does_not_blame_gh(tmp_path, monkeypatch):
    """gh answered PUBLIC: the message must not send the reader to their gh auth.
    That sentence belongs to the case where gh could not answer at all, which
    test_hook_gitignore_idempotent.py pins."""
    repo = _tenant(tmp_path, monkeypatch, "PUBLIC")
    out = _run(repo)
    assert MARKER in (repo / ".gitignore").read_text()
    assert "confirmed via gh" in out
    assert "Could not confirm" not in out


def test_build_sh_declares_the_visibility_it_needs():
    """The fixture builder must keep declaring the intent; dropping the export
    silently returns the five scratch tenants to the public branch."""
    text = BUILD.read_text()
    assert "export AGENTSMITH_TENANT_VISIBILITY=private" in text
    assert text.index("export AGENTSMITH_TENANT_VISIBILITY=private") < text.index('bash "$HOOK"'), (
        "the declaration has to precede the hook it is declared for"
    )


def _appended_blocks() -> list[list[str]]:
    """The paths each append block writes, one list per block. Each block is the
    run of `echo` lines from its marker line to the `} >>` that closes it \u2014 read
    out of the hook rather than copied here, so a path added to the hook and not
    to the prompt, or to one block and not the other, fails."""
    lines = HOOK.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == f'echo "{MARKER}"']
    assert starts, "no append block found \u2014 this test would pass by matching nothing"
    out = []
    for i in starts:
        paths = []
        for line in lines[i + 1 :]:
            if ">>" in line and "GITIGNORE" in line:
                break
            stripped = line.strip()
            if stripped.startswith('echo "'):
                paths.append(stripped.split('"')[1])
        out.append(paths)
    return out


def test_both_append_blocks_ignore_the_same_paths():
    """The list exists twice — the interactive branch and the CI branch — and the
    two must not drift. There is no third place to move it to that a shell hook
    with no helper functions would make clearer."""
    blocks = _appended_blocks()
    assert len(blocks) == 2, f"expected an interactive and a non-interactive block, got {len(blocks)}"
    assert blocks[0] == blocks[1], f"the two append blocks disagree: {blocks}"
    assert len(blocks[0]) == 7, blocks[0]


def test_the_prompt_names_every_path_it_would_ignore():
    """Consent has to cover the action. The prompt listed six of the seven paths
    the block appends — .agent-history.log was ignored without ever being named —
    so answering "y" agreed to less than it got."""
    lines = HOOK.read_text().splitlines()
    first = next(i for i, line in enumerate(lines) if "[ -t 1 ]; then" in line)
    last = next(i for i, line in enumerate(lines) if "GITIGNORE_CHOICE" in line)
    # What the hook PRINTS, not the source of those lines: the first version of
    # this test sliced the region as text, and the comment above the prompt
    # mentions .agent-history.log \u2014 so removing that path from the prompt left the
    # test passing on a comment. Proven by making the cut and watching it pass.
    printed = " ".join(
        line.strip().split('"')[1]
        for line in lines[first : last + 1]
        if line.strip().startswith(('echo "', 'read -r -p "'))
    )
    missing = [path for path in _appended_blocks()[0] if path not in printed]
    assert not missing, f"the prompt does not name what it would ignore: {missing}"
