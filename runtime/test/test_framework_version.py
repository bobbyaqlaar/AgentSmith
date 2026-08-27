"""
runtime/test/test_framework_version.py — the running framework says which one
it is, on both wires.

AgentSmith and the tenants that use it have different owners and different
release cadences: IT ships the framework and the Ops Portal, the business ships
the tenant and pins a version. So the portal always reads a FLEET spanning
several framework versions, and a version decides what a tenant can emit at all
— v1.2.0 has no prompt_identity, no metrics, and no identity processor, so its
spans carry no `prompt.system.sha256`, no counters, and `tenant.id` only where a
caller remembered the kwarg.

Without the version on the wire, that is indistinguishable from a current tenant
that is broken. `framework.version` WAS declared in tenant.yaml and read by
nothing — and a declaration in the tenant's repo could not answer this anyway,
since what matters is the version of the code that is running, not the one the
repo says it wants.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from runtime import version as version_mod
from runtime.tracing import resource_attributes

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _fresh_cache():
    version_mod._reset_cache()
    yield
    version_mod._reset_cache()


def test_a_checkout_is_marked_as_one() -> None:
    """The distinction the whole module exists for.

    This working copy's pyproject.toml says 1.2.0 while `main` is twenty-odd
    changelog sections past that tag. Reporting a bare "1.2.0" would be a
    confident lie about what this process emits — precisely the failure the
    version is being added to prevent.
    """
    version_mod._cached = None
    reported = version_mod.framework_version()
    assert reported.endswith("+src") or version_mod._installed_version(), (
        f"{reported!r} claims to be a released artifact while running from a "
        "source checkout"
    )


def test_source_builds_are_identifiable_without_parsing() -> None:
    assert version_mod.is_source_checkout("1.2.0+src") is True
    assert version_mod.is_source_checkout("1.2.0") is False


def test_the_checkout_version_matches_pyproject(monkeypatch) -> None:
    monkeypatch.setattr(version_mod, "_installed_version", lambda: None)
    version_mod._reset_cache()
    declared = re.search(
        r'^version = "(\d+\.\d+\.\d+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    )
    assert declared, "pyproject.toml has no version line"
    assert version_mod.framework_version() == f"{declared.group(1)}+src"


def test_an_installed_package_reports_its_release_version_bare(monkeypatch) -> None:
    monkeypatch.setattr(version_mod, "_installed_version", lambda: "1.3.0")
    version_mod._reset_cache()
    assert version_mod.framework_version() == "1.3.0"
    assert version_mod.is_source_checkout() is False


def test_unresolvable_is_named_not_guessed(monkeypatch) -> None:
    """A wrong version is aggregated with real fleet data; an absent one is a
    gap an operator can see."""
    monkeypatch.setattr(version_mod, "_installed_version", lambda: None)
    monkeypatch.setattr(version_mod, "_checkout_version", lambda: None)
    version_mod._reset_cache()
    assert version_mod.framework_version() == version_mod.UNKNOWN


# ── Wire 1: the OTel Resource ────────────────────────────────────────────────


def test_every_span_carries_the_framework_version() -> None:
    """On the Resource, not per span.

    Unlike `agent.role` and `tenant.id` — which vary within one process and
    would be confident lies on a Resource — the framework version is fixed for
    the life of the worker. This is the one identity attribute for which the
    Resource is the correct home.
    """
    attrs = resource_attributes()
    assert "agentsmith.framework.version" in attrs
    assert attrs["agentsmith.framework.version"] == version_mod.framework_version()


# ── Wire 2: the run-status ingest ────────────────────────────────────────────


def test_the_ingest_payload_carries_the_version() -> None:
    """Read out of the source rather than by driving a POST: the alternative is
    a fake portal, and what matters here is that the field is in the body at
    all — the same property the portal's own test asserts from its side."""
    src = (ROOT / "runtime" / "llm_gateway.py").read_text(encoding="utf-8")
    assert '"frameworkVersion": framework_version(),' in src, (
        "the run-status POST no longer reports which framework wrote the row"
    )


def test_the_portal_column_is_nullable_and_added_by_an_alter() -> None:
    """A NULL here is meaningful — a row from a framework too old to report one
    — so a NOT NULL DEFAULT would erase the distinction the column exists for.
    And a deployed portal only ever gains a column from the ALTER: CREATE TABLE
    IF NOT EXISTS is a no-op against a database that already has the table."""
    schema = (ROOT / "portal" / "db" / "schema.sql").read_text(encoding="utf-8")
    assert re.search(r"framework_version TEXT(?!\s+NOT NULL)", schema)
    assert (
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS framework_version TEXT;"
        in schema
    )


def test_the_two_sides_agree_on_the_field_name() -> None:
    """Python writes it, TypeScript reads it, and neither can import the other.

    Parsed from both rather than restated here — a test that hardcodes the name
    twice is just a third copy of it.
    """
    py = (ROOT / "runtime" / "llm_gateway.py").read_text(encoding="utf-8")
    ts = (ROOT / "portal" / "app" / "api" / "runs" / "ingest" / "route.ts").read_text(
        encoding="utf-8"
    )
    sent = set(re.findall(r'"(\w+)": framework_version\(\)', py))
    assert sent == {"frameworkVersion"}, f"gateway sends {sent}"
    received = set(re.findall(r"versionOrNull\(body\.(\w+)\)", ts))
    assert received == sent, f"gateway sends {sent}, portal reads {received}"


def test_a_pinned_tenant_would_send_none_of_this() -> None:
    """The premise, checked against the tag rather than assumed.

    v1.2.0 — the version KYC Sentinel pins — has no version module to report
    from. That is what makes a NULL `framework_version` a reliable date stamp
    rather than a guess: the release that added the column is the release that
    started filling it.
    """
    import subprocess

    proc = subprocess.run(
        ["git", "cat-file", "-e", "v1.2.0:runtime/version.py"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0:
        pytest.fail("v1.2.0 has runtime/version.py — the dating premise is wrong")


def test_the_version_is_json_serialisable_for_the_post() -> None:
    json.dumps({"frameworkVersion": version_mod.framework_version()})


# ── Declared versus installed ────────────────────────────────────────────────
#
# `framework.version` in .agenticframework/tenant.yaml has been declared since
# the scaffold shipped and read by nothing, and `ai-tenant-init` writes that
# declaration but no requirements.txt and no pin — so a tenant is scaffolded
# stating a version that nothing installs and nothing checks.
#
# This is the only check available to the tenants that matter. KYC Sentinel is
# an exception: it lives beside the framework and can be compared against a
# checkout with tags. Real tenants are separate repositories, monitored and
# traced by an AgentSmith with no access to their code, so a guard that needs
# git, tags or a sibling directory is a guard they cannot run.


def _tenant_root(tmp_path, declared: str):
    cfg = tmp_path / ".agenticframework"
    cfg.mkdir()
    (cfg / "tenant.yaml").write_text(
        f'tenant:\n  id: t\nframework:\n  version: "{declared}"\n', encoding="utf-8"
    )
    return tmp_path


def test_a_matching_declaration_says_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod, "_installed_version", lambda: "1.3.4")
    version_mod._reset_cache()
    assert version_mod.warn_if_declared_version_differs(_tenant_root(tmp_path, "1.3.x")) is None


def test_a_patch_release_is_not_a_mismatch(tmp_path, monkeypatch) -> None:
    """Minor granularity, which is what the compatibility matrix is written at
    and what the scaffold declares. Warning on every patch release teaches an
    operator to ignore the warning."""
    monkeypatch.setattr(version_mod, "_installed_version", lambda: "1.3.9")
    version_mod._reset_cache()
    assert version_mod.warn_if_declared_version_differs(_tenant_root(tmp_path, "1.3.0")) is None


def test_a_source_checkout_matches_its_declared_series(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod, "_installed_version", lambda: None)
    monkeypatch.setattr(version_mod, "_checkout_version", lambda: "1.3.0")
    version_mod._reset_cache()
    assert version_mod.warn_if_declared_version_differs(_tenant_root(tmp_path, "1.3.x")) is None


def test_a_different_minor_series_warns(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod, "_installed_version", lambda: "1.2.0")
    version_mod._reset_cache()
    text = version_mod.warn_if_declared_version_differs(_tenant_root(tmp_path, "1.3.x"))
    assert text and "1.2.0" in text and "1.3.x" in text
    assert "Ops Portal sees" in text, "the operator needs to know what the fleet view will show"


def test_it_warns_once_per_process(tmp_path, monkeypatch) -> None:
    """A per-call warning on a worker that logs at startup is noise; a
    per-process one is a fact."""
    monkeypatch.setattr(version_mod, "_installed_version", lambda: "1.2.0")
    version_mod._reset_cache()
    root = _tenant_root(tmp_path, "1.3.x")
    assert version_mod.warn_if_declared_version_differs(root) is not None
    assert version_mod.warn_if_declared_version_differs(root) is None


def test_no_declaration_is_silent(tmp_path, monkeypatch) -> None:
    """A repo that has not adopted the config file is a normal state — the same
    reasoning as tenant_id_from_config returning None rather than raising."""
    monkeypatch.setattr(version_mod, "_installed_version", lambda: "1.3.0")
    version_mod._reset_cache()
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text("tenant:\n  id: t\n")
    assert version_mod.warn_if_declared_version_differs(tmp_path) is None


def test_an_unreadable_declaration_is_reported_not_ignored(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod, "_installed_version", lambda: "1.3.0")
    version_mod._reset_cache()
    text = version_mod.warn_if_declared_version_differs(_tenant_root(tmp_path, "latest"))
    assert text and "not a version this can read" in text


def test_an_unknown_running_version_is_reported(tmp_path, monkeypatch) -> None:
    """A runtime that cannot name itself also emits `unknown` on the wire. The
    operator should hear that here, not find it on a fleet dashboard."""
    monkeypatch.setattr(version_mod, "_installed_version", lambda: None)
    monkeypatch.setattr(version_mod, "_checkout_version", lambda: None)
    version_mod._reset_cache()
    text = version_mod.warn_if_declared_version_differs(_tenant_root(tmp_path, "1.3.x"))
    assert text and "cannot determine its own version" in text


def test_it_never_raises(tmp_path, monkeypatch) -> None:
    """The control: a version check that breaks startup is worse than the drift
    it reports."""
    monkeypatch.setattr(version_mod, "_installed_version", lambda: "1.2.0")
    version_mod._reset_cache()
    version_mod.warn_if_declared_version_differs(_tenant_root(tmp_path, "9.9.x"))


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "runtime" / "worker.py",
        ROOT / "examples" / "oil-price-agent" / "worker.py",
        ROOT.parent / "KYC_Sentinel" / "worker.py",
    ],
)
def test_every_worker_entrypoint_runs_the_check(path) -> None:
    if not path.exists():
        pytest.skip(f"{path} not present")
    assert "warn_if_declared_version_differs()" in path.read_text(encoding="utf-8")
