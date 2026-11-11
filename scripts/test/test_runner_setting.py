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
