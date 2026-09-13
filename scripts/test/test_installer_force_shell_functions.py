"""
scripts/test/test_installer_force_shell_functions.py — `install-ai-stack.sh
--force` replaces the managed shell-function block.

The installer skipped Step 7 whenever the profile already had AgentSmith
functions, telling the user to "re-run with --force to overwrite" — and nothing
read --force. A re-install could therefore never update ai-stack-upgrade,
ai-tenant-init and the rest: the machine this was found on still ran the
v1.0.0 block, missing every upgrade fix since.

Runs the real Step 7 section of the installer against a fake profile, with the
installer's output helpers stubbed, so the test does not perform an install.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

USER_BEFORE = "export PATH=/opt/mine/bin:$PATH\n"
USER_AFTER = "alias ll='ls -la'\n"
OLD_BLOCK = (
    "# >>> AgentSmith managed block — DO NOT EDIT, removed by ai-stack-uninstall >>>\n"
    "# AI AGENT FRAMEWORK CONTROLLER — AgentSmith v1.0.0\n"
    "function ai-stack-upgrade() { echo old; }\n"
    "# <<< AgentSmith managed block <<<\n"
)


def _step7(force: bool, rc: Path) -> subprocess.CompletedProcess:
    text = (REPO / "install-ai-stack.sh").read_text(encoding="utf-8")
    m = re.search(r'^header "Step 7.*?(?=^header "Step 8)', text, re.S | re.M)
    assert m, "Step 7 section not found in install-ai-stack.sh"
    script = "\n".join([
        'header() { :; }; info() { echo "$*"; }; warn() { echo "$*"; }; success() { echo "$*"; }',
        f'SHELL_RC="{rc}"',
        f"FORCE_SHELL_FUNCTIONS={1 if force else 0}",
        m.group(0),
    ])
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)


def test_force_replaces_the_block_and_keeps_the_users_lines(tmp_path):
    rc = tmp_path / ".zshrc"
    rc.write_text(USER_BEFORE + OLD_BLOCK + USER_AFTER)

    result = _step7(True, rc)

    assert result.returncode == 0, result.stderr
    new = rc.read_text()
    assert new.startswith(USER_BEFORE) and USER_AFTER in new
    assert len(re.findall(r"^# >>> AgentSmith managed block", new, re.M)) == 1
    assert len(re.findall(r"^# <<< AgentSmith managed block <<<$", new, re.M)) == 1
    assert "echo old" not in new
    assert "depends on agentsmith-runtime as a package" in new, "the current ai-stack-upgrade was not written"
    assert (tmp_path / ".zshrc.agentsmith-bak").read_text() == USER_BEFORE + OLD_BLOCK + USER_AFTER


def test_without_force_an_existing_block_is_left_alone(tmp_path):
    rc = tmp_path / ".zshrc"
    rc.write_text(USER_BEFORE + OLD_BLOCK + USER_AFTER)

    result = _step7(False, rc)

    assert result.returncode == 0, result.stderr
    assert rc.read_text() == USER_BEFORE + OLD_BLOCK + USER_AFTER
    assert "already present" in result.stdout


def test_force_will_not_edit_a_block_without_markers(tmp_path):
    rc = tmp_path / ".zshrc"
    legacy = "# AI AGENT FRAMEWORK CONTROLLER — pre-marker install\nfunction ai-stack-upgrade() { echo old; }\n"
    rc.write_text(USER_BEFORE + legacy)

    result = _step7(True, rc)

    assert rc.read_text() == USER_BEFORE + legacy
    assert "not editing it blind" in result.stdout


def test_uninstall_removes_the_whole_block_it_installed(tmp_path):
    """The installed block contains the marker text inside ai-stack-uninstall's
    own sed pattern. Unanchored, the delete range ended on that line and left
    the rest of the block in the profile; this applies the uninstall's real sed
    expressions to the real block."""
    text = (REPO / "install-ai-stack.sh").read_text(encoding="utf-8")
    block = re.search(r"^# >>> AgentSmith managed block.*?^# <<< AgentSmith managed block <<<\n", text, re.S | re.M)
    exprs = re.findall(r"sed -i\.af-uninstall-bak '([^']+)'", text)
    assert block and exprs
    rc = tmp_path / ".zshrc"
    rc.write_text(USER_BEFORE + block.group(0) + USER_AFTER)

    for expr in exprs:
        subprocess.run(["sed", "-i.bak", expr, str(rc)], check=True)

    assert rc.read_text() == USER_BEFORE + USER_AFTER

