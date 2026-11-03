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
    return any((framework / d).exists() and any((framework / d).iterdir()) for d in ("scripts", ".githooks", "runtime"))


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
