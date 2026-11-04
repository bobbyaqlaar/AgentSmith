"""
scripts/test/test_release_artifact_contract.py — what a release publishes must be
what install-ai-stack.sh fetches and what the docs hand a user.

These files form a contract with no shared definition: the installer names assets
by URL, docs/UserManual.md tells a user to fetch them, and
scripts/build_release_assets.sh builds them. Nothing connected them, and they
had come apart more than once: the installer fetched a tarball that lacked what
it expected; the documented installer URL 404'd at every version.

A release is the one artifact you cannot fix in place after the fact. These run a
real build rather than reading a workflow's text, and
scripts/check_release_install.sh runs the stranger's whole path in CI
(.agent-rfc/designs/release-install-path.md).
"""

from __future__ import annotations

import os
import re
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BUILD = REPO / "scripts" / "build_release_assets.sh"
RELEASE_YML = REPO / ".github" / "workflows" / "release.yml"
INSTALLER = REPO / "install-ai-stack.sh"
# Docs that hand a user a release URL to run or verify.
DOC_FILES = ("README.md", "docs/UserManual.md")

_REQUESTED = re.compile(r"\$\{RELEASE_BASE\}/([\w-]+(?:\.[\w-]+)*)")
# Any release-download URL in the docs, pinned or latest.
_DOC_RELEASE_URL = re.compile(r"releases/(?:latest/download|download/[^/\s]+)/([\w-]+(?:\.[\w-]+)*)")


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("dist")
    done = subprocess.run(["bash", str(BUILD), str(out)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    return out


def _names(built: Path) -> set[str]:
    return {p.name for p in built.iterdir()}


def test_every_asset_the_installer_fetches_is_built(built):
    requested = set(_REQUESTED.findall(INSTALLER.read_text(encoding="utf-8")))
    assert requested >= {"agentsmith-source.tar.gz", "agentsmith-source.tar.gz.sha256"}, requested
    assert not requested - _names(built), "the installer fetches what the build never makes: a remote install fails"


def test_the_installer_itself_is_a_release_asset(built):
    """Regression: the documented `curl .../releases/download/<tag>/install-ai-stack.sh
    | bash` 404'd at every version that ever existed, and `curl -fsSL … | bash` on a
    404 exits 0, so a wrong URL looked like a clean install."""
    assert {"install-ai-stack.sh", "install-ai-stack.sh.sha256"} <= _names(built)


def test_each_checksum_names_its_file_bare(built):
    """The docs pipe the file into `shasum -a 256 --check`, which resolves the name
    against the current directory, so a path in it fails."""
    for name in ("install-ai-stack.sh", "agentsmith-source.tar.gz"):
        assert (built / f"{name}.sha256").read_text().split()[1] == name


def test_docs_only_reference_assets_the_release_builds(built):
    """A doc that hands someone a URL is as much a part of the contract as the
    installer is."""
    for doc in DOC_FILES:
        refs = set(_DOC_RELEASE_URL.findall((REPO / doc).read_text(encoding="utf-8")))
        assert not refs - _names(built), f"{doc} references assets the release never builds: {refs - _names(built)}"


def test_the_source_archive_unpacks_as_a_checkout(built):
    """The installer recognises a checkout by its own file and the gate launcher, at
    the top level, so a prefix directory would break the one install path."""
    with tarfile.open(built / "agentsmith-source.tar.gz") as archive:
        names = set(archive.getnames())
    assert {"install-ai-stack.sh", ".githooks/process-gate"} <= names
    # What the first commit and the ports read at run time: the installer's second
    # path once installed without these, and the gate refused the first commit.
    assert {"docs/review-levers.md", "runtime/cli.py", "fixtures/security/control_registry.json"} <= names


def test_the_source_archive_holds_only_tracked_files(built):
    tracked = set(
        subprocess.run(
            ["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.splitlines()
    )
    with tarfile.open(built / "agentsmith-source.tar.gz") as archive:
        files = {m.name for m in archive.getmembers() if m.isfile()}
    assert not files - tracked, f"the archive carries what git does not track: {sorted(files - tracked)[:5]}"
    assert not any(n.endswith(".env") or "node_modules/" in n for n in files)


def test_the_release_builds_through_the_shared_script():
    """One build, or what Self-Test's check exercises is not what ships."""
    assert "bash scripts/build_release_assets.sh dist" in RELEASE_YML.read_text(encoding="utf-8")


def _build_with_listing(tmp_path: Path, listing: str) -> subprocess.CompletedProcess:
    """The real build, with `tar -tzf` answering `listing`."""
    stubs = tmp_path / "bin"
    stubs.mkdir()
    (tmp_path / "listing").write_text(listing, encoding="utf-8")
    stub = stubs / "tar"
    stub.write_text(f'#!/bin/sh\ncat "{tmp_path / "listing"}"\n', encoding="utf-8")
    stub.chmod(0o755)
    return subprocess.run(
        ["bash", str(BUILD), str(tmp_path / "dist")],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"},
    )


def _needed_names() -> list[str]:
    text = BUILD.read_text(encoding="utf-8")
    block = text[text.index("for needed in") : text.index("; do\n  # A here-string")]
    return block.replace("for needed in", "").replace("\\", " ").split()


def test_a_name_found_early_in_a_long_listing_is_not_reported_missing(tmp_path):
    """Tagging v3.0.1 failed on "missing install-ai-stack.sh" with the file present.

    The listing is longer than a pipe buffer, so a `printf | grep -q` is always
    still writing when grep leaves at its first match.
    """
    padding = "".join(f"padding/{i:06}.txt\n" for i in range(50_000))
    listing = "\n".join(_needed_names()) + "\n" + padding
    result = _build_with_listing(tmp_path, listing)
    assert result.returncode == 0, result.stderr


def test_a_name_really_absent_from_the_listing_is_still_reported(tmp_path):
    names = _needed_names()
    result = _build_with_listing(tmp_path, "\n".join(names[1:]) + "\n")
    assert result.returncode == 1
    assert f"missing {names[0]}" in result.stderr
