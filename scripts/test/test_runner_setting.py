"""Every job AgentSmith gives a tenant runs where the tenant says
(.agent-rfc/designs/sovereign-build-side.md): a self-hosted runner through
`vars.AGENTSMITH_RUNNER`, GitHub's hosted runner when it is unset."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

TEMPLATES = Path(__file__).resolve().parents[2] / "workflow-templates"
RUNNER = "${{ vars.AGENTSMITH_RUNNER || 'ubuntu-latest' }}"


def _jobs():
    for path in sorted(TEMPLATES.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_id, job in (workflow.get("jobs") or {}).items():
            if isinstance(job, dict) and "uses" not in job:  # a reusable-workflow call has no runner of its own
                yield path.name, job_id, job


@pytest.mark.parametrize("name, job_id, job", list(_jobs()), ids=lambda value: value if isinstance(value, str) else "")
def test_every_template_job_runs_where_the_tenant_says(name, job_id, job):
    assert job.get("runs-on") == RUNNER, f"{name} job {job_id} runs on {job.get('runs-on')!r}"


def test_there_are_jobs_to_check():
    assert len(list(_jobs())) >= 12


# ── The 4.1.0 release review: R8 ──


def _own_machines_section() -> str:
    text = (Path(__file__).resolve().parents[2] / "docs" / "UserManual.md").read_text(encoding="utf-8")
    start = text.index("### Keeping the build side on your own machines")
    return text[start:text.index("\n## ", start)]


def test_the_manual_names_every_outside_action_the_templates_use():
    """R8: the section said "four outside services" and named none of the actions."""
    import re

    templates = Path(__file__).resolve().parents[2] / "workflow-templates"
    used = set()
    for path in templates.glob("*.yml"):
        for ref in re.findall(r"uses:\s*\"?([^\s\"@]+)", path.read_text(encoding="utf-8")):
            if not ref.startswith(("./", "{{")):
                used.add(ref.split("/.github/")[0] if "/.github/" in ref else ref)
    section = _own_machines_section()
    missing = sorted(ref for ref in used if ref not in section)
    assert missing == [], missing


def test_the_manual_says_what_is_not_supported_and_warns_about_forks():
    section = _own_machines_section()
    assert "cannot run on a runner with no route to the internet" in section
    assert "fork pull requests" in section
    for service in ("PyPI", "npm", "codecov"):
        assert service in section, service
