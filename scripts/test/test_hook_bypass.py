"""
scripts/test/test_hook_bypass.py — the four git hooks let the org policy decide
a bypass, instead of exiting on `DISABLE_AI_STACK=true` unconditionally.

`hooks.bypass_policy` (enterprise/README.md) was read by `ai-stack-off` alone;
`DISABLE_AI_STACK=true git commit` skipped every hook whatever the policy said,
and pre-commit printed that command as the way to do it. Each hook now runs one
shared block: no policy → the bypass is granted (a developer machine, as
before); a policy → `agentsmith hooks bypass-check` decides, and when it
refuses or cannot run, the hook enforces.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS = ("pre-commit", "commit-msg", "post-commit", "post-checkout")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

_BLOCK = re.compile(r"^# ── Bypass ─+\n.*?^fi\n", re.S | re.M)


def _block(hook: str) -> str:
    m = _BLOCK.search((REPO / "hooks" / hook).read_text(encoding="utf-8"))
    assert m, f"hooks/{hook} has no bypass block"
    return m.group(0)


def test_all_four_hooks_share_one_bypass_block_and_nothing_else_exits_on_the_variable():
    blocks = {hook: _block(hook) for hook in HOOKS}
    assert len(set(blocks.values())) == 1, "the hooks' bypass blocks differ"
    for hook in HOOKS:
        text = (REPO / "hooks" / hook).read_text(encoding="utf-8")
        assert text.index(blocks[hook]) < text.index("REPO_ROOT") if "REPO_ROOT" in text else True
        outside = text.replace(blocks[hook], "")
        assert not re.search(r'DISABLE_AI_STACK:-false\}" = "true" \]; then exit 0', outside), (
            f"hooks/{hook} still exits on DISABLE_AI_STACK without asking the policy"
        )


def _run(tmp_path: Path, *, env: dict[str, str], policy: str | None = None, checker: str | None = None):
    home = tmp_path / "home"
    fw = home / ".agent-framework"
    (fw / "state").mkdir(parents=True, exist_ok=True)
    if policy is not None:
        (fw / "agenticframework-org.yaml").write_text(policy)
    if checker is not None:
        (fw / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
        stub = fw / ".venv" / "bin" / "agentsmith"
        stub.write_text("#!/bin/bash\n" + checker)
        stub.chmod(0o755)
    script = _block("pre-commit") + 'echo "HOOK RAN"\n'
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=False,
        env={"PATH": os.environ["PATH"], "HOME": str(home), **env},
    )


def test_no_bypass_requested_the_hook_runs(tmp_path):
    assert "HOOK RAN" in _run(tmp_path, env={}).stdout


def test_without_a_policy_the_variable_bypasses(tmp_path):
    result = _run(tmp_path, env={"DISABLE_AI_STACK": "true"})
    assert result.returncode == 0 and "HOOK RAN" not in result.stdout


def test_without_a_policy_a_disabled_mode_file_bypasses(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "mode").write_text("disabled\n")
    result = _run(tmp_path, env={"AGENTSMITH_STATE_DIR": str(state)})
    assert result.returncode == 0 and "HOOK RAN" not in result.stdout


@pytest.mark.parametrize("word", ["local", "hybrid", "garbage"])
def test_any_other_mode_does_not_bypass(tmp_path, word):
    state = tmp_path / "state"
    state.mkdir()
    (state / "mode").write_text(word)
    assert "HOOK RAN" in _run(tmp_path, env={"AGENTSMITH_STATE_DIR": str(state)}).stdout


def test_with_a_policy_the_checker_decides_yes(tmp_path):
    result = _run(tmp_path, env={"DISABLE_AI_STACK": "true"}, policy="hooks:\n  bypass_policy: break-glass\n",
                  checker='[ "$*" = "hooks bypass-check" ] && exit 0; exit 9\n')
    assert result.returncode == 0 and "HOOK RAN" not in result.stdout


def test_with_a_policy_the_checker_decides_no_and_the_hook_enforces(tmp_path):
    result = _run(tmp_path, env={"DISABLE_AI_STACK": "true"}, policy="hooks:\n  bypass_policy: disabled\n",
                  checker="exit 1\n")
    assert "HOOK RAN" in result.stdout
    assert "bypass refused" in result.stderr


def test_with_a_policy_and_no_checker_installed_the_hook_enforces(tmp_path):
    """guards-must-be-able-to-fail: the check failing to RUN must not read as a yes."""
    result = _run(tmp_path, env={"DISABLE_AI_STACK": "true"}, policy="hooks:\n  bypass_policy: disabled\n")
    assert "HOOK RAN" in result.stdout
    assert "bypass refused" in result.stderr


def test_end_to_end_a_disabled_policy_refuses_through_the_real_command_and_records_it(tmp_path):
    checker = f'PYTHONPATH="{REPO}" exec "{sys.executable}" -P -m runtime.cli "$@"\n'
    result = _run(tmp_path, env={"DISABLE_AI_STACK": "true", "AGENT_OWNER_ID": "dev@example.com"},
                  policy='hooks:\n  bypass_policy: disabled\n  break_glass_approvers: ["it@example.com"]\n',
                  checker=checker)
    assert "HOOK RAN" in result.stdout, result.stderr
    assert "bypass is DISABLED" in result.stderr and "it@example.com" in result.stderr
    log = (tmp_path / "home" / ".agent-framework" / "local-audit-fallback.log").read_text()
    assert '"eventType": "hook_bypass"' in log and '"result": "denied"' in log and "dev@example.com" in log
