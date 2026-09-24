"""
scripts/test/test_sync_workflow.py — a tenant is told when it is behind, as a
pull request (.agent-rfc/designs/sync-pull-request.md).

The workflow runs in a tenant's CI, which cannot be exercised here, so these
tests read it as data and assert what it does: proposes rather than pushes,
carries the trailers the gate accepts, stops when nothing changed, and keeps one
open proposal.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "workflow-templates" / "agentsmith-sync.yml"


@pytest.fixture()
def workflow() -> dict:
    return yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))


@pytest.fixture()
def steps(workflow) -> list[dict]:
    [job] = workflow["jobs"].values()
    return job["steps"]


def _script(steps: list[dict]) -> str:
    return "\n".join(step.get("run", "") for step in steps)


def test_it_runs_weekly_and_on_demand(workflow):
    # `on` is YAML's `True` unless quoted — the workflow quotes it.
    triggers = workflow.get("on") or workflow.get(True)
    assert triggers.get("schedule"), "a tenant nobody watches is the point"
    assert "workflow_dispatch" in triggers


def test_it_proposes_and_never_pushes_to_the_default_branch(steps):
    script = _script(steps)
    assert "gh pr create" in script or "gh pr edit" in script
    assert "push --force" not in script.replace("git push --force-with-lease origin HEAD:refs/heads/", "")
    assert "origin main" not in script, "a sync is a proposal, not a push to the default branch"


def test_the_commit_carries_the_trailers_the_gate_accepts(steps):
    script = _script(steps)
    assert "Design: .agent-rfc/designs/adoption.md" in script
    assert "Review: n/a: framework sync" in script


def test_nothing_to_sync_ends_the_run_rather_than_failing(steps):
    script = _script(steps)
    assert "git status --porcelain" in script
    assert "nothing to sync" in script.lower()


def test_it_follows_the_latest_release_rather_than_a_pin(steps):
    script = _script(steps)
    joined = script + "\n" + "\n".join(str(step.get("with", "")) for step in steps)
    assert "releases/latest" in joined, "the point is to notice a new release"
    assert "{{FRAMEWORK_REF}}" not in joined, "this one is not pinned to the adopted release"


def test_one_branch_so_a_second_run_updates_the_open_proposal(steps):
    assert "agentsmith/sync" in _script(steps)


def test_it_names_what_it_needs_and_asks_for_no_more(workflow, steps):
    [job] = workflow["jobs"].values()
    assert job.get("permissions") == {"contents": "write", "pull-requests": "write"}
    script = _script(steps) + "\n" + "\n".join(str(step.get("env", "")) for step in steps)
    assert "AGENTSMITH_READ_TOKEN" in script
    assert "GITHUB_TOKEN" in script


def test_the_template_is_what_a_tenant_gets(steps):
    """No placeholder left unsubstituted: unlike the gates workflow, this one is
    not pinned to a release, so it needs no substitution at all."""
    assert "{{" not in TEMPLATE.read_text(encoding="utf-8").replace("${{", "")
