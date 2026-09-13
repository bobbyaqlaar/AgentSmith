"""
scripts/test/test_hook_gitignore_idempotent.py — the post-checkout hook adds its
IDE-config block to .gitignore once per repository, not once per checkout.

When the hook cannot confirm a github.com repository is private (gh missing or
unauthenticated), it treats it as public and, non-interactively, appends a block
ignoring CLAUDE.md, .cursorrules and friends. There was no "already there?"
check: every checkout appended another copy. Found in the three scratch tenants,
whose .gitignore files carried the block up to three times over after
re-provisioning runs where gh was not signed in.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "hooks" / "post-checkout"
MARKER = "# AgentSmith — IDE configs (system prompt content)"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="git and bash required"
)


def test_repeated_checkouts_add_the_ide_block_once(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".agent-framework").mkdir(parents=True)
    # A gh that cannot answer: visibility unknown, so the hook assumes public.
    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "gh").write_text("#!/bin/sh\nexit 1\n")
    (shim / "gh").chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)

    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/example/tenant.git"], check=True
    )
    (repo / ".gitignore").write_text("node_modules\n")
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "enabled").touch()

    outputs = []
    for _ in range(3):
        result = subprocess.run(
            ["bash", str(HOOK)], cwd=repo, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL
        )
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout)

    text = (repo / ".gitignore").read_text()
    assert text.startswith("node_modules\n")
    assert text.count(MARKER) == 1, text
    assert "Could not confirm this repo is private" in outputs[0], "the append must not be silent"
    assert "Could not confirm" not in outputs[1] + outputs[2]
