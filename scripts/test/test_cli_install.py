"""
scripts/test/test_cli_install.py — the installer puts `agentsmith` on the
machine and takes the old shell functions off it.

install-ai-stack.sh appended 18 functions to ~/.zshrc (.agent-rfc/designs/
agentsmith-cli.md). They reached interactive shells only, and re-installing
skipped them unless --force, so machines ran stale copies. Step 7 now records
machine state and removes that block; the commands are `agentsmith <command>`.

fixtures/legacy_profile_block.zshrc is the block exactly as the last installer
that wrote it did — including the blank line before it and the marker text
inside its own uninstall's sed pattern, the two things that broke earlier
removals.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from runtime.cli import build_parser
from runtime.machine.ops import remove_profile_blocks

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install-ai-stack.sh"
LEGACY_BLOCK = (Path(__file__).parent / "fixtures" / "legacy_profile_block.zshrc").read_text(encoding="utf-8")

USER_BEFORE = "export PATH=/opt/mine/bin:$PATH\n"
USER_AFTER = "alias ll='ls -la'\n"

bash_required = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


# ── removing the legacy block ───────────────────────────────────────────────


def test_the_real_legacy_block_is_removed_and_the_users_lines_kept(tmp_path):
    assert LEGACY_BLOCK.startswith("\n# >>> AgentSmith managed block"), "fixture no longer matches what was installed"
    rc = tmp_path / ".zshrc"
    original = USER_BEFORE + LEGACY_BLOCK + USER_AFTER
    rc.write_text(original)
    said: list[str] = []

    assert remove_profile_blocks(tmp_path, out=said.append) == 0

    assert rc.read_text() == USER_BEFORE + USER_AFTER, "block (or its leading blank line) left behind"
    assert (tmp_path / ".zshrc.agentsmith-bak").read_text() == original
    assert any("Removed" in s for s in said)


def test_two_blocks_from_repeated_installs_and_the_old_name_are_all_removed(tmp_path):
    old_name = LEGACY_BLOCK.replace("AgentSmith managed block", "AgenticFramework managed block")
    rc = tmp_path / ".bashrc"
    rc.write_text(USER_BEFORE + LEGACY_BLOCK + LEGACY_BLOCK + old_name + USER_AFTER)

    assert remove_profile_blocks(tmp_path, out=lambda _: None) == 0

    assert rc.read_text() == USER_BEFORE + USER_AFTER


def test_a_block_without_an_end_marker_is_not_edited(tmp_path):
    truncated = LEGACY_BLOCK[: LEGACY_BLOCK.index("# <<< AgentSmith managed block <<<")]
    rc = tmp_path / ".zshrc"
    rc.write_text(USER_BEFORE + truncated)
    said: list[str] = []

    assert remove_profile_blocks(tmp_path, out=said.append) == 1

    assert rc.read_text() == USER_BEFORE + truncated
    assert not (tmp_path / ".zshrc.agentsmith-bak").exists()
    assert any("no end marker" in s for s in said)


def test_a_pre_marker_legacy_block_is_reported_not_edited(tmp_path):
    legacy = "# AI AGENT FRAMEWORK CONTROLLER — pre-marker install\nfunction ai-stack-upgrade() { echo old; }\n"
    rc = tmp_path / ".profile"
    rc.write_text(USER_BEFORE + legacy)
    said: list[str] = []

    assert remove_profile_blocks(tmp_path, out=said.append) == 1

    assert rc.read_text() == USER_BEFORE + legacy
    assert any("without managed-block markers" in s for s in said)


def test_nothing_to_remove_is_success_and_touches_nothing(tmp_path):
    rc = tmp_path / ".zshrc"
    rc.write_text(USER_BEFORE)
    assert remove_profile_blocks(tmp_path, out=lambda _: None) == 0
    assert rc.read_text() == USER_BEFORE
    assert not (tmp_path / ".zshrc.agentsmith-bak").exists()


# ── the installer ───────────────────────────────────────────────────────────


def _code(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def test_the_installer_writes_nothing_into_a_shell_profile():
    code = _code(INSTALLER)
    assert "SHELL_EOF" not in code and not re.search(r"^function ai-", code, re.M)
    assert "SHELL_RC" not in "".join(line for line in code.splitlines() if re.search(r">>|sed -i|> ", line)), (
        "the installer writes to the shell profile again"
    )


@bash_required
@pytest.mark.parametrize("mode", ["developer", "enterprise"])
def test_step7_records_the_install_mode_and_removes_the_block_via_the_command(tmp_path, mode):
    text = INSTALLER.read_text(encoding="utf-8")
    m = re.search(r'^header "Step 7.*?(?=^# ═+\n# SECTION 8)', text, re.S | re.M)
    assert m, "Step 7 section not found"
    venv = tmp_path / "fw" / ".venv"
    (venv / "bin").mkdir(parents=True)
    stub = venv / "bin" / "agentsmith"
    stub.write_text(f'#!/bin/bash\necho "$*" >> "{tmp_path}/calls"\n')
    stub.chmod(0o755)
    script = "\n".join([
        'header() { :; }; info() { echo "$*"; }; warn() { echo "$*"; }; success() { echo "$*"; }',
        f'FRAMEWORK_DIR="{tmp_path / "fw"}"; VENV_DIR="{venv}"; INSTALL_MODE="{mode}"',
        f'INSTALLER_DIR="{REPO}"; FORCE_FLAG_GIVEN=1',
        m.group(0),
    ])
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "fw" / "state" / "install-mode").read_text() == f"{mode}\n"
    assert (tmp_path / "calls").read_text() == "uninstall --legacy-profile-only\n"
    assert (tmp_path / "fw" / "shell" / "ai-compat.sh").is_file()
    assert "--force is no longer needed" in result.stdout


def test_step3_installs_the_command_without_re_resolving_dependencies_and_links_it():
    code = _code(INSTALLER)
    step3 = code[code.index('header "Step 3'):code.index('header "Step 4')]
    assert 'uv pip install --quiet --no-deps --reinstall --python "$VENV_PYTHON" "$AGENTSMITH_PACKAGE"' in step3
    assert '-m pip install --quiet --no-deps --force-reinstall "$AGENTSMITH_PACKAGE"' in step3
    assert step3.index("uv pip sync") < step3.index("uv pip install"), "a later sync would remove the package"
    assert 'ln -sfn "$VENV_DIR/bin/agentsmith" "$AGENTSMITH_BIN_DIR/agentsmith"' in step3


def test_verification_runs_the_command_through_its_link():
    code = _code(INSTALLER)
    step9 = code[code.index('header "Step 9'):]
    assert '"$AGENTSMITH_BIN_DIR/agentsmith" version' in step9


@pytest.mark.parametrize("path", [INSTALLER, *sorted((REPO / "hooks").iterdir())], ids=lambda p: p.name)
def test_no_output_string_runs_a_command_by_accident(path):
    """A backtick inside a double-quoted `echo`/`warn` is command substitution:
    `warn "… `agentsmith dashboard start` …"` STARTS the dashboard. Written
    while replacing ai-* names with `agentsmith …` in this file's messages."""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"\s*(echo|warn|info|error|success)\b", line) and re.search(r'"[^"]*(?<!\\)`[^"]*"', line):
            pytest.fail(f"{path.name}:{number} has an unescaped backtick in an output string: {line.strip()}")


# ── the optional ai-* wrappers ──────────────────────────────────────────────


Leaves = dict[tuple[str, ...], argparse.ArgumentParser]


def _leaf_paths(parser: argparse.ArgumentParser, path: tuple[str, ...] = ()) -> Leaves:
    subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subs:
        return {path: parser}
    found: Leaves = {}
    for action in subs:
        for name, child in action.choices.items():
            found.update(_leaf_paths(child, (*path, name)))
    return found


def test_every_compat_wrapper_names_a_real_command_and_real_options():
    text = (REPO / "templates" / "shell" / "ai-compat.sh").read_text(encoding="utf-8")
    wrappers = re.findall(r'^(ai-[a-z-]+)\(\)\s*\{\s*agentsmith ([^"]*)"\$@"; \}$', text, re.M)
    assert len(wrappers) == 17, f"expected one wrapper per removed shell function, found {len(wrappers)}"
    leaves = _leaf_paths(build_parser())
    for name, args in wrappers:
        tokens = args.split()
        path = next((tuple(tokens[:n]) for n in range(len(tokens), 0, -1) if tuple(tokens[:n]) in leaves), None)
        assert path, f"{name} calls `agentsmith {args}`, which is not a command"
        options = {s for action in leaves[path]._actions for s in action.option_strings}
        positional_choices = {c for action in leaves[path]._actions if not action.option_strings
                              for c in (action.choices or [])}
        for token in tokens[len(path):]:
            assert token in options or token in positional_choices, f"{name}: `{token}` is not valid for {path}"


# ── The manual's Command Reference is a second copy of the CLI surface ────────


def _reference_rows() -> dict[tuple[str, ...], str]:
    """{command path: every reference cell that documents it}.

    The args column contains escaped pipes (`shared\\|dedicated`), so the row is
    split on unescaped `|` only — splitting naively truncates the column and the
    check silently stops seeing most of it.
    """
    manual = (REPO / "docs" / "UserManual.md").read_text(encoding="utf-8")
    leaves = _leaf_paths(build_parser())
    rows: dict[tuple[str, ...], str] = {}
    for line in manual.splitlines():
        if not line.startswith("| `agentsmith "):
            continue
        cells = re.split(r"(?<!\\)\|", line)
        head = re.match(r"\s*`agentsmith ([^`]+)`", cells[1] or "")
        if not head:
            continue
        tokens = head.group(1).split()
        path = next((tuple(tokens[:n]) for n in range(len(tokens), 0, -1)
                     if tuple(tokens[:n]) in leaves), None)
        if path is None:
            continue
        rows[path] = rows.get(path, "") + " " + " ".join(cells[1:])
    return rows


# `agentsmith hooks` is described in build_parser as "internal: called by the git
# hooks", and the Command Reference is the DAILY command table, so its subcommand
# is documented in prose (docs/UserManual.md § Bypass policy enforcement) instead
# of a row. Pinned rather than filtered: a new internal command has to be added
# here deliberately, and cannot arrive undocumented by inheriting an exemption.
_NOT_DAILY_COMMANDS = {("hooks", "bypass-check")}


def test_every_command_has_a_reference_row():
    """`pin-unremovable-duplicates`: the manual restates the CLI surface in prose,
    which cannot be merged into argparse, so it is pinned by parsing both."""
    documented = set(_reference_rows())
    real = set(_leaf_paths(build_parser()))
    missing = sorted(" ".join(p) for p in real - documented - _NOT_DAILY_COMMANDS)
    assert not missing, f"these commands have no Command Reference row: {missing}"

    stale = sorted(" ".join(p) for p in _NOT_DAILY_COMMANDS - real)
    assert not stale, f"exempted from the reference table but no longer a command: {stale}"


def test_a_command_kept_out_of_the_table_is_still_documented():
    """The exemption is from the DAILY table, not from the manual. Without this,
    `_NOT_DAILY_COMMANDS` would be a way to make a command disappear."""
    manual = (REPO / "docs" / "UserManual.md").read_text(encoding="utf-8")
    for path in sorted(_NOT_DAILY_COMMANDS):
        assert f"agentsmith {' '.join(path)}" in manual, (
            f"`agentsmith {' '.join(path)}` is exempt from the reference table and appears nowhere "
            "in the manual — exempt from the table is not exempt from being documented"
        )


def test_every_reference_row_lists_the_flags_its_command_accepts():
    """Found `tenant init` documenting two of seven options — `--architecture`
    and `--agentic` among the five missing, while `tenant adopt`'s row documented
    both. Two sibling commands, and a reader would have concluded `init` could
    not do what `adopt` could (.agent-rfc/designs/docs-vs-code-audit.md).
    """
    rows = _reference_rows()
    leaves = _leaf_paths(build_parser())
    gaps = {}
    for path, cell in rows.items():
        real = {s for action in leaves[path]._actions for s in action.option_strings
                if s.startswith("--") and s != "--help"}
        undocumented = sorted(f for f in real if not re.search(re.escape(f) + r"\b", cell))
        if undocumented:
            gaps[" ".join(path)] = undocumented
    assert not gaps, f"reference rows omit flags their command accepts: {gaps}"
