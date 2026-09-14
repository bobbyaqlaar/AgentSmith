"""
scripts/test/test_process_gate.py — the gates that make design-before-code and
review-before-merge more than advice (docs/process-gates.md).

Every check is tested by forcing its violation, and every caller — the Claude
Code hooks in .claude/settings.json, .githooks/commit-msg, the Self-Test job —
is tested by running it, because a gate nothing invokes is the failure this
file exists to prevent.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / "scripts" / "process_gate.py"
sys.path.insert(0, str(REPO / "scripts"))
import process_gate as pg

needs_git = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None, reason="git+bash")
SLUGS = pg.lever_slugs((REPO / "docs" / "review-levers.md").read_text(encoding="utf-8"))

DESIGN = """---
status: active
scope:
  - scripts/lib/**
  - scripts/tool.py
---
# A change

## Problem
Something.

## Approach
Something else.

## Levers
- `gate-integrity` — it can fail.
"""
REVIEW_CLEAN = "# Review\n\n## Pass 1 — findings: 2\n- a\n- b\n\n## Pass 2 — findings: 0\n"


# ── The catalog ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("path", "gated"),
    [
        ("scripts/process_gate.py", True),
        ("runtime/test/test_x.py", True),
        (".github/workflows/self-test.yml", True),
        ("install-ai-stack.sh", True),
        ("requirements-lint.txt", True),
        (".claude/settings.json", True),
        ("docs/process-gates.md", False),
        ("portal/README.md", False),
        (".agent-rfc/fixtures/knowledge_graph.json", False),
        ("portal/node_modules/x/index.js", False),
        ("CHANGELOG.md", False),
        (".claude/settings.local.json", False),
    ],
)
def test_what_is_gated(path, gated):
    assert pg.is_gated(path) is gated


def test_tenant_facing_paths_are_what_scratch_tenants_rebuilds_on():
    """Two lists of 'what a tenant receives'. The workflow's also names its own
    two files; everything else must agree, parsed from the YAML."""
    doc = yaml.safe_load((REPO / ".github/workflows/scratch-tenants.yml").read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))
    paths = on["push"]["paths"]
    include = {p for p in paths if not p.startswith("!")} - {
        ".github/scratch-tenants/**", ".github/workflows/scratch-tenants.yml",
    }
    exclude = {p[1:] for p in paths if p.startswith("!")}
    assert include == set(pg.TENANT_FACING)
    assert exclude == set(pg.TENANT_FACING_EXCEPT)


def test_glob_semantics():
    assert pg.glob_match("a/b/c.py", "a/**")
    assert pg.glob_match("requirements-lint.txt", "requirements*.txt")
    assert not pg.glob_match("a/b/c.py", "a/*")
    assert not pg.glob_match("xscripts/a.py", "scripts/**")


def test_runs_on_python_39_syntax():
    """Hooks run the PATH python3 — 3.9 on a stock Mac."""
    ast.parse(GATE.read_text(encoding="utf-8"), feature_version=(3, 9))


# ── Records ──────────────────────────────────────────────────────────────────


def test_a_complete_design_passes():
    assert pg.check_design(DESIGN, SLUGS) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d.replace("status: active", "status: draft"), "status is 'draft'"),
        (lambda d: d.replace("scope:\n  - scripts/lib/**\n  - scripts/tool.py\n", "scope:\n"), "scope lists no paths"),
        (lambda d: d.replace("## Approach", "## Plan"), "no '## Approach'"),
        (lambda d: d.replace("`gate-integrity`", "`not-a-lever`"), "cites no lever"),
        (lambda d: d.split("---\n", 2)[2], "no front matter"),
    ],
)
def test_an_incomplete_design_fails(mutate, expected):
    errors = pg.check_design(mutate(DESIGN), SLUGS)
    assert any(expected in e for e in errors), errors


@pytest.mark.parametrize(
    ("review", "expected"),
    [
        ("# nothing\n", "records no passes"),
        ("## Pass 1 — findings: 3\n", "reports 3 finding"),
        ("## Pass 1 — findings: 1\n## Pass 3 — findings: 0\n", "numbered [1, 3]"),
    ],
)
def test_an_unclean_review_fails(review, expected):
    assert any(expected in e for e in pg.check_review(review))


def test_a_clean_review_passes_with_any_dash():
    assert pg.check_review(REVIEW_CLEAN) == []
    assert pg.check_review("## Pass 1 - findings: 0\n") == []


@pytest.mark.parametrize(
    "value",
    ["../../etc/passwd.md", ".agent-rfc/designs/../reviews/x.md", ".agent-rfc/designs/sub/x.md",
     ".agent-rfc/designs/x.txt", "/abs/.agent-rfc/designs/x.md", ".agent-rfc/designs/.hidden.md"],
)
def test_a_trailer_may_only_name_a_record_file(value):
    path, error = pg.resolve_record(value, pg.DESIGNS_DIR)
    assert path is None and error


# ── One commit against its trailers ──────────────────────────────────────────

FILES = {
    ".agent-rfc/designs/change.md": DESIGN,
    ".agent-rfc/reviews/change.md": REVIEW_CLEAN,
}
MESSAGE = "feat: x\n\nDesign: .agent-rfc/designs/change.md\nReview: .agent-rfc/reviews/change.md\n"


def _check(files, message=MESSAGE, lines=50, store=None):
    store = dict(FILES if store is None else store)
    return pg.check_change(files, lines, message, store.get, SLUGS)


def test_a_commit_with_no_gated_paths_needs_nothing():
    assert _check(["docs/a.md", "README.md"], message="docs: x") == ([], [])


def test_a_complete_commit_passes():
    assert _check(["scripts/lib/a.py", ".agent-rfc/reviews/change.md"]) == ([], [])


def test_missing_trailers_are_named_separately():
    errors, _ = _check(["scripts/lib/a.py"], message="feat: x")
    assert any("missing 'Design:" in e for e in errors)
    assert any("missing 'Review:" in e for e in errors)


def test_a_trailer_naming_a_missing_file_says_so():
    only_review = {".agent-rfc/reviews/change.md": REVIEW_CLEAN}
    errors, _ = _check(["scripts/lib/a.py", ".agent-rfc/reviews/change.md"], store=only_review)
    assert any("does not exist in this commit" in e for e in errors)


def test_the_design_scope_must_cover_every_gated_file():
    errors, _ = _check(["scripts/lib/a.py", "runtime/b.py", ".agent-rfc/reviews/change.md"])
    assert any("does not cover runtime/b.py" in e for e in errors)


def test_a_review_not_changed_in_the_commit_cannot_vouch_for_it():
    errors, _ = _check(["scripts/lib/a.py"])
    assert any("not changed in this commit" in e for e in errors)


def test_an_unclean_review_blocks_the_commit():
    store = dict(FILES, **{".agent-rfc/reviews/change.md": "## Pass 1 — findings: 2\n"})
    errors, _ = _check(["scripts/lib/a.py", ".agent-rfc/reviews/change.md"], store=store)
    assert any("reports 2 finding" in e for e in errors)


def test_na_is_accepted_for_a_small_change_and_reported():
    message = "fix: typo\n\nDesign: n/a: comment typo\nReview: n/a: comment typo\n"
    errors, notes = _check(["scripts/tool.py"], message=message, lines=2)
    assert errors == []
    assert len(notes) == 2 and "comment typo" in notes[0]


def test_na_is_refused_for_a_large_change():
    message = "feat: big\n\nDesign: n/a: trust me\nReview: n/a: trust me\n"
    errors, _ = _check(["scripts/tool.py"], message=message, lines=pg.SMALL_CHANGE_LINES + 1)
    assert len([e for e in errors if "n/a is allowed only" in e]) == 2


# ── Real git: the commit hook and the CI range ───────────────────────────────


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@x", *args],
        capture_output=True, text=True, check=check,
    )


@pytest.fixture()
def gated_repo(tmp_path, monkeypatch):
    """A repo carrying the real gate, the real levers doc and the real hook."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    for rel in ("scripts/process_gate.py", "docs/review-levers.md", ".githooks/commit-msg"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, repo / rel)
    (repo / ".githooks/commit-msg").chmod(0o755)
    _git(repo, "add", "-A")
    _git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "chore: base", "--no-verify")
    _git(repo, "config", "core.hooksPath", ".githooks")
    return repo


def _write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text)


def _commit(repo: Path, message: str) -> subprocess.CompletedProcess:
    _git(repo, "add", "-A")
    return _git(repo, "commit", "-q", "-m", message, check=False)


@needs_git
def test_the_commit_hook_blocks_a_gated_commit_without_trailers(gated_repo):
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    result = _commit(gated_repo, "feat: add tool")
    assert result.returncode != 0
    assert "missing 'Design:" in result.stderr


@needs_git
def test_the_commit_hook_accepts_a_designed_and_reviewed_commit(gated_repo):
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    result = _commit(gated_repo, MESSAGE.replace("feat: x", "feat: add tool"))
    assert result.returncode == 0, result.stderr


@needs_git
def test_amending_a_gated_commit_is_checked_like_the_commit_it_replaces(gated_repo):
    """An amend that changes only the message used to look like an empty
    change, and passed without trailers."""
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "feat: sneak", "--no-verify")

    amended = _git(gated_repo, "commit", "-q", "--amend", "-m", "feat: sneak, amended", check=False)

    assert amended.returncode != 0
    assert "missing 'Design:" in amended.stderr


@needs_git
def test_the_commit_hook_still_enforces_conventional_commits(gated_repo):
    _write(gated_repo, "notes.txt", "x\n")
    result = _commit(gated_repo, "added notes")
    assert result.returncode != 0 and "Conventional Commit" in result.stderr


def _ci(repo: Path, base: str, head: str = "HEAD", summary: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if summary:
        env["GITHUB_STEP_SUMMARY"] = str(summary)
    return subprocess.run(
        [sys.executable, "scripts/process_gate.py", "ci", "--base", base, "--head", head],
        cwd=repo, capture_output=True, text=True, check=False, env=env,
    )


@needs_git
def test_ci_fails_a_pushed_range_containing_an_ungated_commit(gated_repo, tmp_path):
    base = _git(gated_repo, "rev-parse", "HEAD").stdout.strip()
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "feat: sneak", "--no-verify")    # the hook bypassed locally
    summary = tmp_path / "summary.md"

    result = _ci(gated_repo, base, summary=summary)

    assert result.returncode == 1
    assert "feat: sneak" in result.stdout and "::error title=Process gate" in result.stdout
    assert "feat: sneak" in summary.read_text()


@needs_git
def test_ci_passes_a_compliant_range_and_requires_changelog_for_tenant_facing_paths(gated_repo):
    base = _git(gated_repo, "rev-parse", "HEAD").stdout.strip()
    _write(gated_repo, "scripts/tool.py", "print(1)\n")      # scripts/ is tenant-facing
    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    assert _commit(gated_repo, MESSAGE).returncode == 0

    without = _ci(gated_repo, base)
    assert without.returncode == 1 and "CHANGELOG.md" in without.stdout

    _write(gated_repo, "CHANGELOG.md", "## [Unreleased]\n- tool\n")
    assert _commit(gated_repo, "docs: changelog").returncode == 0
    assert _ci(gated_repo, base).returncode == 0


@needs_git
def test_ci_lists_every_na_escape_in_its_summary(gated_repo, tmp_path):
    base = _git(gated_repo, "rev-parse", "HEAD").stdout.strip()
    _write(gated_repo, "pytest.ini", "[pytest]\n")        # gated, not tenant-facing
    message = "fix: pin\n\nDesign: n/a: one-line config\nReview: n/a: one-line config\n"
    assert _commit(gated_repo, message).returncode == 0
    summary = tmp_path / "summary.md"

    result = _ci(gated_repo, base, summary=summary)

    assert result.returncode == 0, result.stdout
    assert summary.read_text().count("one-line config") == 2
    assert "⚠️" in summary.read_text()


@needs_git
def test_ci_with_no_base_checks_the_head_commit_and_says_so(gated_repo):
    _write(gated_repo, "scripts/lib/a.py", "x = 1\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "feat: new branch", "--no-verify")

    result = _ci(gated_repo, "0" * 40)

    assert result.returncode == 1
    assert "checked the head commit only" in result.stdout


# ── The Claude Code hooks ────────────────────────────────────────────────────


def _hook(repo: Path, command: str, payload) -> subprocess.CompletedProcess:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(repo / "scripts/process_gate.py"), command],
        input=raw, capture_output=True, text=True, check=False, cwd=repo,
    )


def _decision(result: subprocess.CompletedProcess):
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] if result.stdout.strip() else "allow"


@needs_git
def test_pre_edit_denies_an_uncovered_gated_path_and_allows_a_covered_one(gated_repo):
    def edit(rel):
        return {"tool_name": "Edit", "tool_input": {"file_path": str(gated_repo / rel)},
                "cwd": str(gated_repo)}
    assert _decision(_hook(gated_repo, "pre-edit", edit("scripts/lib/a.py"))) == "deny"
    assert _decision(_hook(gated_repo, "pre-edit", edit("docs/notes.md"))) == "allow"

    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    assert _decision(_hook(gated_repo, "pre-edit", edit("scripts/lib/a.py"))) == "allow"
    assert _decision(_hook(gated_repo, "pre-edit", edit("runtime/b.py"))) == "deny", "outside the scope"

    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN.replace("status: active", "status: done"))
    finished = _hook(gated_repo, "pre-edit", edit("scripts/lib/a.py"))
    assert _decision(finished) == "deny", "a finished design unlocks nothing"


@needs_git
def test_pre_edit_does_not_accept_a_stub_design(gated_repo):
    _write(gated_repo, ".agent-rfc/designs/stub.md", "---\nstatus: active\nscope:\n  - scripts/lib/**\n---\n# todo\n")
    target = str(gated_repo / "scripts/lib/a.py")
    edit = {"tool_name": "Write", "tool_input": {"file_path": target}, "cwd": str(gated_repo)}
    result = _hook(gated_repo, "pre-edit", edit)
    assert _decision(result) == "deny"
    assert "not complete" in result.stdout


@needs_git
def test_pre_edit_fails_closed_on_input_it_cannot_read(gated_repo):
    result = _hook(gated_repo, "pre-edit", "{not json")
    assert _decision(result) == "deny"


@needs_git
def test_stop_blocks_unreviewed_changes_then_does_not_loop(gated_repo):
    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, "scripts/lib/a.py", "x = 1\n")
    payload = {"cwd": str(gated_repo), "stop_hook_active": False}

    first = json.loads(_hook(gated_repo, "stop", payload).stdout)
    assert first["decision"] == "block" and "no review record" in first["reason"]

    again = json.loads(_hook(gated_repo, "stop", dict(payload, stop_hook_active=True)).stdout)
    assert "decision" not in again and "Unreviewed" in again["systemMessage"]


@needs_git
def test_stop_requires_the_review_to_be_newer_than_the_change(gated_repo):
    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(gated_repo, "scripts/lib/a.py", "x = 1\n")
    past = time.time() - 3600
    os.utime(gated_repo / ".agent-rfc/reviews/change.md", (past, past))
    payload = {"cwd": str(gated_repo), "stop_hook_active": False}

    stale = json.loads(_hook(gated_repo, "stop", payload).stdout)
    assert "last updated before the newest change" in stale["reason"]

    os.utime(gated_repo / ".agent-rfc/reviews/change.md", None)
    assert _hook(gated_repo, "stop", payload).stdout.strip() == ""


@needs_git
def test_stop_catches_a_gated_change_no_design_covers(gated_repo):
    """An edit made through Bash never met the edit gate; the stop gate sees it."""
    _write(gated_repo, "runtime/b.py", "x = 1\n")
    result = json.loads(_hook(gated_repo, "stop", {"cwd": str(gated_repo)}).stdout)
    assert "runtime/b.py: no complete active design note covers it" in result["reason"]


@needs_git
def test_session_start_states_the_rules_and_an_unarmed_commit_gate(gated_repo):
    _git(gated_repo, "config", "--unset", "core.hooksPath")
    context = json.loads(_hook(gated_repo, "session-start", {"cwd": str(gated_repo)}).stdout)
    text = context["hookSpecificOutput"]["additionalContext"]
    assert "design-review-checklist.md" in text and "review-levers.md" in text
    assert "git config core.hooksPath .githooks" in text


@needs_git
def test_session_start_names_missing_agent_files_only_when_they_are_missing(gated_repo):
    _write(gated_repo, "scripts/generate-ide-config.py", "# stub\n")
    def context():
        out = json.loads(_hook(gated_repo, "session-start", {"cwd": str(gated_repo)}).stdout)
        return out["hookSpecificOutput"]["additionalContext"]
    assert "generate-ide-config.py --repo-root ." in context()
    _write(gated_repo, "AGENTS.md", "# rules\n")
    assert "generate-ide-config.py" not in context()


# ── Every caller invokes a real subcommand ───────────────────────────────────


def _subcommands() -> set:
    return {"session-start", "pre-edit", "stop", "commit-msg", "ci"}


def test_claude_settings_wire_all_three_agent_hooks():
    hooks = json.loads((REPO / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    commands = {event: [h["command"] for m in entries for h in m["hooks"]] for event, entries in hooks.items()}
    assert any("process_gate.py\" session-start" in c for c in commands["SessionStart"])
    assert any("process_gate.py\" stop" in c for c in commands["Stop"])
    pre = [m for m in hooks["PreToolUse"] if any("process_gate.py\" pre-edit" in h["command"] for h in m["hooks"])]
    assert pre and {"Edit", "Write", "MultiEdit", "NotebookEdit"} <= set(pre[0]["matcher"].split("|"))
    for event_commands in commands.values():
        for command in event_commands:
            invoked = command.split("process_gate.py\" ", 1)[1].split()[0]
            assert invoked in _subcommands()


@needs_git
def test_the_edit_gate_fails_closed_when_the_gate_cannot_run(tmp_path):
    """Claude Code lets an edit through when a PreToolUse hook exits non-zero —
    so python3 missing, or the script dying before it answers, must still deny."""
    hooks = json.loads((REPO / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    command = hooks["PreToolUse"][0]["hooks"][0]["command"]
    result = subprocess.run(
        ["bash", "-c", command], input="{}", capture_output=True, text=True, check=False,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path)),     # no scripts/process_gate.py here
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_self_test_runs_the_ci_gate_over_the_pushed_range():
    workflow = yaml.safe_load((REPO / ".github/workflows/self-test.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["process-gates"]
    checkout = job["steps"][0]
    assert checkout["with"]["fetch-depth"] == 0, "a shallow clone has no range to check"
    step = next(s for s in job["steps"] if "process_gate.py ci" in s.get("run", ""))
    assert "github.event.before" in step["env"]["BASE"] and "pull_request.base.sha" in step["env"]["BASE"]


def test_the_commit_hook_calls_the_gate():
    text = (REPO / ".githooks/commit-msg").read_text(encoding="utf-8")
    assert 'process_gate.py" commit-msg "${amend[@]+"${amend[@]}"}" "$msg_file"' in text
    assert os.access(REPO / ".githooks/commit-msg", os.X_OK)
