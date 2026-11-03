"""
scripts/test/test_agpl_compliance.py — the notices AGPL-3.0 asks for exist, and say
what they must (.agent-rfc/designs/agpl-compliance.md).

A mapping of obligations to files, held by a test, not legal advice.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import third_party_notices as tpn

# Reviewed 2026-11-03 as compatible with AGPL-3.0 for how they are used here. A licence
# outside this list needs a human to look at it, not a row added by a script.
REVIEWED = re.compile(
    r"MIT|ISC|BSD|Apache|Python Software Foundation|PSF|CNRI-Python|MPL|Mozilla Public"
    r"|LGPL|Lesser General Public|CC-BY-4\.0|0BSD"
)
THIRD_PARTY = REPO / "THIRD_PARTY_LICENSES.md"


def _rows() -> dict[str, str]:
    return {
        m[0]: m[2]
        for m in re.findall(r"^\| ([^|]+?) \| ([^|]*?) \| ([^|]*?) \|$", THIRD_PARTY.read_text(encoding="utf-8"), re.M)
    }


def test_the_license_is_the_agpl_in_full():
    text = (REPO / "LICENSE").read_text(encoding="utf-8")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in text and "13. Remote Network Interaction" in text


def test_notice_names_the_holder_the_warranty_the_source_and_section_13():
    text = (REPO / "NOTICE").read_text(encoding="utf-8")
    for needed in (
        "Copyright (C) 2026 Aqlaar Tech FZE LLC",
        "WITHOUT ANY",
        "AGPL-3.0-only",
        "https://github.com/bobbyaqlaar/AgentSmith",
        "section 13",
        "AGENTSMITH_SOURCE_URL",
    ):
        assert needed in text, needed


def test_the_portal_offers_its_source_on_every_page():
    """Section 13: everyone interacting with it remotely. The root layout wraps every
    page, and the offer must follow AGENTSMITH_SOURCE_URL for a modified copy."""
    layout = (REPO / "portal" / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert "sourceUrl(process.env.AGENTSMITH_SOURCE_URL)" in layout and ">\n                Source\n" in layout
    assert "COPYRIGHT" in layout and "LICENSE_URL" in layout and "no warranty" in layout


def test_what_is_conveyed_carries_the_notice():
    assert "@license AGPL-3.0-only" in (REPO / "templates/in-app-widget/widget.js").read_text(encoding="utf-8")
    assert 'license-files = ["LICENSE", "NOTICE"]' in (REPO / "pyproject.toml").read_text(encoding="utf-8")


def test_every_pinned_package_is_listed():
    rows = _rows()
    pinned = set(tpn.pinned_python())
    for lock in tpn.NPM_LOCKS.values():
        pinned |= set(tpn.pinned_npm(lock))
    missing = pinned - set(rows)
    assert not missing, f"run scripts/third_party_notices.py: not in THIRD_PARTY_LICENSES.md: {sorted(missing)[:8]}"


def test_every_listed_licence_has_been_reviewed():
    unreviewed = {name: lic for name, lic in _rows().items() if name != "Package" and not REVIEWED.search(lic)}
    assert not unreviewed, f"a licence no one has reviewed against the AGPL: {unreviewed}"


def test_the_separately_licensed_services_are_named():
    for path in ("NOTICE", "THIRD_PARTY_LICENSES.md"):
        assert "Elastic License 2.0" in (REPO / path).read_text(encoding="utf-8"), path


def test_a_public_project_has_its_community_files():
    for name in (
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE/bug_report.md",
        ".github/ISSUE_TEMPLATE/config.yml",
    ):
        assert (REPO / name).is_file(), name
