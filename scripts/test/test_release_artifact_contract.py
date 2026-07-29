"""
scripts/test/test_release_artifact_contract.py — the artifacts release.yml
builds must be exactly the ones install-ai-stack.sh downloads.

These two files form a contract with no shared definition: release.yml names
tarballs in a `run:` block, and install-ai-stack.sh fetches
`releases/latest/download/<name>` from a different file in a different
language. Nothing connected them, and they had already come apart —
`templates.tar.gz` was built from the single file `templates/agent-rules.yaml`
while the installer fetched that same tarball a second time expecting
`templates/onprem-deploy/` inside it, so `ai-onprem-deploy-scaffold` was
permanently broken on any remote install, with a `warn` as the only symptom.

A release is the one artifact you cannot fix in place after the fact: every
machine that runs the `curl | bash` one-liner gets whatever shipped. Worth a
test that runs before the tag, not after.
"""

from __future__ import annotations

import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RELEASE_YML = REPO / ".github" / "workflows" / "release.yml"
INSTALLER = REPO / "install-ai-stack.sh"
# Docs that hand a user a release URL to run or verify.
DOC_FILES = ("README.md", "OPERATIONS.md", "UserManual.md")

_DOWNLOAD_URL = re.compile(r"releases/latest/download/([\w.-]+)")
_TAR_BUILD = re.compile(r"-czf\s+dist/([\w.-]+)")
_COPY_BUILD = re.compile(r"cp\s+\S+\s+dist/([\w.-]+)")
_SHASUM_BUILD = re.compile(r"shasum[^\n]*>\s*([\w.-]+)")
# Any release-download URL in the docs, pinned or latest.
_DOC_RELEASE_URL = re.compile(r"releases/(?:latest|download/[^/\s]+)/download/([\w.-]+)|releases/download/[^/\s]+/([\w.-]+)")


def _requested_artifacts() -> set[str]:
    return set(_DOWNLOAD_URL.findall(INSTALLER.read_text(encoding="utf-8")))


def _built_artifacts() -> set[str]:
    text = RELEASE_YML.read_text(encoding="utf-8")
    return (
        set(_TAR_BUILD.findall(text))
        | set(_COPY_BUILD.findall(text))
        | set(_SHASUM_BUILD.findall(text))
    )


def _doc_referenced_artifacts() -> dict[str, set[str]]:
    """Release assets each doc tells a user to fetch."""
    out: dict[str, set[str]] = {}
    for name in DOC_FILES:
        text = (REPO / name).read_text(encoding="utf-8")
        found = {a or b for a, b in _DOC_RELEASE_URL.findall(text)}
        if found:
            out[name] = found
    return out


def test_every_downloaded_artifact_is_built() -> None:
    missing = _requested_artifacts() - _built_artifacts()
    assert not missing, (
        f"install-ai-stack.sh downloads artifacts release.yml never builds: "
        f"{sorted(missing)} — a fresh remote install would 404 on them"
    )


def test_the_installer_itself_is_a_release_asset() -> None:
    """The bootstrap script has to ship as an asset, not just build others.

    Regression: the release published only the tarballs install-ai-stack.sh
    downloads, so `curl .../releases/download/<tag>/install-ai-stack.sh | bash`
    — the first command in OPERATIONS.md — 404'd at every version that ever
    existed. The pre-existing tests here could not catch it by construction:
    they check artifacts the installer *downloads*, and it does not download
    itself. Nothing surfaced it either, because `curl -fsSL … | bash` on a 404
    exits 0 (curl writes to stderr, bash runs an empty script, the pipeline
    reports bash's status), so a wrong URL looks like a clean install.
    """
    built = _built_artifacts()
    assert "install-ai-stack.sh" in built, (
        "release.yml never copies install-ai-stack.sh into dist/ — the "
        "documented curl-bootstrap URL will 404"
    )
    assert "install-ai-stack.sh.sha256" in built, (
        "no checksum published for the installer, but OPERATIONS.md documents "
        "verifying one before executing it"
    )


def test_docs_only_reference_artifacts_the_release_builds() -> None:
    """Closes the loop the installer-only check left open.

    OPERATIONS.md documented fetching `install-ai-stack.sh` and its `.sha256`
    from a release for an entire version cycle while neither was published.
    A doc that hands someone a URL is as much a part of the release contract as
    the installer is.
    """
    built = _built_artifacts()
    bad = {
        doc: sorted(refs - built)
        for doc, refs in _doc_referenced_artifacts().items()
        if refs - built
    }
    assert not bad, (
        f"docs reference release assets that release.yml never builds: {bad} — "
        f"built assets are {sorted(built)}"
    )


def test_templates_tarball_carries_both_destinations() -> None:
    """install-ai-stack.sh fetches templates.tar.gz for TWO destinations:
    agent-rules.yaml (IDE config generation) and onprem-deploy/
    (ai-onprem-deploy-scaffold). One archive has to satisfy both."""
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "templates.tar.gz"
        subprocess.run(
            [
                "tar",
                "--exclude=node_modules",
                "--exclude=__pycache__",
                "-czf",
                str(archive),
                "-C",
                str(REPO / "templates"),
                ".",
            ],
            check=True,
        )
        with tarfile.open(archive) as tf:
            names = {n.lstrip("./") for n in tf.getnames()}

    assert "agent-rules.yaml" in names, "IDE config generation would break"
    assert any(n.startswith("onprem-deploy/") for n in names), (
        "ai-onprem-deploy-scaffold would break on a remote install"
    )
    assert not any("node_modules" in n for n in names), "build artifact leaked into the release"


def test_artifacts_extract_flat() -> None:
    """install-ai-stack.sh does `tar -xz -C "$DEST"`, so an archive with a
    top-level directory prefix double-nests every path it installs. release.yml
    checks this in CI; checking it here means a broken build step fails before
    the tag exists rather than after."""
    specs = {
        "scripts.tar.gz": REPO / "scripts",
        "hooks.tar.gz": REPO / "hooks",
        "workflow-templates.tar.gz": REPO / "workflow-templates",
        "templates.tar.gz": REPO / "templates",
        "github-actions.tar.gz": REPO / ".github" / "actions",
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, source in specs.items():
            archive = Path(tmp) / name
            subprocess.run(
                ["tar", "--exclude=node_modules", "--exclude=__pycache__",
                 "-czf", str(archive), "-C", str(source), "."],
                check=True,
            )
            with tarfile.open(archive) as tf:
                tops = {n.lstrip("./").split("/")[0] for n in tf.getnames() if n not in (".", "./")}
            assert len(tops) > 1, (
                f"{name} collapses to a single top-level entry {tops} — it would "
                f"double-nest on extraction"
            )
