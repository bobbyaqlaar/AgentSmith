"""
scripts/test/test_vouched_files.py — a skip is granted only by a hash that matched.

`scripts/vouched_files.py` tells `hooks/pre-commit` which staged files AgentSmith
wrote and the tenant has not touched, so the guardrails can skip them
(.agent-rfc/designs/scaffold-rfc-and-vouched-skip.md). Every way it can fail has
to produce an EMPTY list, because an empty list means "check everything" — the
behaviour before it existed. A bug here must be able to make the hook stricter,
never laxer.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from test_process_gate import REPO, needs_git

pytestmark = needs_git

HELPER = REPO / "scripts" / "vouched_files.py"


def _repo(tmp_path: Path, files: dict[str, str], manifest: object | None) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    if manifest is not None:
        (root / ".agenticframework").mkdir(exist_ok=True)
        body = manifest if isinstance(manifest, str) else json.dumps(manifest)
        (root / ".agenticframework" / "scaffold.json").write_text(body)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return root


def _vouched(root: Path) -> list[str]:
    done = subprocess.run([sys.executable, str(HELPER)], cwd=str(root), capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    return done.stdout.split()


def _manifest(root_files: dict[str, str]) -> dict:
    return {"files": {rel: hashlib.sha256(text.encode("utf-8")).hexdigest() for rel, text in root_files.items()}}


def test_a_file_the_manifest_records_unchanged_is_vouched(tmp_path):
    files = {"scripts/a.py": "print(1)\n", "mine.py": "print(2)\n"}
    root = _repo(tmp_path, files, _manifest({"scripts/a.py": files["scripts/a.py"]}))

    assert _vouched(root) == ["scripts/a.py"], "only the recorded file, and only it"


def test_an_edited_file_loses_its_vouch(tmp_path):
    """The property that makes the skip safe: it is a hash match, not a path
    allowlist. This is the mutation to beat."""
    files = {"scripts/a.py": "print(1)\n"}
    root = _repo(tmp_path, files, _manifest({"scripts/a.py": "print(ORIGINAL)\n"}))

    assert _vouched(root) == [], "a file that differs from the manifest must be checked"


def test_a_staged_edit_after_add_is_judged_on_the_staged_copy(tmp_path):
    """The hook checks what is about to be committed, so the vouch must be about
    the staged blob — not the working tree, which may have moved on."""
    files = {"scripts/a.py": "print(1)\n"}
    root = _repo(tmp_path, files, _manifest(files))
    assert _vouched(root) == ["scripts/a.py"]

    (root / "scripts" / "a.py").write_text("print(99)\n")  # worktree only, not staged

    assert _vouched(root) == ["scripts/a.py"], "the staged copy is still what AgentSmith wrote"


def test_no_manifest_vouches_for_nothing(tmp_path):
    root = _repo(tmp_path, {"scripts/a.py": "print(1)\n"}, None)
    assert _vouched(root) == []


def test_an_unparseable_manifest_vouches_for_nothing(tmp_path):
    root = _repo(tmp_path, {"scripts/a.py": "print(1)\n"}, "{ not json")
    assert _vouched(root) == []


def test_a_manifest_that_is_not_a_mapping_vouches_for_nothing(tmp_path):
    root = _repo(tmp_path, {"scripts/a.py": "print(1)\n"}, {"files": ["scripts/a.py"]})
    assert _vouched(root) == []


def test_a_manifest_naming_an_unstaged_path_grants_nothing(tmp_path):
    """The manifest is repository content. It must not be able to vouch for a
    file this commit does not contain."""
    files = {"scripts/a.py": "print(1)\n"}
    manifest = _manifest(files)
    manifest["files"]["../outside.py"] = "0" * 64
    manifest["files"]["scripts/never-staged.py"] = "0" * 64
    root = _repo(tmp_path, files, manifest)

    assert _vouched(root) == ["scripts/a.py"]


def test_outside_a_git_repository_it_says_nothing(tmp_path):
    done = subprocess.run([sys.executable, str(HELPER)], cwd=str(tmp_path), capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == ""
