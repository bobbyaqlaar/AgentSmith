"""
scripts/test/test_release_install.py — outside a checkout the installer installs from
its release's source archive, or not at all
(.agent-rfc/designs/release-install-path.md).

The real installer, against a local release directory. A half-install that exited 0
is what this replaced: the machine's first commit was refused. The success path needs
a package index, so scripts/check_release_install.sh runs it in CI.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install-ai-stack.sh"

pytestmark = pytest.mark.skipif(not shutil.which("curl"), reason="the installer's download needs curl")


def _install(tmp_path: Path, base: str) -> subprocess.CompletedProcess:
    """Run a copy of the installer from an empty directory, which is not a checkout."""
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(INSTALLER, work / "install-ai-stack.sh")
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "AI_STACK_RELEASE_BASE": base}
    for name in ("AGENTSMITH_DIR", "PYTHONPATH"):
        env.pop(name, None)
    return subprocess.run(["bash", str(work / "install-ai-stack.sh")], cwd=work, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, check=False, timeout=120)


def _installed_anything(tmp_path: Path) -> bool:
    framework = tmp_path / "home" / ".agent-framework"
    shipped = ("scripts", ".githooks", "agentsmith")
    return any((framework / d).exists() and any((framework / d).iterdir()) for d in shipped)


def test_a_failed_download_stops_the_install_and_writes_nothing(tmp_path):
    done = _install(tmp_path, f"file://{tmp_path}/no-such-release")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "Could not download" in done.stderr and "Nothing was installed" in done.stderr
    assert "no-such-release" in done.stderr, "the URL that failed is named"
    assert "does not match its checksum" not in done.stderr, "it stops at the failed download, not a later step"
    assert not _installed_anything(tmp_path)


def test_a_corrupt_download_stops_the_install_and_writes_nothing(tmp_path):
    release = tmp_path / "release"
    release.mkdir()
    # A valid archive with the wrong checksum: only the check itself can stop this one.
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "install-ai-stack.sh").write_text("# not AgentSmith\n")
    with tarfile.open(release / "agentsmith-source.tar.gz", "w:gz") as archive:
        archive.add(payload / "install-ai-stack.sh", arcname="install-ai-stack.sh")
    (release / "agentsmith-source.tar.gz.sha256").write_text(f"{'0' * 64}  agentsmith-source.tar.gz\n")
    done = _install(tmp_path, f"file://{release}")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "does not match its checksum" in done.stderr
    assert "downloaded and verified" not in done.stdout, "an unverified archive must not be unpacked and used"
    assert not _installed_anything(tmp_path)


def test_a_release_install_fetches_its_own_version_by_default():
    """Installer and payload from one tag, including when an older URL is pinned:
    `latest` would mix them."""
    text = INSTALLER.read_text(encoding="utf-8")
    assert "${FRAMEWORK_REPO}/releases/download/v${FRAMEWORK_VERSION}" in text
    code = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    assert not any("releases/latest" in line for line in code), "the installer must not fetch `latest`"


# ── a piped install installs the release it announces ─────────


def _installer_text() -> str:
    return (REPO / "install-ai-stack.sh").read_text(encoding="utf-8")


def _installer_dir_seen_from(cwd, *argv, stdin=None) -> str:
    block = re.search(r'^INSTALLER_DIR="\$\(cd .*?^fi$', _installer_text(), re.S | re.M)
    assert block, "INSTALLER_DIR detection not found"
    script = block.group(0) + '\necho "$INSTALLER_DIR"\n'
    if not stdin:
        (cwd / "install-ai-stack.sh").write_text(script)
    return subprocess.run(["bash", *argv], input=script if stdin else None, cwd=cwd,
                          capture_output=True, text=True, check=True).stdout.strip()


def test_a_piped_install_inside_a_checkout_does_not_install_that_checkout(tmp_path):
    (tmp_path / ".githooks").mkdir()
    (tmp_path / ".githooks" / "process-gate").write_text("")
    (tmp_path / "install-ai-stack.sh").write_text("")
    assert _installer_dir_seen_from(tmp_path, stdin=True) == ""


def test_run_as_a_file_a_checkout_is_still_a_checkout(tmp_path):
    (tmp_path / ".githooks").mkdir()
    (tmp_path / ".githooks" / "process-gate").write_text("")
    assert _installer_dir_seen_from(tmp_path, "install-ai-stack.sh") == str(tmp_path.resolve())


def _step9(tmp_path, reported: str) -> subprocess.CompletedProcess:
    """Step 9 to the end of the installer, with a stub command reporting `reported`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "agentsmith"
    stub.write_text(f'#!/bin/bash\necho "{reported}"\n')
    stub.chmod(0o755)
    text = _installer_text()
    script = "\n".join([
        'header() { :; }; info() { :; }; warn() { :; }; success() { echo "OK $*"; }; error() { echo "ERR $*"; }',
        'FRAMEWORK_VERSION="4.0.1"; TEMPLATE_DIR="/nonexistent"; VENV_PYTHON="/usr/bin/true"',
        f'AGENTSMITH_BIN_DIR="{bin_dir}"; DOCS_AT="{tmp_path}"',
        text[text.index('header "Step 9'):],
    ])
    return subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True, check=False,
                          env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})


@pytest.mark.parametrize("reported", ["4.0.1", "4.0.1+src"])
def test_the_install_passes_on_the_version_it_announces(tmp_path, reported):
    result = _step9(tmp_path, reported)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "installed successfully" in result.stdout


def test_another_version_fails_the_install_and_says_so(tmp_path):
    result = _step9(tmp_path, "3.0.0")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "agentsmith reports 3.0.0, and this installer is 4.0.1" in result.stdout
    assert "installed successfully" not in result.stdout
