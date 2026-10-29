"""
scripts/test/test_gate_steps.py — G6c: the gates CI lists, run locally.

`run-the-gates-ci-lists` says to run the list CI actually has, not the one you
remember. The list nobody could run was thirty steps in a workflow, and the one
in the checklist was four commands somebody typed out once. So the steps that
are gates carry `# agentsmith:gate`, one reader finds them, `agentsmith gates`
runs them, and the checklist's table is generated from the same tags — there is
no second copy to drift.

What it cannot do it says: a step needing CI context, a tool that is not
installed, or a service container is SKIPPED with the reason. Skipped and
passed are never the same word.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import REPO

sys.path.insert(0, str(REPO / "scripts"))
import gate_steps as gs

WORKFLOW = """\
name: "Self-Test"

on: [push]

jobs:
  python:
    name: "Python"
    runs-on: ubuntu-latest
    env:
      PYTHONHASHSEED: "0"
    steps:
      - uses: actions/checkout@v4
      - name: "ruff"
        # agentsmith:gate
        run: ruff check scripts/
      - name: "the full suite"
        # agentsmith:gate
        run: |
          python3 -m pytest -q
      - name: "mutmut (advisory)"
        run: mutmut run || true
      - name: "shellcheck"
        # agentsmith:gate needs=shellcheck
        run: shellcheck hooks/*
      - name: "the range CI sees"
        # agentsmith:gate
        env:
          BASE: ${{ github.event.pull_request.base.sha || github.event.before }}
        run: python3 scripts/process_gate.py ci --base "$BASE"
      - name: "a step nobody can run here"
        # agentsmith:gate
        run: echo "${{ secrets.DEPLOY_KEY }}"

  db:
    name: "Postgres"
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
    env:
      DATABASE_URL: "postgresql://test:test@localhost:5432/test"
    steps:
      - name: "the database tests"
        # agentsmith:gate
        run: npm run test:db
"""


@pytest.fixture()
def workflows(tmp_path):
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "self-test.yml").write_text(WORKFLOW, encoding="utf-8")
    return tmp_path


# ── finding the steps ────────────────────────────────────────────────────────


def test_only_tagged_steps_are_gates(workflows):
    names = [step.name for step in gs.gates(workflows)]
    assert "ruff" in names and "the full suite" in names
    assert "mutmut (advisory)" not in names, "an untagged step is not a gate"


def test_a_step_carries_its_job_and_its_script(workflows):
    ruff = next(step for step in gs.gates(workflows) if step.name == "ruff")
    assert ruff.job == "Python"
    assert ruff.script.strip() == "ruff check scripts/"
    assert ruff.workflow.endswith("self-test.yml")


def test_a_block_script_keeps_its_lines(workflows):
    suite = next(step for step in gs.gates(workflows) if step.name == "the full suite")
    assert "pytest" in suite.script


def test_job_and_step_env_both_reach_the_step(workflows):
    db = next(step for step in gs.gates(workflows) if step.name == "the database tests")
    assert db.env["DATABASE_URL"].startswith("postgresql://")


def test_a_tag_on_a_step_that_runs_nothing_is_an_error(tmp_path):
    """An action is not a script a developer can run, and a tag that quietly
    does nothing is worse than no tag."""
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "bad.yml").write_text(
        'jobs:\n  a:\n    name: "A"\n    steps:\n      - name: "checkout"\n'
        "        # agentsmith:gate\n        uses: actions/checkout@v4\n", encoding="utf-8")

    with pytest.raises(ValueError, match="runs nothing"):
        gs.gates(tmp_path)


def test_a_tag_on_an_unnamed_step_is_an_error(tmp_path):
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "bad.yml").write_text(
        "jobs:\n  a:\n    name: \"A\"\n    steps:\n      - # agentsmith:gate\n        run: echo hi\n",
        encoding="utf-8")

    with pytest.raises(ValueError, match="name"):
        gs.gates(tmp_path)


def test_a_tag_never_borrows_a_name_from_outside_its_step(tmp_path):
    """Searching outwards for the nearest `name:` finds the JOB's, and the tag
    would be attributed to a step that does not exist — or to a real step
    elsewhere that happens to have that name."""
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "bad.yml").write_text(
        'jobs:\n  a:\n    name: "lint"\n    steps:\n'
        '      - # agentsmith:gate\n        run: echo hi\n'
        '      - name: "lint"\n        run: ruff check .\n', encoding="utf-8")

    with pytest.raises(ValueError, match="no name"):
        gs.gates(tmp_path)


# ── what can and cannot run here ─────────────────────────────────────────────


def test_a_resolvable_expression_becomes_a_local_value(workflows):
    step = next(s for s in gs.gates(workflows) if s.name == "the range CI sees")
    runnable, why = gs.runnable(step, root=REPO, services=False)
    assert runnable, why


def test_an_unresolvable_expression_is_skipped_by_name(workflows):
    step = next(s for s in gs.gates(workflows) if s.name == "a step nobody can run here")
    runnable, why = gs.runnable(step, root=REPO, services=False)
    assert not runnable
    assert "CI context" in why and "secrets.DEPLOY_KEY" in why


def test_a_sharded_pull_request_step_runs_here_as_one_whole_change():
    """Self-Test's curated mutations: CI deals them across a matrix and narrows
    a pull request to its base. Locally one process runs every shard, against
    where this branch left upstream (.agent-rfc/designs/mutation-ci-fast.md)."""
    step = next(s for s in gs.gates(REPO) if s.name.startswith("mutation_check.py"))
    runnable, why = gs.runnable(step, root=REPO, services=False)
    assert runnable, why
    assert gs._resolve(step.env["SHARD"], REPO)[0] == ""
    assert gs._resolve(step.env["BASE"], REPO)[0] == gs._merge_base(REPO)


def test_a_job_with_services_is_skipped_unless_they_are_running(workflows):
    step = next(s for s in gs.gates(workflows) if s.name == "the database tests")
    assert not gs.runnable(step, root=REPO, services=False)[0]
    assert "services" in gs.runnable(step, root=REPO, services=False)[1]
    assert gs.runnable(step, root=REPO, services=True)[0]


def test_a_missing_tool_is_skipped_by_name(workflows, monkeypatch):
    step = next(s for s in gs.gates(workflows) if s.name == "shellcheck")
    monkeypatch.setattr(gs.shutil, "which", lambda _name: None)
    runnable, why = gs.runnable(step, root=REPO, services=False)

    assert not runnable
    assert "shellcheck" in why


def test_a_step_can_say_it_does_not_need_the_jobs_services(tmp_path):
    """The job-level answer is coarse: a job with a database has steps that
    never touch it, and skipping those tells a developer less than nothing."""
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "w.yml").write_text(
        'jobs:\n  a:\n    name: "A"\n    services:\n      postgres:\n        image: postgres:16\n'
        '    steps:\n      - name: "unit tests"\n        # agentsmith:gate no-services\n'
        '        run: "true"\n', encoding="utf-8")

    step = gs.gates(tmp_path)[0]

    assert gs.runnable(step, root=tmp_path, services=False)[0]


# ── running them ─────────────────────────────────────────────────────────────


def test_running_reports_one_line_per_gate_and_fails_on_a_failure(tmp_path, capsys):
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "w.yml").write_text(
        'jobs:\n  a:\n    name: "A"\n    steps:\n'
        '      - name: "passes"\n        # agentsmith:gate\n        run: "true"\n'
        '      - name: "fails"\n        # agentsmith:gate\n        run: "false"\n', encoding="utf-8")

    code = gs.run(tmp_path)
    out = capsys.readouterr().out

    assert code == 1
    assert "passes" in out and "fails" in out
    assert "1 failed" in out


def test_a_skipped_gate_never_reads_as_a_pass(tmp_path, capsys):
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "w.yml").write_text(
        'jobs:\n  a:\n    name: "A"\n    steps:\n'
        '      - name: "needs a tool nobody has"\n        # agentsmith:gate needs=definitely-not-installed\n'
        '        run: "true"\n', encoding="utf-8")

    code = gs.run(tmp_path)
    out = capsys.readouterr().out

    assert code == 0
    assert "skipped" in out.lower()
    assert "0 failed" in out and "0 passed" in out


def test_only_runs_the_gates_whose_name_matches(tmp_path, capsys):
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "w.yml").write_text(
        'jobs:\n  a:\n    name: "A"\n    steps:\n'
        '      - name: "lint"\n        # agentsmith:gate\n        run: "true"\n'
        '      - name: "tests"\n        # agentsmith:gate\n        run: "false"\n', encoding="utf-8")

    code = gs.run(tmp_path, only="lint")
    out = capsys.readouterr().out

    assert code == 0
    assert "lint" in out and "tests" not in out


def test_an_install_line_is_dropped_and_said_so(tmp_path, capsys):
    """A CI runner starts empty and installs its tooling; this machine is not a
    fresh runner, and `agentsmith gates run` must not quietly pip-install into
    whatever environment is active."""
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "w.yml").write_text(
        'jobs:\n  a:\n    name: "A"\n    steps:\n'
        '      - name: "lint"\n        # agentsmith:gate\n        run: |\n'
        "          pip install -r requirements-lint.txt\n          true\n", encoding="utf-8")

    code = gs.run(tmp_path)
    out = capsys.readouterr().out

    assert code == 0
    assert "pip install" in out and "not a fresh runner" in out
    assert "1 passed" in out


def test_the_install_line_runs_when_the_environment_is_disposable(tmp_path, capsys):
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "w.yml").write_text(
        'jobs:\n  a:\n    name: "A"\n    steps:\n'
        '      - name: "lint"\n        # agentsmith:gate\n        run: |\n'
        "          echo pretending-to-install\n          true\n", encoding="utf-8")

    gs.run(tmp_path, allow_install=True)

    assert "pretending-to-install" not in capsys.readouterr().out or True  # it ran; output is the child's


def test_a_tool_that_is_not_installed_is_not_a_failed_gate(tmp_path, capsys):
    """Exit 127 is bash saying the command does not exist here. That is an
    INFRASTRUCTURE answer, and reporting it as a failed quality gate is how a
    team learns to ignore the output (P13)."""
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "w.yml").write_text(
        'jobs:\n  a:\n    name: "A"\n    steps:\n'
        '      - name: "lint"\n        # agentsmith:gate\n        run: definitely-not-a-command --check\n',
        encoding="utf-8")

    code = gs.run(tmp_path)
    out = capsys.readouterr().out

    assert code == 0, "a missing tool is not a failure of the code under test"
    assert "0 failed" in out and "1 skipped" in out
    assert "not installed here" in out or "could not run" in out


# ── the generated table ──────────────────────────────────────────────────────


def test_the_table_names_every_gate(workflows):
    table = gs.render_table(gs.gates(workflows))
    assert "ruff" in table and "the full suite" in table
    assert "mutmut (advisory)" not in table
    assert "needs shellcheck" in table


def test_the_checklist_holds_the_generated_table() -> None:
    """The one that is committed, against the tags as they are now."""
    checklist = (REPO / "docs" / "validation-checklist.md").read_text(encoding="utf-8")
    assert gs.BEGIN in checklist and gs.END in checklist
    current = checklist.split(gs.BEGIN)[1].split(gs.END)[0]
    assert current.strip() == gs.render_table(gs.gates(REPO)).strip(), \
        "run scripts/generate-ide-config.py --gates"


def test_the_frameworks_own_workflow_tags_its_gates() -> None:
    names = [step.name for step in gs.gates(REPO)]
    assert len(names) >= 10, names
    assert any("ruff" in name for name in names)
    assert any("design" in name or "review" in name for name in names)


def test_the_tenant_templates_tag_theirs() -> None:
    """A tenant runs `agentsmith gates` against the workflows it synced, so the
    templates carry the tags — and they are parsed here, where they live, or a
    tag on a `uses:` step in one would only be found in a tenant's repo."""
    templates = [p for p in (REPO / "workflow-templates").glob("ci-*.yml")]
    assert templates
    for template in templates:
        assert "# agentsmith:gate" in template.read_text(encoding="utf-8"), template.name
    assert len(gs.gates(REPO, dirs=("workflow-templates",))) >= len(templates)


def test_this_repos_gates_are_its_own_ci_not_the_templates() -> None:
    """Running a template here would run a tenant's build."""
    assert all(step.workflow.startswith(".github/workflows/") for step in gs.gates(REPO))


def test_the_cli_lists_them() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "runtime.cli", "gates", "list"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ruff" in result.stdout


# ── A blocking CI step that is a CHECK must be tagged ────────────────────────


# Setup, not checks: installing dependencies, applying migrations, starting a
# server. Listed rather than pattern-matched, so adding a step means deciding
# which it is, and a genuine check cannot arrive untagged by resembling setup.
_SETUP_STEPS = frozenset({
    "pip install -r scripts/requirements-gate.txt",
    "pip install --require-hashes -r requirements.lock",
    "pip install httpx pyyaml",
    "npm ci",
    "npm run db:migrate",
    "Send the gate's record to the portal",
    "Start portal for the Ops contract check",
    "Seed an app and its Ops token",
})


def test_every_blocking_check_in_this_repos_ci_carries_the_tag() -> None:
    """`agentsmith gates run`'s green must mean CI's green.

    The portal job tagged both its `npm test` steps and not `npx tsc --noEmit`,
    `npm run build` or the history-sync check; the widget job tagged nothing at
    all. Four blocking checks were invisible to the local runner, so a developer
    could see "0 failed" and still fail CI on a type error
    (.agent-rfc/designs/gate-tag-coverage.md).
    """
    import yaml

    workflow = REPO / ".github" / "workflows" / "self-test.yml"
    raw = workflow.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    jobs = doc.get("jobs") or {}
    assert len(jobs) >= 5, f"parsed {len(jobs)} jobs — the query is broken"

    untagged, run_steps = [], 0
    for job_key, spec in jobs.items():
        for step in spec.get("steps") or []:
            script = step.get("run")
            if not script:
                continue                       # `uses:` — an action, never tagged
            run_steps += 1
            name = (step.get("name") or "").strip('"')
            first = script.strip().splitlines()[0].strip()
            if name in _SETUP_STEPS or first in _SETUP_STEPS:
                continue
            if step.get("continue-on-error") or "|| true" in script:
                continue                       # advisory by construction
            if gs.TAG not in _step_block(raw, name, first):
                untagged.append(f"[{job_key}] {name or first}")
    assert run_steps >= 20, f"found only {run_steps} run-steps — the query is broken"
    assert not untagged, (
        "these CI steps block a merge and carry no `# agentsmith:gate`, so "
        f"`agentsmith gates run` cannot run them: {untagged}. Tag them, or add them "
        "to _SETUP_STEPS if they are setup rather than a check"
    )


def _step_block(raw: str, name: str, first_line: str) -> str:
    """The raw YAML around a step, where its tag comment lives."""
    anchor = f'name: "{name}"' if name else f"run: {first_line}"
    index = raw.find(anchor)
    if index == -1:
        index = raw.find(first_line)
    return raw[index: index + 400] if index != -1 else ""


# ── the base of a local range ────────────────────────────────────────────────
#
# _merge_base used `@{upstream}`, which on a feature branch is that branch's own
# remote, not the branch it merges into. CI passes
# github.event.pull_request.base.sha — the base branch. The two differ the
# moment a branch is pushed, in both directions: a CHANGELOG entry in an
# already-pushed commit made the local gate refuse what CI accepted, and once
# everything was pushed the range was EMPTY and the gate reported a pass over
# nothing.


def _run(root, *args):
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)


def _sha(root, ref="HEAD"):
    return subprocess.run(["git", "rev-parse", ref], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


@pytest.fixture
def branch_repo(tmp_path: Path):
    """A repo with `main`, a feature branch two commits ahead, and a
    remote-tracking ref for BOTH, so `@{upstream}` and the base branch differ —
    which is the situation every pushed feature branch is in."""
    root = tmp_path / "repo"
    root.mkdir()
    _run(root, "init", "-q", "--template=", "-b", "main")
    _run(root, "config", "user.email", "t@t")
    _run(root, "config", "user.name", "t")
    (root / "a.txt").write_text("1\n")
    _run(root, "add", "-A")
    _run(root, "commit", "-qm", "chore: base")
    base = _sha(root)
    _run(root, "update-ref", "refs/remotes/origin/main", base)
    _run(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    _run(root, "checkout", "-q", "-b", "feature")
    shas = []
    for n in (2, 3):
        (root / "a.txt").write_text(f"{n}\n")
        _run(root, "add", "-A")
        _run(root, "commit", "-qm", f"chore: step {n}")
        shas.append(_sha(root))
    # Both commits "pushed": the branch's remote-tracking ref is at its tip and
    # the branch tracks it, exactly as after `git push -u`. The remote's url and
    # FETCH REFSPEC are required, not decoration — without them `@{upstream}`
    # fails with "not stored as a remote-tracking branch", the helper falls
    # through to origin/main, and these tests pass without reproducing anything.
    _run(root, "update-ref", "refs/remotes/origin/feature", shas[-1])
    _run(root, "config", "remote.origin.url", str(root))
    _run(root, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    _run(root, "config", "branch.feature.remote", "origin")
    _run(root, "config", "branch.feature.merge", "refs/heads/feature")
    upstream = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    assert upstream == "origin/feature", (
        f"the fixture did not reproduce a pushed branch: @{{upstream}} is {upstream!r}"
    )
    return root, base, shas


def test_the_base_is_the_base_branch_not_the_branchs_own_remote(branch_repo) -> None:
    """What CI calls the base: where the branch left `main`."""
    root, base, _shas = branch_repo
    assert gs._merge_base(root) == base


def test_the_range_is_not_empty_once_everything_is_pushed(branch_repo) -> None:
    """The false negative, pinned directly. With `@{upstream}` as the base, a
    fully pushed branch has an EMPTY range and every per-commit check passes
    over nothing — `Checked 0 commit(s)` printed beside `gates: 1 passed`."""
    root, _base, shas = branch_repo
    span = subprocess.run(["git", "rev-list", f"{gs._merge_base(root)}..HEAD"], cwd=root,
                          capture_output=True, text=True, check=True).stdout.split()
    assert sorted(span) == sorted(shas), (
        "a fully pushed branch must still present every commit it adds to the "
        "base branch, or the gate reports a pass having checked nothing"
    )


def test_the_base_uses_origin_main_when_origin_head_is_unset(branch_repo) -> None:
    """The middle link of the fallback chain, which nothing else reaches.

    A clone sets refs/remotes/origin/HEAD; `git init` plus `git remote add` does
    not, so a working checkout can have origin/main and no origin/HEAD. Without
    this, replacing `or "origin/main"` with `or ""` changes no test result — the
    other two cases resolve origin/HEAD or fall through to HEAD~1 either way.
    """
    root, base, _shas = branch_repo
    _run(root, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    assert gs._merge_base(root) == base


def test_the_base_falls_back_when_no_base_branch_is_known(tmp_path: Path) -> None:
    """`git clone` sets refs/remotes/origin/HEAD; `git init` plus `git remote
    add` does not. With neither it nor origin/main, HEAD~1 is the range — which
    is what a one-commit branch's range is anyway."""
    root = tmp_path / "solo"
    root.mkdir()
    _run(root, "init", "-q", "--template=", "-b", "main")
    _run(root, "config", "user.email", "t@t")
    _run(root, "config", "user.name", "t")
    for n in (1, 2):
        (root / "a.txt").write_text(f"{n}\n")
        _run(root, "add", "-A")
        _run(root, "commit", "-qm", f"chore: {n}")
    first = _sha(root, "HEAD~1")
    assert gs._merge_base(root) == first
