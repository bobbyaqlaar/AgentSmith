"""
scripts/test/test_process_gate.py — the gates that make design-before-code and
review-before-merge more than advice (docs/process-gates.md).

Every check is tested by forcing its violation, and every caller — the Claude
Code hooks in .claude/settings.json, .githooks/commit-msg and the launcher
.githooks/process-gate, the Self-Test job — is tested by running it, because a
gate nothing invokes is the failure this file exists to prevent. The same
script serves tenants through their own .agenticframework/process-gates.json,
so the tenant shapes (a vendored copy, an installed-mode repo reading
@framework/ docs) are exercised here too.
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
CONFIG_PATH = REPO / ".agenticframework" / "process-gates.json"
sys.path.insert(0, str(REPO / "scripts"))
import process_gate as pg

needs_git = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None, reason="git+bash")
LEVERS = (REPO / "docs" / "review-levers.md").read_text(encoding="utf-8")
SLUGS = pg.lever_slugs(LEVERS)
# AgentSmith's own config, with one rule turned off for these tests: the
# `KG query:` hash is computed from each commit's file set, so a shared review
# constant cannot carry one, and every commit test in this file would end up
# asserting about the knowledge graph instead of the rule it is about. That
# rule has its own tests, which turn it back on (test_gate_kg.py).
FIXTURE_CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
FIXTURE_CONFIG["knowledge_graph"] = "off"
# And `artifacts` in `report`, for the same reason: AgentSmith enforces one
# document per type since its migration, and a fixture repo has none of the six
# — every stop and sweep in these tests would block on documents they are not
# about. test_gate_artifacts.py sets the mode each of its tests needs.
FIXTURE_CONFIG["artifacts"] = "report"
AGENTSMITH = pg.Config(dict(FIXTURE_CONFIG))
REGISTRY = AGENTSMITH.load_registry(lambda _p: None)[0]
DESIGN_PILLARS = ", ".join(f"P{p.id}" for p in REGISTRY.pillars if "design" in p.check)

# What a pillar answer names, once a repo is held to the evidence rule: a
# path this fixture repo really tracks.
TOKEN = "`scripts/process_gate.py`"

DESIGN = f"""---
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

## Pillars
- {DESIGN_PILLARS} applies — each was worked for {TOKEN}.

## Deviations
none

## Dependencies
none

## Levers
- `gate-integrity` — it can fail.
"""
SIGNOFF = """
## Sign-off

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no session

Tests added/updated:      test_tool.py
Mutation-checked:          yes — guard removed, test fails
Fixtures re-pinned:        n/a
Gates run locally:         pytest
```
"""
REVIEW_CLEAN = "# Review\n\n## Pass 1 — findings: 2\n- a\n- b\n\n## Pass 2 — findings: 0\n" + SIGNOFF


# ── AgentSmith's own configuration ───────────────────────────────────────────


def test_agentsmith_config_is_valid_and_gates_itself():
    assert pg.parse_config(CONFIG_PATH.read_text(encoding="utf-8"))[1] == []
    assert AGENTSMITH.is_gated(pg.CONFIG)


@pytest.mark.parametrize(
    ("path", "gated"),
    [
        ("scripts/process_gate.py", True),
        ("runtime/test/test_x.py", True),
        (".github/workflows/self-test.yml", True),
        ("install-ai-stack.sh", True),
        ("requirements-lint.txt", True),
        (".claude/settings.json", True),
        (".githooks/process-gate", True),
        ("docs/process-gates.md", False),
        ("portal/README.md", False),
        (".agent-rfc/fixtures/knowledge_graph.json", False),
        ("portal/node_modules/x/index.js", False),
        ("CHANGELOG.md", False),
        (".claude/settings.local.json", False),
    ],
)
def test_what_agentsmith_gates(path, gated):
    assert AGENTSMITH.is_gated(path) is gated


def test_agentsmith_changelog_paths_are_what_scratch_tenants_rebuilds_on():
    """Two lists of 'what a tenant receives'. The workflow also names its own
    two files; everything else must agree, parsed from both sides."""
    doc = yaml.safe_load((REPO / ".github/workflows/scratch-tenants.yml").read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))
    paths = on["push"]["paths"]
    include = {p for p in paths if not p.startswith("!")} - {
        ".github/scratch-tenants/**", ".github/workflows/scratch-tenants.yml",
    }
    exclude = {p[1:] for p in paths if p.startswith("!")}
    assert AGENTSMITH.changelog_file == "CHANGELOG.md"
    assert include == set(AGENTSMITH.changelog_paths)
    assert exclude == set(AGENTSMITH.changelog_except)


def test_the_script_holds_no_catalog_of_its_own():
    """One catalog per repo, in its config. A default list in the code would be
    a second catalog for whichever repo also has a config."""
    source = GATE.read_text(encoding="utf-8")
    for layout_path in ('"portal/**"', '"workflow-templates/**"', '"install-ai-stack.sh"'):
        assert layout_path not in source


def test_glob_semantics():
    assert pg.glob_match("a/b/c.py", "a/**")
    assert pg.glob_match("requirements-lint.txt", "requirements*.txt")
    assert not pg.glob_match("a/b/c.py", "a/*")
    assert not pg.glob_match("xscripts/a.py", "scripts/**")


def test_an_old_interpreter_can_still_say_why_it_cannot_gate():
    """The gate runs in the framework environment (3.11+, pydantic, OTel), but a
    stock Mac's python3 is 3.9: run by it, the file must parse and name the
    problem (exit 3, so the launcher tries the next interpreter) rather than die
    on a syntax error the hook reports as nothing."""
    ast.parse(GATE.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_a_design_must_answer_every_pillar_it_is_asked():
    without = DESIGN.replace(f"- {DESIGN_PILLARS} applies", "- P1 applies")
    errors = _design_errors(without)
    assert any("does not answer P3" in e for e in errors), errors


def test_a_design_with_an_unapproved_deviation_is_incomplete():
    deviating = DESIGN.replace("## Deviations\nnone", "## Deviations\n- D1 — P3 — no spans — approval: A-0123abcd")
    errors = _design_errors(deviating)
    assert any("A-0123abcd" in e and "agentsmith approve" in e for e in errors), errors
    approval = pg.gm.Approval(
        id="A-0123abcd", design=".agent-rfc/designs/change.md", deviation="D1",
        approver="o", approved_at="2026-09-15T00:00:00Z", channel="tty", statement="ok")
    assert _design_errors(deviating, approvals=[approval]) == []


def test_a_review_without_a_signoff_is_not_clean():
    errors = pg.check_review(REVIEW_CLEAN.replace(SIGNOFF, ""), REGISTRY)
    assert any("Sign-off" in e for e in errors), errors


def test_a_missing_registry_blocks_rather_than_checking_less():
    config = pg.Config({"gated": ["**"], "registry": "templates/nowhere.json"})
    registry, problems = config.load_registry(lambda _p: None)
    assert registry is None and "does not exist" in problems[0]
    errors, _ = pg.check_change(["scripts/a.py"], 50, MESSAGE, dict(FILES).get, config)
    assert errors == problems


def test_extends_cannot_redefine_a_framework_pillar():
    config = pg.Config({"gated": ["**"], "extends": {"pillars": [{"id": 3, "name": "mine", "check": ["review"]}]}})
    registry, problems = config.load_registry(lambda _p: None)
    assert registry is None and "P3" in problems[0]


# ── Config validation ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("{not json", "not valid JSON"),
        ("[]", "must be a JSON object"),
        ('{"gated": []}', "declares no gated paths"),
        ('{"gated": ["src/**"]}', "must gate itself"),
        ('{"gated": ["**"], "not_gated": [".agenticframework/**"]}', "must gate itself"),
        ('{"gated": ["**"], "changelog": {"file": "CHANGELOG.md"}}', "no paths that require it"),
    ],
)
def test_a_broken_config_is_named(text, expected):
    _, problems = pg.parse_config(text)
    assert any(expected in p for p in problems), problems


def test_no_config_means_not_adopted():
    assert pg.parse_config(None) == (None, [])


def test_framework_docs_resolve_beside_the_running_script():
    config = pg.Config({"gated": ["**"], "levers_doc": "@framework/docs/review-levers.md"})
    assert config.doc_text(config.levers_doc, lambda _p: None) == LEVERS
    assert "AgentSmith checkout" in config.display(config.levers_doc)


# ── Records ──────────────────────────────────────────────────────────────────


DESIGN_PATH = ".agent-rfc/designs/change.md"


def _design_errors(text, approvals=()):
    return pg.check_design(text, SLUGS, "docs/review-levers.md", REGISTRY, list(approvals), DESIGN_PATH)


def test_a_complete_design_passes():
    assert _design_errors(DESIGN) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d.replace("status: active", "status: draft"), "status is 'draft'"),
        (lambda d: d.replace("scope:\n  - scripts/lib/**\n  - scripts/tool.py\n", "scope:\n"), "scope lists no paths"),
        (lambda d: d.replace("## Approach", "## Plan"), "no '## Approach'"),
        (lambda d: d.replace("## Pillars", "## Notes"), "no '## Pillars'"),
        (lambda d: d.replace("## Deviations\nnone\n", ""), "no '## Deviations'"),
        (lambda d: d.replace("## Dependencies", "## Deps"), "no '## Dependencies'"),
        (lambda d: d.replace("`gate-integrity`", "`not-a-lever`"), "cites no lever"),
        (lambda d: d.split("---\n", 2)[2], "no front matter"),
    ],
)
def test_an_incomplete_design_fails(mutate, expected):
    errors = _design_errors(mutate(DESIGN))
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
    assert any(expected in e for e in pg.check_review(review, REGISTRY))


def test_a_clean_review_passes_with_any_dash():
    assert pg.check_review(REVIEW_CLEAN, REGISTRY) == []
    assert pg.check_review("## Pass 1 - findings: 0\n" + SIGNOFF, REGISTRY) == []


def test_a_heading_that_does_not_parse_is_named_not_counted_as_a_gap():
    """`_PASS` anchors on `\\s*$`, so a heading with anything after the count is
    INVISIBLE — and `check_review` then reported the hole it left as a numbering
    error. Written after three reviews in one session were refused with "passes
    are numbered [1, 2, 3, 5]" when the real fault was
    `## Pass 4 — findings: 1 (CI, 2026-09-24)`: one message for two causes, and
    it sends the author to the numbers instead of the syntax
    (.agent-rfc/designs/audit-notes-resolved.md).
    """
    text = ("## Pass 1 — findings: 2\n"
            "## Pass 2 — findings: 1 (CI, 2026-09-24)\n"
            "## Pass 3 — findings: 0\n" + SIGNOFF)
    errors = pg.check_review(text, REGISTRY)
    assert any("did not parse" in e for e in errors), errors
    assert any("(CI, 2026-09-24)" in e for e in errors), (
        "the message must quote the line, so the author can see what is wrong with it", errors)
    assert not any("numbered" in e for e in errors), (
        "an unparseable heading must not be reported as a numbering gap", errors)


def test_a_real_numbering_gap_is_still_reported_as_one():
    """The diagnosis above must not swallow the case it was confused with."""
    text = "## Pass 1 — findings: 1\n## Pass 3 — findings: 0\n" + SIGNOFF
    errors = pg.check_review(text, REGISTRY)
    assert any("numbered" in e for e in errors), errors
    assert not any("did not parse" in e for e in errors), errors


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
    "docs/review-levers.md": LEVERS,
}
MESSAGE = "feat: x\n\nDesign: .agent-rfc/designs/change.md\nReview: .agent-rfc/reviews/change.md\n"


def _check(files, message=MESSAGE, lines=50, store=None, config=AGENTSMITH):
    store = dict(FILES if store is None else store)
    return pg.check_change(files, lines, message, store.get, config)


def test_a_commit_with_no_gated_paths_needs_nothing():
    assert _check(["docs/a.md", "README.md"], message="docs: x") == ([], [])


def test_a_complete_commit_passes():
    assert _check(["scripts/lib/a.py", ".agent-rfc/reviews/change.md"]) == ([], [])


def test_missing_trailers_are_named_separately():
    errors, _ = _check(["scripts/lib/a.py"], message="feat: x")
    assert any("missing 'Design:" in e for e in errors)
    assert any("missing 'Review:" in e for e in errors)


def test_a_trailer_naming_a_missing_file_says_so():
    without_design = {k: v for k, v in FILES.items() if "designs" not in k}
    errors, _ = _check(["scripts/lib/a.py", ".agent-rfc/reviews/change.md"], store=without_design)
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


def test_levers_come_from_the_repos_configured_doc():
    """OTS validates against its OWN review-levers.md, which extends the
    framework's: a lever that exists only there must count there."""
    local = LEVERS + "\n- `ots-only-lever` — a repo-local addition.\n"
    config = pg.Config({"gated": ["scripts/**", pg.CONFIG], "levers_doc": "docs/local-levers.md"})
    design = DESIGN.replace("`gate-integrity`", "`ots-only-lever`")
    store = {".agent-rfc/designs/change.md": design, ".agent-rfc/reviews/change.md": REVIEW_CLEAN,
             "docs/local-levers.md": local}
    assert _check(["scripts/lib/a.py", ".agent-rfc/reviews/change.md"], store=store, config=config) == ([], [])
    assert _check(["scripts/lib/a.py", ".agent-rfc/reviews/change.md"], store=store)[0], \
        "the framework's own doc must not know the local lever"


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


def _make_repo(tmp_path: Path, name: str, files: dict, monkeypatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # HOME moved, so ~/.agent-framework/.venv is gone: name the interpreter
    # running these tests, which has the framework environment.
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    monkeypatch.setenv("AGENTSMITH_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("AGENTSMITH_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    for rel, source in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, Path) and source.is_dir():
            shutil.copytree(source, repo / rel, ignore=shutil.ignore_patterns("__pycache__", "test", "k8s"))
        elif isinstance(source, Path):
            shutil.copy(source, repo / rel)
        else:
            (repo / rel).write_text(source)
    for hook in HOOK_FILES:
        if (repo / hook).exists():
            (repo / hook).chmod(0o755)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: base", "--no-verify")
    _git(repo, "config", "core.hooksPath", ".githooks")
    return repo


HOOK_FILES = {
    ".githooks/commit-msg": REPO / ".githooks/commit-msg",
    ".githooks/process-gate": REPO / ".githooks/process-gate",
    ".githooks/pre-commit": REPO / ".githooks/pre-commit",
    ".githooks/pre-push": REPO / ".githooks/pre-push",
}
# What a vendored copy of the gate carries: the script, its models and tracing,
# the registry beside it, and the runtime its spans go through.
GATE_FILES = {
    "scripts/process_gate.py": GATE,
    "scripts/gate_models.py": REPO / "scripts/gate_models.py",
    "scripts/gate_ides.py": REPO / "scripts/gate_ides.py",
    "scripts/gate_pillars.py": REPO / "scripts/gate_pillars.py",
    "scripts/gate_shell.py": REPO / "scripts/gate_shell.py",
    "scripts/gate_kg.py": REPO / "scripts/gate_kg.py",
    "scripts/gate_history.py": REPO / "scripts/gate_history.py",
    "scripts/local_knowledge_graph.py": REPO / "scripts/local_knowledge_graph.py",
    # local_knowledge_graph's CLI reaches for the shared helpers; the GATE does
    # not — it imports gate_kg.py, which is why that split exists.
    "scripts/_shared.py": REPO / "scripts/_shared.py",
    "scripts/gate_tracing.py": REPO / "scripts/gate_tracing.py",
    "templates/governance.json": REPO / "templates/governance.json",
    "runtime": REPO / "runtime",
}


@pytest.fixture()
def gated_repo(tmp_path, monkeypatch):
    """A repo shaped like AgentSmith: the gate, its levers doc and its config in-tree."""
    return _make_repo(tmp_path, "repo", {
        **GATE_FILES,
        "docs/review-levers.md": REPO / "docs/review-levers.md",
        pg.CONFIG: json.dumps(FIXTURE_CONFIG, indent=2) + "\n",
        **HOOK_FILES,
    }, monkeypatch)


INSTALLED_CONFIG = json.dumps({
    "gated": ["agents/**", "*.py", ".agenticframework/**", ".githooks/**"],
    "not_gated": ["**.md", ".agent-rfc/**"],
    "levers_doc": "@framework/docs/review-levers.md",
    "design_checklist": "@framework/docs/design-review-checklist.md",
})


@pytest.fixture()
def installed_repo(tmp_path, monkeypatch):
    """A repo shaped like KYC Sentinel: no gate script and no lever docs of its
    own; the hooks find the framework through $AGENTSMITH_DIR."""
    repo = _make_repo(tmp_path, "kyc", {pg.CONFIG: INSTALLED_CONFIG, **HOOK_FILES}, monkeypatch)
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    return repo


def _write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text)


def _commit(repo: Path, message: str) -> subprocess.CompletedProcess:
    _git(repo, "add", "-A")
    return _git(repo, "commit", "-q", "-m", message, check=False)


def test_the_working_tree_reader_returns_a_binary_file_rather_than_crashing(tmp_path):
    """The stop gate reads the working tree. A PNG is not UTF-8, and strict
    decoding crashed it; the file must still read as present
    (.agent-rfc/designs/gate-reads-binary-files.md). The index and commit reader
    is covered end to end in test_gate_kg.py."""
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)))
    read = pg._worktree_reader(tmp_path)
    assert isinstance(read("logo.png"), str)
    assert read("absent.png") is None


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


@needs_git
def test_a_repo_without_config_is_not_gated_locally(gated_repo):
    _git(gated_repo, "rm", "-q", pg.CONFIG)
    _git(gated_repo, "commit", "-qm", "chore: drop config", "--no-verify")
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    assert _commit(gated_repo, "feat: add tool").returncode == 0


@needs_git
def test_a_broken_config_blocks_every_commit(gated_repo):
    _write(gated_repo, pg.CONFIG, '{"gated": ["scripts/**"]}')     # no longer gates itself
    result = _commit(gated_repo, "chore: narrow the gates")
    assert result.returncode != 0 and "must gate itself" in result.stderr


@needs_git
def test_the_first_commit_of_a_repo_is_checked(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "fresh"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    for rel, source in {**GATE_FILES, "docs/review-levers.md": REPO / "docs/review-levers.md",
                        pg.CONFIG: CONFIG_PATH, **HOOK_FILES}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, repo / rel, ignore=shutil.ignore_patterns("__pycache__", "test", "k8s"))
        else:
            shutil.copy(source, repo / rel)
    _git(repo, "config", "core.hooksPath", ".githooks")
    result = _commit(repo, "feat: initial")
    assert result.returncode != 0 and "missing 'Design:" in result.stderr


@needs_git
def test_an_installed_mode_repo_is_gated_through_agentsmith_dir(installed_repo):
    """No script and no lever docs in the repo: the launcher finds the gate in
    $AGENTSMITH_DIR, and @framework/ levers resolve beside it."""
    _write(installed_repo, "agents/intake.py", "x = 1\n")
    assert "missing 'Design:" in _commit(installed_repo, "feat: intake").stderr

    design = DESIGN.replace("scripts/lib/**", "agents/**")
    _write(installed_repo, ".agent-rfc/designs/change.md", design)
    _write(installed_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    result = _commit(installed_repo, MESSAGE.replace("feat: x", "feat: intake"))
    assert result.returncode == 0, result.stderr


@needs_git
def test_the_launcher_fails_safe_when_it_finds_no_gate(installed_repo, monkeypatch):
    monkeypatch.delenv("AGENTSMITH_DIR")
    _write(installed_repo, "agents/intake.py", "x = 1\n")
    result = _commit(installed_repo, "feat: intake")
    assert result.returncode != 0 and "could not run" in result.stderr

    launcher = installed_repo / ".githooks/process-gate"
    denied = subprocess.run(["bash", str(launcher), "pre-edit"], input="{}", capture_output=True, text=True,
                            check=False, cwd=installed_repo)
    # Exit 0 with the deny: Claude Code ignores a non-zero hook's output and
    # lets the edit through (and the settings fallback would print a second deny).
    assert denied.returncode == 0
    assert json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    advisory = subprocess.run(["bash", str(launcher), "stop"], input="{}", capture_output=True, text=True,
                              check=False, cwd=installed_repo)
    assert advisory.returncode == 0 and "did not run" in advisory.stderr


@needs_git
def test_the_launcher_prefers_the_repos_own_copy(gated_repo, tmp_path, monkeypatch):
    """A vendored tenant runs the gate it carries, not whatever $AGENTSMITH_DIR has."""
    decoy = tmp_path / "decoy"
    (decoy / "scripts").mkdir(parents=True)
    (decoy / "scripts/process_gate.py").write_text("import sys; print('decoy'); sys.exit(3)\n")
    monkeypatch.setenv("AGENTSMITH_DIR", str(decoy))
    # A Claude Code session in ANOTHER project committing here: its project dir
    # must not decide which gate runs.
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(decoy))
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    result = _commit(gated_repo, "feat: add tool")
    assert "missing 'Design:" in result.stderr and "decoy" not in result.stdout


def _fake_interpreter(tmp_path: Path) -> Path:
    """An interpreter that cannot run the gate: it drains stdin (as a real one
    would before failing) and exits 3, as process_gate.py does under Python 3.9."""
    fake = tmp_path / "old-python"
    fake.write_text("#!/usr/bin/env bash\ncat >/dev/null\necho 'too old' >&2\nexit 3\n")
    fake.chmod(0o755)
    return fake


@needs_git
def test_the_launcher_moves_past_an_interpreter_that_cannot_run_the_gate(gated_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTSMITH_PYTHON", str(_fake_interpreter(tmp_path)))
    framework_python = Path(os.environ["HOME"]) / ".agent-framework/.venv/bin/python"
    framework_python.parent.mkdir(parents=True)
    framework_python.symlink_to(sys.executable)
    launcher = gated_repo / ".githooks/process-gate"

    denied = subprocess.run(
        ["bash", str(launcher), "pre-edit"], input=json.dumps(_edit(gated_repo, "scripts/lib/a.py")),
        capture_output=True, text=True, check=False, cwd=gated_repo)
    assert _decision(denied) == "deny" and "no active design note covers it" in denied.stdout, \
        "the second interpreter must receive the same payload the first one drained"

    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    assert "missing 'Design:" in _commit(gated_repo, "feat: add tool").stderr


@needs_git
def test_the_launcher_fails_closed_when_no_interpreter_can_run_the_gate(gated_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTSMITH_PYTHON", str(_fake_interpreter(tmp_path)))
    launcher = gated_repo / ".githooks/process-gate"

    denied = subprocess.run(["bash", str(launcher), "pre-edit"], input=json.dumps(_edit(gated_repo, "docs/x.md")),
                            capture_output=True, text=True, check=False, cwd=gated_repo)
    assert denied.returncode == 0 and _decision(denied) == "deny"
    assert "no interpreter could run" in denied.stdout and "install-ai-stack.sh" in denied.stdout

    _write(gated_repo, "notes.txt", "x\n")
    blocked = _commit(gated_repo, "docs: notes")
    assert blocked.returncode != 0 and "no interpreter could run" in blocked.stderr


def test_the_gate_under_an_old_interpreter_exits_3_and_names_the_fix(monkeypatch):
    monkeypatch.setattr(pg, "UNUSABLE", "Python 3.9.6 at /usr/bin/python3 is older than 3.11")
    assert pg.main(["stop"]) == pg.EXIT_UNUSABLE


@needs_git
def test_a_hook_run_spools_a_span_carrying_its_decision(gated_repo, tmp_path):
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    launcher = gated_repo / ".githooks/process-gate"
    subprocess.run(["bash", str(launcher), "pre-edit"], input=json.dumps(_edit(gated_repo, "scripts/lib/a.py")),
                   capture_output=True, text=True, check=True, cwd=gated_repo)

    spans = []
    for batch in (tmp_path / "state" / "gate-spans").glob("*.pb"):
        request = ExportTraceServiceRequest()
        request.ParseFromString(batch.read_bytes())
        spans += [s for rs in request.resource_spans for ss in rs.scope_spans for s in ss.spans]
    [span] = [s for s in spans if s.name == "agent.gate.pre_edit"]
    attrs = {a.key: a.value.string_value for a in span.attributes}
    assert attrs["agent.decision"] == "deny" and attrs["agent.role"] == "process-gate"
    assert _git(gated_repo, "status", "--porcelain").stdout == "", "the gate must leave the tree it checks untouched"


@needs_git
def test_the_approvals_record_cannot_be_edited_through_a_design(gated_repo):
    """An agent that could edit approvals.jsonl could approve its own deviation,
    so no design scope unlocks it — not even one that names it."""
    design = DESIGN.replace("  - scripts/tool.py", f"  - {pg.gm.APPROVALS_FILE}")
    _write(gated_repo, ".agent-rfc/designs/change.md", design)
    result = _hook(gated_repo, "pre-edit", _edit(gated_repo, pg.gm.APPROVALS_FILE))
    assert _decision(result) == "deny"
    assert "agentsmith approve" in result.stdout


@needs_git
def test_a_denied_edit_is_labelled_deny_in_its_span_whatever_the_json_looks_like(gated_repo, tmp_path, monkeypatch):
    """The span's decision comes from the decision, not from matching the text
    the hook printed — which a formatting change would silently relabel."""
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    monkeypatch.setenv("AGENTSMITH_IDE", "cursor")
    subprocess.run([sys.executable, str(gated_repo / "scripts/process_gate.py"), "pre-edit"],
                   input=json.dumps(_edit(gated_repo, "scripts/lib/a.py")), capture_output=True, text=True,
                   check=True, cwd=gated_repo, env=dict(os.environ, AGENTSMITH_IDE="cursor",
                                                        AGENTSMITH_STATE_DIR=str(tmp_path / "state")))
    spans = []
    for batch in (tmp_path / "state" / "gate-spans").glob("*.pb"):
        request = ExportTraceServiceRequest()
        request.ParseFromString(batch.read_bytes())
        spans += [s for rs in request.resource_spans for ss in rs.scope_spans for s in ss.spans]
    attrs = {a.key: a.value.string_value for s in spans for a in s.attributes}
    assert attrs["agent.decision"] == "deny"
    assert attrs["agent.ide"] == "cursor", "the span names the IDE that ran it, not a guess"


@needs_git
def test_session_start_says_which_active_designs_unlock_nothing(gated_repo):
    """A design listed by name reads as one that is in force. An incomplete one
    — an unanswered pillar, an unapproved deviation — unlocks nothing."""
    _write(gated_repo, ".agent-rfc/designs/change.md",
           DESIGN.replace("## Deviations\nnone", "## Deviations\n- D1 — P3 — no spans — approval: A-0123abcd"))
    context = json.loads(_hook(gated_repo, "session-start", {"cwd": str(gated_repo)}).stdout)
    text = context["hookSpecificOutput"]["additionalContext"]
    assert "INCOMPLETE, unlocks nothing" in text and "A-0123abcd" in text


@needs_git
def test_session_start_lists_the_pillars_and_a_repos_own_extra_lines(gated_repo):
    config = json.loads((gated_repo / pg.CONFIG).read_text(encoding="utf-8"))
    config["extends"] = {"session_start": ["Tenant rule: run `npm test` in apps/web too."]}
    _write(gated_repo, pg.CONFIG, json.dumps(config, indent=2))
    context = json.loads(_hook(gated_repo, "session-start", {"cwd": str(gated_repo)}).stdout)
    text = context["hookSpecificOutput"]["additionalContext"]
    assert "Tenant rule: run `npm test`" in text
    assert "Pillars a design must answer" in text and "P3 Tracing" in text


@needs_git
def test_session_start_says_when_gate_spans_are_not_emitted(gated_repo):
    shutil.rmtree(gated_repo / "runtime")
    _git(gated_repo, "commit", "-qam", "chore: drop runtime", "--no-verify")
    context = json.loads(_hook(gated_repo, "session-start", {"cwd": str(gated_repo)}).stdout)
    text = context["hookSpecificOutput"]["additionalContext"]
    assert "gate spans NOT emitted" in text


def _ci(repo: Path, base: str, head: str = "HEAD", summary: Path | None = None,
        script: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if summary:
        env["GITHUB_STEP_SUMMARY"] = str(summary)
    return subprocess.run(
        [sys.executable, str(script or repo / "scripts/process_gate.py"), "ci", "--base", base, "--head", head],
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
def test_ci_passes_a_compliant_range_and_requires_changelog_where_configured(gated_repo):
    base = _git(gated_repo, "rev-parse", "HEAD").stdout.strip()
    _write(gated_repo, "scripts/tool.py", "print(1)\n")      # a changelog path in AgentSmith's config
    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    assert _commit(gated_repo, MESSAGE).returncode == 0

    without = _ci(gated_repo, base)
    assert without.returncode == 1 and "CHANGELOG.md" in without.stdout

    _write(gated_repo, "CHANGELOG.md", "## [Unreleased]\n- tool\n")
    assert _commit(gated_repo, "docs: changelog").returncode == 0
    assert _ci(gated_repo, base).returncode == 0


@needs_git
def test_ci_has_no_changelog_rule_where_the_config_declares_none(installed_repo):
    base = _git(installed_repo, "rev-parse", "HEAD").stdout.strip()
    design = DESIGN.replace("scripts/lib/**", "agents/**")
    _write(installed_repo, "agents/intake.py", "x = 1\n")
    _write(installed_repo, ".agent-rfc/designs/change.md", design)
    _write(installed_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    assert _commit(installed_repo, MESSAGE).returncode == 0

    result = _ci(installed_repo, base, script=GATE)     # CI runs the framework checkout's copy

    assert result.returncode == 0, result.stdout


@needs_git
def test_ci_fails_when_the_config_was_removed(gated_repo):
    base = _git(gated_repo, "rev-parse", "HEAD").stdout.strip()
    _git(gated_repo, "rm", "-q", pg.CONFIG)
    _git(gated_repo, "commit", "-qm", "chore: drop the gates", "--no-verify")

    result = _ci(gated_repo, base)

    assert result.returncode == 1 and "gates were removed" in result.stdout


@needs_git
def test_ci_lists_commits_from_before_adoption_instead_of_failing_them(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path, "adopting", {**GATE_FILES, "src.py": "x = 1\n"}, monkeypatch)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _write(repo, "scripts/other.py", "y = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat: before adoption", "--no-verify")
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "docs/review-levers.md", repo / "docs/review-levers.md")
    (repo / pg.CONFIG).parent.mkdir(parents=True, exist_ok=True)
    (repo / pg.CONFIG).write_text(json.dumps(FIXTURE_CONFIG, indent=2) + "\n", encoding="utf-8")
    _write(repo, ".agent-rfc/designs/change.md", DESIGN.replace("scripts/tool.py", pg.CONFIG))
    _write(repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(repo, "CHANGELOG.md", "adopted\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", MESSAGE.replace("feat: x", "chore: adopt the gates"), "--no-verify")

    result = _ci(repo, base)

    assert result.returncode == 0, result.stdout
    assert "feat: before adoption — before this repo adopted the gates; not checked" in result.stdout


@needs_git
def test_ci_lists_every_na_escape_in_its_summary(gated_repo, tmp_path):
    base = _git(gated_repo, "rev-parse", "HEAD").stdout.strip()
    _write(gated_repo, "pytest.ini", "[pytest]\n")        # gated, no changelog needed
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


def _hook(repo: Path, command: str, payload, script: Path | None = None) -> subprocess.CompletedProcess:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(script or repo / "scripts/process_gate.py"), command],
        input=raw, capture_output=True, text=True, check=False, cwd=repo,
    )


def _decision(result: subprocess.CompletedProcess):
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] if result.stdout.strip() else "allow"


def _edit(repo: Path, rel: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(repo / rel)}, "cwd": str(repo)}


@needs_git
def test_pre_edit_denies_an_uncovered_gated_path_and_allows_a_covered_one(gated_repo):
    assert _decision(_hook(gated_repo, "pre-edit", _edit(gated_repo, "scripts/lib/a.py"))) == "deny"
    assert _decision(_hook(gated_repo, "pre-edit", _edit(gated_repo, "docs/notes.md"))) == "allow"

    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    assert _decision(_hook(gated_repo, "pre-edit", _edit(gated_repo, "scripts/lib/a.py"))) == "allow"
    assert _decision(_hook(gated_repo, "pre-edit", _edit(gated_repo, "runtime/b.py"))) == "deny", "outside the scope"

    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN.replace("status: active", "status: done"))
    finished = _hook(gated_repo, "pre-edit", _edit(gated_repo, "scripts/lib/a.py"))
    assert _decision(finished) == "deny", "a finished design unlocks nothing"


@needs_git
def test_pre_edit_does_not_accept_a_stub_design(gated_repo):
    _write(gated_repo, ".agent-rfc/designs/stub.md", "---\nstatus: active\nscope:\n  - scripts/lib/**\n---\n# todo\n")
    result = _hook(gated_repo, "pre-edit", _edit(gated_repo, "scripts/lib/a.py"))
    assert _decision(result) == "deny"
    assert "not complete" in result.stdout


@needs_git
def test_pre_edit_fails_closed_on_input_it_cannot_read(gated_repo):
    assert _decision(_hook(gated_repo, "pre-edit", "{not json")) == "deny"


@needs_git
def test_pre_edit_allows_everything_where_the_gates_are_not_adopted(gated_repo):
    (gated_repo / pg.CONFIG).unlink()
    assert _decision(_hook(gated_repo, "pre-edit", _edit(gated_repo, "scripts/lib/a.py"))) == "allow"


@needs_git
def test_pre_edit_with_a_broken_config_allows_only_fixing_it(gated_repo):
    _write(gated_repo, pg.CONFIG, "{broken")
    assert _decision(_hook(gated_repo, "pre-edit", _edit(gated_repo, "docs/notes.md"))) == "deny"
    assert _decision(_hook(gated_repo, "pre-edit", _edit(gated_repo, pg.CONFIG))) == "allow"


@needs_git
def test_pre_edit_in_an_installed_mode_repo_reads_framework_levers(installed_repo):
    _write(installed_repo, ".agent-rfc/designs/change.md", DESIGN.replace("scripts/lib/**", "agents/**"))
    allowed = _hook(installed_repo, "pre-edit", _edit(installed_repo, "agents/intake.py"), script=GATE)
    assert _decision(allowed) == "allow", allowed.stdout
    denied = _hook(installed_repo, "pre-edit", _edit(installed_repo, "worker.py"), script=GATE)
    assert "design-review-checklist.md in your AgentSmith checkout" in denied.stdout


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
def test_session_start_states_the_rules_and_rearms_an_unarmed_commit_gate(gated_repo):
    """An unarmed clone used to be told to arm itself, which only works if
    somebody reads it. Since the sweep (G3) the session start re-arms it and
    reports that it did — the fix, not the reminder."""
    _git(gated_repo, "config", "--unset", "core.hooksPath")
    context = json.loads(_hook(gated_repo, "session-start", {"cwd": str(gated_repo)}).stdout)
    text = context["hookSpecificOutput"]["additionalContext"]
    assert "design-review-checklist.md" in text and "review-levers.md" in text
    assert _git(gated_repo, "config", "core.hooksPath").stdout.strip() == ".githooks"


@needs_git
def test_session_start_warns_when_the_gate_cannot_be_armed(gated_repo):
    """No launcher to point core.hooksPath at: re-arming would name a directory
    with no hooks in it, which is worse than saying so."""
    _git(gated_repo, "config", "--unset", "core.hooksPath")
    (gated_repo / ".githooks" / "process-gate").unlink()
    context = json.loads(_hook(gated_repo, "session-start", {"cwd": str(gated_repo)}).stdout)

    assert "not armed" in context["hookSpecificOutput"]["additionalContext"]


@needs_git
def test_session_start_is_silent_where_the_gates_are_not_adopted(gated_repo):
    (gated_repo / pg.CONFIG).unlink()
    assert _hook(gated_repo, "session-start", {"cwd": str(gated_repo)}).stdout.strip() == ""


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

SUBCOMMANDS = {"session-start", "pre-edit", "stop", "commit-msg", "ci"}


def test_claude_settings_wire_all_three_agent_hooks_through_the_launcher():
    hooks = json.loads((REPO / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    commands = {event: [h["command"] for m in entries for h in m["hooks"]] for event, entries in hooks.items()}
    launcher = 'bash "$CLAUDE_PROJECT_DIR/.githooks/process-gate"'
    # Every command names its dialect since G2a: one gate, six of them.
    assert f"{launcher} session-start --ide claude" in commands["SessionStart"]
    assert f"{launcher} stop --ide claude" in commands["Stop"]
    pre = [m for m in hooks["PreToolUse"] if any(f"{launcher} pre-edit --ide claude" in h["command"]
                                                 for h in m["hooks"])]
    matchers = {matcher for entry in pre for matcher in entry["matcher"].split("|")}
    assert {"Edit", "Write", "MultiEdit", "NotebookEdit"} <= matchers
    shell = [entry for entry in hooks["PreToolUse"] if entry["matcher"] == "Bash"]
    assert shell, "the shell surface (G2b) is wired here too"
    for event_commands in commands.values():
        for command in event_commands:
            assert command.split(launcher + " ", 1)[1].split()[0] in SUBCOMMANDS


@needs_git
def test_the_edit_gate_fails_closed_when_the_gate_cannot_run(tmp_path):
    """Claude Code lets an edit through when a PreToolUse hook exits non-zero —
    so a missing launcher, or one that dies before answering, must still deny."""
    hooks = json.loads((REPO / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    edit = next(entry for entry in hooks["PreToolUse"] if "Edit" in entry["matcher"])
    command = edit["hooks"][0]["command"]
    result = subprocess.run(
        ["bash", "-c", command], input="{}", capture_output=True, text=True, check=False,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path)),     # no .githooks/process-gate here
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_self_test_runs_the_ci_gate_over_the_pushed_range():
    workflow = yaml.safe_load((REPO / ".github/workflows/self-test.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["process-gates"]
    checkout = job["steps"][0]
    assert checkout["with"]["fetch-depth"] == 0, "a shallow clone has no range to check"
    step = next(s for s in job["steps"] if "process_gate.py ci" in s.get("run", ""))
    assert "github.event.before" in step["env"]["BASE"] and "pull_request.base.sha" in step["env"]["BASE"]
    # Without the framework environment the gate exits 3 and checks nothing.
    assert any("requirements-gate.txt" in s.get("run", "") for s in job["steps"]), \
        "CI must install what the gate imports, or it cannot run at all"


def test_the_gate_requirements_list_covers_what_the_gate_imports():
    listed = (REPO / "scripts/requirements-gate.txt").read_text(encoding="utf-8")
    for package in ("pydantic", "opentelemetry-sdk", "opentelemetry-exporter-otlp-proto-http"):
        assert package in listed


def test_the_commit_hook_calls_the_gate_through_the_launcher():
    text = (REPO / ".githooks/commit-msg").read_text(encoding="utf-8")
    assert '"$hook_dir/process-gate" commit-msg "${amend[@]+"${amend[@]}"}" "$msg_file"' in text
    for hook in (".githooks/commit-msg", ".githooks/process-gate"):
        assert os.access(REPO / hook, os.X_OK), hook


# ── Adoption of the registry's design-time rules ─────────────────────────────


PRE_REGISTRY_DESIGN = """---
status: active
scope:
  - scripts/**
---
# A design written before the registry existed

## Problem
Something was wrong.

## Approach
Fix it.

## Levers
- `declared-vs-enforced` — the gate reads it.
"""

PRE_REGISTRY_REVIEW = """# Review — before the registry

## Pass 1 — findings: 0
Everything checked.
"""


def _checked(config_data: dict, design: str, review: str) -> list:
    """The errors `ci` would report for one commit carrying this config."""
    config = pg.Config(config_data)
    files = {
        ".agent-rfc/designs/change.md": design,
        ".agent-rfc/reviews/change.md": review,
        "docs/review-levers.md": (REPO / "docs/review-levers.md").read_text(encoding="utf-8"),
        "templates/governance.json": (REPO / "templates/governance.json").read_text(encoding="utf-8"),
    }
    errors, _notes = pg.check_change(
        ["scripts/tool.py", ".agent-rfc/reviews/change.md"], 10,
        "feat: x\n\nDesign: .agent-rfc/designs/change.md\nReview: .agent-rfc/reviews/change.md\n",
        lambda path: files.get(path), config,
    )
    return errors


BASE_CONFIG = {
    "gated": ["scripts/**"],
    "not_gated": ["**.md", ".agent-rfc/**"],
    "levers_doc": "docs/review-levers.md",
}


def test_a_commit_made_before_the_registry_is_judged_by_the_rules_it_was_made_under():
    """G1 added `## Pillars`, `## Deviations`, `## Dependencies` and the sign-off
    block. Applying them to commits made before they existed would fail history
    that no design written then could have satisfied — and `ci` walks a range of
    commits. A config that does not declare `registry` has not adopted them."""
    assert _checked(BASE_CONFIG, PRE_REGISTRY_DESIGN, PRE_REGISTRY_REVIEW) == []


def test_a_commit_that_declares_the_registry_must_answer_it():
    errors = _checked(
        {**BASE_CONFIG, "registry": "templates/governance.json"},
        PRE_REGISTRY_DESIGN, PRE_REGISTRY_REVIEW,
    )
    assert any("Pillars" in e for e in errors), errors
    assert any("Deviations" in e for e in errors), errors
    assert any("Dependencies" in e for e in errors), errors
    assert any("Sign-off" in e for e in errors), errors


def test_this_repo_has_adopted_the_registry():
    """AgentSmith declares it, so every commit from G1 on is held to it — the
    grandfathering above is for history, not an opt-out."""
    assert "registry" in json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
