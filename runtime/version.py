"""
runtime/version.py — which AgentSmith a tenant is actually running.

WHY IT HAS TO BE ON THE WIRE. AgentSmith and the tenants that use it have
different owners and different release cadences: IT operations ships the
framework and the Ops Portal; the business ships the tenant app and pins a
framework version so IT's cadence cannot move underneath it. That separation is
the design, and the pin is what makes it work.

The consequence nobody had accounted for is that IT then operates a FLEET of
tenants on different framework versions at once, and a version determines what
telemetry a tenant is even capable of emitting. A tenant pinned to v1.2.0 emits
no `prompt.system.sha256` (prompt_identity did not exist), no metrics at all
(neither did metrics.py), and `tenant.id` only when a caller remembered the
kwarg — there was no identity processor. On an ops dashboard that is
indistinguishable from a current tenant that is BROKEN.

`framework.version` was declared in `.agenticframework/tenant.yaml` by the
scaffold and read by nothing — the same declared-but-unenforced shape as
`tenant.id`, `budget.monthly_usd_cap` and `workflow.engine` before those were
closed. And a declaration in the tenant's own repo could not answer this
anyway: what matters is the version of the code that is RUNNING, not the one
the repo says it wants.

INSTALLED VERSUS CHECKED-OUT, and this is the part that must not be smoothed
over. `importlib.metadata` answers for a package installed from a release
artifact. A framework checkout on `sys.path` — `AGENTSMITH_DIR`, which is how
tenant CI and local development run — has a `pyproject.toml` whose version is
whatever the last release set, and `main` can be far ahead of it. Reporting a
bare "1.2.0" from a working copy that is twenty-odd changelog sections past the
tag would be a confident lie of exactly the kind this module exists to prevent.

So a checkout reports `1.2.0+src`. The `+src` is SemVer build metadata, it
compares equal for ordering, and it says the one thing an operator needs: this
is not a released artifact, so the number alone does not tell you what it
emits. `UNKNOWN` when even that cannot be determined — never a guess.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DIST_NAME = "agentsmith-runtime"

#: What `framework_version()` returns when nothing can answer. Never a number:
#: a wrong version is aggregated with real fleet data, an absent one is a gap
#: an operator can see.
UNKNOWN = "unknown"

#: Marks a version resolved from a source checkout rather than an installed
#: release artifact. See the module docstring.
SOURCE_SUFFIX = "+src"

_cached: Optional[str] = None


def _installed_version() -> Optional[str]:
    try:
        from importlib.metadata import version

        return version(DIST_NAME)
    except Exception:  # PackageNotFoundError, or no importlib.metadata at all
        return None


def _checkout_version() -> Optional[str]:
    """The `version = "x.y.z"` line of the pyproject.toml above this file.

    Parsed rather than tomllib-loaded so this works on any supported Python and
    cannot fail on an unrelated syntax error elsewhere in the file — the same
    regex `scripts/test/test_version_consistency.py` already pins.
    """
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r'^version = "(\d+\.\d+\.\d+)"', text, re.M)
    return m.group(1) if m else None


def framework_version() -> str:
    """The running framework's version. Cached — it cannot change mid-process."""
    global _cached
    if _cached is not None:
        return _cached

    installed = _installed_version()
    if installed:
        _cached = installed
        return _cached

    checkout = _checkout_version()
    _cached = f"{checkout}{SOURCE_SUFFIX}" if checkout else UNKNOWN
    return _cached


def is_source_checkout(version: Optional[str] = None) -> bool:
    """Whether a reported version came from a working copy rather than a release.

    Exposed because a consumer reasoning about what a version EMITS has to treat
    these differently: a released 1.2.0 emits exactly what 1.2.0 emitted, and a
    1.2.0+src emits whatever that working copy happened to contain.
    """
    return (version if version is not None else framework_version()).endswith(
        SOURCE_SUFFIX
    )


# ── Declared versus installed ─────────────────────────────────────────────────

_mismatch_warned = False


def _minor_series(version: str) -> Optional[tuple[int, int]]:
    """`(major, minor)` from `1.3.0`, `1.3.x`, `1.3.0+src`, or None.

    MINOR granularity on purpose. It is the granularity the compatibility matrix
    in CHANGELOG.md is written at — its rows are `1.3.x` — and it is what
    `.agenticframework/tenant.yaml` declares, because the scaffold writes
    `1.3.x` too. Comparing patch levels would warn on every patch release,
    which teaches an operator to ignore the warning.
    """
    m = re.match(r"^(\d+)\.(\d+)\.", version.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^(\d+)\.(\d+)\.[xX*]$", version.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def warn_if_declared_version_differs(root: Optional[Path] = None) -> Optional[str]:
    """Warn once when `framework.version` disagrees with what is installed.

    Returns the warning text, or None when there is nothing to say — so a caller
    can surface it its own way and a test can assert on it without capturing
    logs.

    WHY THIS EXISTS. `framework.version` has been declared in
    `.agenticframework/tenant.yaml` since the scaffold shipped and read by
    nothing — the same declared-but-unenforced shape as `tenant.id`,
    `budget.monthly_usd_cap` and `workflow.engine` before those were closed. And
    `ai-tenant-init` writes that declaration but no `requirements.txt` and no
    pin, so a tenant is scaffolded stating a version that nothing installs and
    nothing checks.

    That gap is invisible in the framework's own repo and in KYC Sentinel, both
    of which have a framework checkout to compare against. It is the ONLY check
    available to the tenants that matter: separate repositories, monitored and
    traced by an AgentSmith that has no access to their code. This needs no git,
    no tags and no checkout — just the installed distribution.

    WARNS, NEVER RAISES. A tenant one line ahead of its own declaration is not a
    safety problem, and refusing to start would make the upgrade order-dependent
    — bump the pin and the declaration in either order and one boot fails.
    `resolve_tenant_id` refuses because an unattributed run corrupts the budget
    ledger and the audit trail; this is not that.
    """
    global _mismatch_warned
    if _mismatch_warned:
        return None

    running = framework_version()
    if running == UNKNOWN:
        # Nothing to compare against. Reported rather than silent: a runtime
        # that cannot name itself is also a runtime whose telemetry carries
        # `unknown`, and an operator should hear that here rather than find it
        # on a fleet dashboard.
        _mismatch_warned = True
        text = (
            "AgentSmith cannot determine its own version — neither an installed "
            "`agentsmith-runtime` distribution nor a readable pyproject.toml. "
            "Telemetry will report the framework version as 'unknown'."
        )
        logger.warning(text)
        return text

    from runtime.config import config_get

    declared = config_get("framework.version", root)
    if declared is None or not str(declared).strip():
        # Not scaffolded, or scaffolded without the key. A normal state for a
        # repo that has not adopted the config file, and not worth a warning —
        # same reasoning as tenant_id_from_config returning None.
        return None

    want = _minor_series(str(declared))
    have = _minor_series(running)
    if want is None:
        _mismatch_warned = True
        text = (
            f"framework.version={declared!r} in .agenticframework/tenant.yaml is "
            f"not a version this can read (expected e.g. '1.3.x' or '1.3.0'); "
            f"the running framework is {running}."
        )
        logger.warning(text)
        return text
    if have is None or want == have:
        return None

    _mismatch_warned = True
    text = (
        f"AgentSmith {running} is running, but "
        f".agenticframework/tenant.yaml declares framework.version={declared!r}. "
        f"Nothing installs from that declaration — it is documentation — so the "
        f"two can drift silently. Telemetry from this process will report "
        f"{running}, which is what an Ops Portal sees. Bump the declaration, or "
        f"the dependency pin, so they agree."
    )
    logger.warning(text)
    return text


def _reset_cache() -> None:
    """For tests only."""
    global _cached, _mismatch_warned
    _cached = None
    _mismatch_warned = False
