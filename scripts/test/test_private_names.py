"""
scripts/test/test_private_names.py — names the owner keeps out of this public repository.

A private tenant and the GCP project are not named here: the tenant is "Tenant B" and the
project is `$GCP_PROJECT_ID` or `PROJECT_ID`. Each record a change writes is a chance to
name them again, so every tracked text file is checked. The names are held as SHA-256
digests, so this file does not publish what it keeps out.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# SHA-256 of each exact token kept out (case-sensitive).
PRIVATE_DIGESTS = frozenset({
    "2b38228e74eb924bd17311e26262af09d424c517f4266316f264dad65daa006c",
    "fc33f77a71cb245e221e5d0837ee33238dc64ab46b0546efab843d97cf6a5767",
    "0c0ad8e3b84491947b6f96aaa31dc1273b29fcbef7f586e2101b2c4e49b45177",
})

TOKEN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")


def private_tokens(text: str, digests: frozenset[str] = PRIVATE_DIGESTS) -> set[str]:
    """The tokens in `text` whose digest is a kept-out name."""
    return {
        tok for tok in set(TOKEN.findall(text))
        if hashlib.sha256(tok.encode()).hexdigest() in digests
    }


def _tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"not a git checkout: {exc}")
    return [ROOT / p for p in out.decode().split("\0") if p]


def test_the_check_matches_whole_exact_tokens() -> None:
    # Proving it on the real names would publish them, so it is proven on a stand-in:
    # whole tokens, inside backticks and before a possessive, and only the exact token.
    digests = frozenset({hashlib.sha256(b"Example-1").hexdigest()})
    text = "see `Example-1`'s design (Example-1), not Example-12 or example-1."
    assert private_tokens(text, digests) == {"Example-1"}
    assert private_tokens("nothing here", digests) == set()
    assert len(PRIVATE_DIGESTS) == 3


def test_no_tracked_file_names_a_private_tenant_or_project() -> None:
    named: dict[str, int] = {}
    for path in _tracked_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        hits = private_tokens(text)
        if hits:
            named[str(path.relative_to(ROOT))] = len(hits)
    assert not named, (
        "These files name a private tenant or the GCP project; write \"Tenant B\" or "
        f"`$GCP_PROJECT_ID` instead: {sorted(named)}"
    )
