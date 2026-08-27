"""
scripts/test/test_no_tenant_repo_dependency.py — the framework's tests must not
reach into a tenant's checkout.

WHAT THIS PREVENTS. Five test locations reached a sibling `../KYC_Sentinel`:
three sweeping its `worker.py` for framework wiring, two asserting things about
its eval fixture. All five skipped or returned silently when the directory was
absent — which is every CI runner, because the framework's CI does not check a
tenant out. So they had never run where it counted, and their green was the
green of a test that cannot fail.

KYC Sentinel is the exception that made this easy to write by accident: it is
the demo tenant and it sits next to the framework on the machine where these
were written. Every other tenant is a separate repository, monitored and traced
by an AgentSmith that has no access to its code. A framework test that needs a
sibling directory is a test that only ever runs on one laptop.

The direction matters. A TENANT depending on the framework is the architecture —
that is what the pin is. The framework depending on a tenant is a cycle, and it
is the one that quietly stops being checked.

REACH. This catches the two idioms this repo actually used to escape its own
root; it is not a general sandbox. A sweep is only as good as the escapes it
knows about, so it also asserts it read something.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# `ROOT.parent / "X"` and `parents[3] / "X"` — from runtime/test/ and
# scripts/test/ respectively, both land outside the repository.
_ESCAPES = (
    re.compile(r"\bROOT\.parent\s*/"),
    re.compile(r"\bparents\[\s*3\s*\]\s*/"),
)


def _test_sources() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "runtime/test/*.py", "scripts/test/*.py", "examples/**/test*.py"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout.split()
    return [ROOT / p for p in out]


def test_the_sweep_reads_the_test_suite() -> None:
    """A sweep that matches nothing passes for the wrong reason."""
    sources = _test_sources()
    assert len(sources) >= 40, f"expected the framework's test files, found {len(sources)}"


def test_no_framework_test_depends_on_a_sibling_checkout() -> None:
    offenders: list[str] = []
    for path in _test_sources():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue  # prose about the rule is not a breach of it
            if any(rx.search(stripped) for rx in _ESCAPES):
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {stripped}")

    assert not offenders, (
        "these reach outside the framework repository. A tenant lives in its own "
        "repo and is absent from every CI runner, so such a test skips where it "
        "matters and passes where it does not — assert it in the tenant's suite "
        "instead:\n  " + "\n  ".join(offenders)
    )


def test_no_tenant_directory_is_named_as_a_path() -> None:
    """The narrower, more direct check: a tenant's directory name used to BUILD
    a path. Naming a tenant in prose is fine — the framework documents its
    testbed — so only path construction counts.
    """
    offenders: list[str] = []
    named = re.compile(r"""["'](KYC_Sentinel|oil-price-demo)["']\s*(?:/|\))""")
    for path in _test_sources():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if named.search(stripped):
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {stripped}")
    assert not offenders, (
        "these build a path from a tenant's directory name:\n  " + "\n  ".join(offenders)
    )
