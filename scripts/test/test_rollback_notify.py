"""
scripts/test/test_rollback_notify.py — the rollback notification names the
commit that was actually deployed.

.github/actions/rollback-notify reported `github.sha`. Since cd-staging.yml and
cd-production.yml were gated on CI they run on `workflow_run`, where
`github.sha` is the default branch's latest commit — so a failed deploy of one
commit was announced as a failure of another. This runs the action's own step
scripts in order, the way a runner would (env from each step's `env:` map,
$GITHUB_ENV carried between steps, `if:` on the webhook inputs), with `curl`
replaced by a shim that records the payload it was given.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
ACTION = REPO / ".github" / "actions" / "rollback-notify" / "action.yml"
DEPLOYED = "a" * 40
BRANCH_HEAD = "b" * 40

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None, reason="bash and git required"
)

_EXPR = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")


def _steps() -> list[dict]:
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))["runs"]["steps"]


def _run_action(
    cwd: Path, tmp_path: Path, context: dict[str, str]
) -> tuple[list[subprocess.CompletedProcess], list[str]]:
    """Execute every step; return the results and each payload curl received."""
    shims = tmp_path / "shims"
    shims.mkdir()
    payloads = tmp_path / "payloads"
    # Record the argument after -d, one JSON document per line.
    (shims / "curl").write_text(
        '#!/usr/bin/env bash\n'
        'while [ $# -gt 0 ]; do\n'
        '  [ "$1" = -d ] && { printf "%s\\n" "$2" >> "' + str(payloads) + '"; shift; }\n'
        '  shift\n'
        'done\n'
    )
    (shims / "curl").chmod(0o755)
    github_env = tmp_path / "github_env"
    github_env.write_text("")

    results = []
    for step in _steps():
        condition = step.get("if", "")
        match = re.fullmatch(r"(inputs\.\w+) != ''", condition)
        if match and not context.get(match.group(1)):
            continue
        env = {
            "PATH": f"{shims}{os.pathsep}{os.environ['PATH']}",
            "HOME": os.environ.get("HOME", str(tmp_path)),
            "GITHUB_ENV": str(github_env),
            "GIT_CEILING_DIRECTORIES": str(tmp_path.parent),
        }
        for line in github_env.read_text().splitlines():
            key, _, value = line.partition("=")
            env[key] = value
        for key, value in (step.get("env") or {}).items():
            env[key] = _EXPR.sub(lambda m: context.get(m.group(1), ""), str(value))
        results.append(subprocess.run(
            ["bash", "-e", "-c", step["run"]], cwd=cwd, env=env, capture_output=True, text=True, check=False,
        ))
    sent = payloads.read_text().splitlines() if payloads.exists() else []
    return results, sent


def _context(**overrides: str) -> dict[str, str]:
    base = {
        "github.sha": BRANCH_HEAD,
        "github.event.workflow_run.head_sha": DEPLOYED,
        "github.repository": "acme/tenant",
        "github.server_url": "https://github.com",
        "github.run_id": "42",
        "inputs.slack_webhook_url": "https://hooks.slack.example/x",
        "inputs.teams_webhook_url": "https://teams.example/y",
        "inputs.rollback_command": "",
        "inputs.environment_label": "production",
        "inputs.failure_context": "post-deploy smoke test",
    }
    return base | overrides


def _checkout_of(tmp_path: Path, sha_hint: str) -> tuple[Path, str]:
    repo = tmp_path / "checkout"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "--template=", str(repo)], check=True)
    (repo / "f").write_text(sha_hint)
    subprocess.run(["git", "-C", str(repo), "add", "f"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "-m", "deployed"],
        check=True,
    )
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return repo, head.stdout.strip()


def test_no_step_script_interpolates_an_expression():
    """Every value reaches a script through env. `${{ }}` inside `run:` is what
    let an input's quote break the payload, and is untestable here besides."""
    for step in _steps():
        assert "${{" not in step["run"], f"step {step['name']!r} interpolates into its script"


def test_under_workflow_run_the_deployed_checkout_is_named_not_the_branch_head(tmp_path):
    checkout, deployed = _checkout_of(tmp_path, "deployed")

    # The CI run's head_sha is normally the same commit; a different value here
    # proves the checkout, the most exact source, is the one that wins.
    results, sent = _run_action(checkout, tmp_path, _context())

    assert len(sent) == 2, "both webhooks must be notified"
    for payload in sent:
        text = json.loads(payload)["text"]
        assert f"acme/tenant@{deployed}" in text
        assert BRANCH_HEAD not in text and DEPLOYED not in text
    assert f"Failed commit: {deployed} (checked-out HEAD)" in results[0].stdout


def test_without_a_checkout_the_triggering_ci_runs_commit_is_named(tmp_path):
    bare = tmp_path / "no-checkout"
    bare.mkdir()

    results, sent = _run_action(bare, tmp_path, _context())

    assert all(f"@{DEPLOYED}" in json.loads(p)["text"] for p in sent)
    assert "(triggering CI run)" in results[0].stdout


def test_a_push_triggered_run_without_a_checkout_falls_back_to_the_event_commit(tmp_path):
    bare = tmp_path / "no-checkout"
    bare.mkdir()

    results, sent = _run_action(bare, tmp_path, _context(**{"github.event.workflow_run.head_sha": ""}))

    assert all(f"@{BRANCH_HEAD}" in json.loads(p)["text"] for p in sent)
    assert "(event commit)" in results[0].stdout


def test_a_failure_context_with_quotes_newlines_and_backslashes_still_sends_valid_json(tmp_path):
    bare = tmp_path / "no-checkout"
    bare.mkdir()
    context_text = 'eval "smoke" failed\nat C:\\path\twith tab'

    results, sent = _run_action(bare, tmp_path, _context(**{"inputs.failure_context": context_text}))

    assert results[0].returncode == 0, results[0].stderr
    text = json.loads(sent[0])["text"]
    assert 'eval "smoke" failed at C:\\path with tab' in text
    # The newline did not smuggle an extra entry into $GITHUB_ENV.
    assert len((tmp_path / "github_env").read_text().splitlines()) == 2


def test_webhooks_left_unset_are_skipped_and_the_job_still_fails(tmp_path):
    bare = tmp_path / "no-checkout"
    bare.mkdir()

    results, sent = _run_action(
        bare, tmp_path, _context(**{"inputs.slack_webhook_url": "", "inputs.teams_webhook_url": ""}),
    )

    assert sent == []
    assert f"failed commit {DEPLOYED}" in results[-2].stdout, "the rollback notice names the commit"
    assert results[-1].returncode == 1, "the action must leave the job red"


def test_a_configured_rollback_command_runs_and_can_read_the_failed_commit(tmp_path):
    """OPERATIONS.md documents $ROLLBACK_NOTIFY_COMMIT for ROLLBACK_COMMAND."""
    bare = tmp_path / "no-checkout"
    bare.mkdir()
    marker = tmp_path / "rolled-back"
    command = f'printf "%s" "$ROLLBACK_NOTIFY_COMMIT" > "{marker}"'

    results, _ = _run_action(bare, tmp_path, _context(**{"inputs.rollback_command": command}))

    assert results[-2].returncode == 0, results[-2].stderr
    assert marker.read_text() == DEPLOYED
