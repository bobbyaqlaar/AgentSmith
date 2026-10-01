"""
scripts/test/test_gate_kg.py — G4: reviews that use the graph.

The knowledge graph existed and nothing made a review use it. `impact` turns a
diff into the files a reviewer has to read — the changed ones plus one hop of
dependents — and a hash of that set. The sign-off carries the hash, so "I
reviewed this" says which scope was reviewed rather than only that someone
typed the words.

The hash covers the file SET, not the diff's bytes: a content hash would go
stale on the next keystroke and turn the line into something people paste
without reading. Freshness of the review against the change is a rule that
already exists — the record changes in the same commit.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from test_process_gate import DESIGN, MESSAGE, REPO, REVIEW_CLEAN, _commit, _git, _write, needs_git

sys.path.insert(0, str(REPO / "scripts"))
import local_knowledge_graph as kg

GRAPH = {
    "directed": True,
    "nodes": [
        {"id": "scripts/tool.py", "node_type": "CodebaseFile", "symbols": ["run"]},
        {"id": "scripts/caller.py", "node_type": "CodebaseFile", "symbols": ["main"]},
        {"id": "scripts/stranger.py", "node_type": "CodebaseFile", "symbols": ["x"]},
        {"id": "portal/app/api/runs/route.ts", "node_type": "CodebaseFile", "symbols": ["GET"]},
    ],
    "links": [
        {"source": "scripts/caller.py", "target": "scripts/tool.py", "edge_type": "IMPORTS"},
    ],
}


# ── what a change touches ────────────────────────────────────────────────────


def test_impact_is_the_change_plus_one_hop_of_dependents() -> None:
    found = kg.impact(GRAPH, ["scripts/tool.py"])

    assert found.files == ["scripts/caller.py", "scripts/tool.py"]
    assert "scripts/stranger.py" not in found.files


def test_a_file_the_graph_does_not_know_is_still_in_the_scope() -> None:
    """A new file has no node yet, and dropping it would shrink a review to the
    part the graph happened to know about."""
    found = kg.impact(GRAPH, ["scripts/brand_new.py"])

    assert "scripts/brand_new.py" in found.files
    assert found.unknown == ["scripts/brand_new.py"]


def test_the_lever_groups_come_from_what_was_touched() -> None:
    """A route is a screen and a session; a gate script is safety and signal."""
    assert 7 in kg.impact(GRAPH, ["portal/app/api/runs/route.ts"]).groups
    assert 6 in kg.impact(GRAPH, ["scripts/process_gate.py"]).groups


def test_the_hash_is_the_scope_not_the_bytes() -> None:
    one = kg.impact(GRAPH, ["scripts/tool.py"]).query
    again = kg.impact(GRAPH, ["scripts/tool.py"]).query
    wider = kg.impact(GRAPH, ["scripts/tool.py", "scripts/stranger.py"]).query

    assert one == again, "the same scope is the same hash"
    assert one != wider, "a wider scope is a different hash"


def test_the_order_files_arrive_in_does_not_change_the_hash() -> None:
    assert kg.impact(GRAPH, ["a.py", "b.py"]).query == kg.impact(GRAPH, ["b.py", "a.py"]).query


def test_the_hash_is_the_same_in_a_second_process() -> None:
    """The scope is built in a set, and set iteration order varies with the
    interpreter's hash seed. Sorting is what makes the line a person writes in
    a review still match when a git hook recomputes it in a fresh process."""
    import os

    program = (
        "import json, sys; sys.path.insert(0, %r);"
        "import gate_kg; print(gate_kg.impact(json.loads(sys.argv[1]), "
        "['scripts/tool.py', 'portal/app/api/runs/route.ts', 'runtime/x.py']).query)"
        % str(REPO / "scripts")
    )
    seeds = []
    for seed in ("0", "12345"):
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        seeds.append(subprocess.run([sys.executable, "-c", program, json.dumps(GRAPH)],
                                    capture_output=True, text=True, env=environment,
                                    check=False).stdout.strip())

    assert seeds[0] == seeds[1] != ""


def test_the_hash_is_short_enough_to_type() -> None:
    query = kg.impact(GRAPH, ["scripts/tool.py"]).query
    assert query.startswith("kg:") and len(query) <= 20


# ── the command ──────────────────────────────────────────────────────────────


@needs_git
def test_the_command_reports_the_scope_of_a_diff(gated_repo) -> None:
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "chore: a file", "--no-verify")

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts" / "local_knowledge_graph.py"),
         "--impact", "--base", "HEAD~1"],
        cwd=gated_repo, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "scripts/tool.py" in result.stdout
    assert "kg:" in result.stdout


# ── the sign-off carries it ──────────────────────────────────────────────────


def _kg_mode(repo, mode, commit=True) -> None:
    path = repo / ".agenticframework" / "process-gates.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    if mode is None:
        config.pop("knowledge_graph", None)
    else:
        config["knowledge_graph"] = mode
    path.write_text(json.dumps(config, indent=2) + "\n")
    if commit:
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "chore: kg mode", "--no-verify")


def _expected(repo, files) -> str:
    graph = json.loads((repo / ".agent-rfc" / "fixtures" / "knowledge_graph.json").read_text(encoding="utf-8"))
    return kg.impact(graph, files).query


@pytest.fixture()
def kg_repo(gated_repo):
    _write(gated_repo, ".agent-rfc/fixtures/knowledge_graph.json", json.dumps(GRAPH))
    _kg_mode(gated_repo, "enforce")
    return gated_repo


@needs_git
def test_a_review_without_the_line_is_refused(kg_repo) -> None:
    _write(kg_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(kg_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(kg_repo, "scripts/tool.py", "print(1)\n")

    result = _commit(kg_repo, MESSAGE)

    assert result.returncode != 0
    assert "KG query" in result.stderr


@needs_git
def test_the_line_must_name_the_scope_that_was_reviewed(kg_repo) -> None:
    _write(kg_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(kg_repo, ".agent-rfc/reviews/change.md",
           REVIEW_CLEAN.replace("Gates run locally:", "KG query:                 kg:0000deadbeef\nGates run locally:"))
    _write(kg_repo, "scripts/tool.py", "print(1)\n")

    result = _commit(kg_repo, MESSAGE)

    assert result.returncode != 0
    assert "kg:0000deadbeef" in result.stderr


@needs_git
def test_the_matching_hash_passes(kg_repo) -> None:
    _write(kg_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(kg_repo, "scripts/tool.py", "print(1)\n")
    query = _expected(kg_repo, ["scripts/tool.py", ".agent-rfc/designs/change.md",
                                ".agent-rfc/reviews/change.md"])
    _write(kg_repo, ".agent-rfc/reviews/change.md",
           REVIEW_CLEAN.replace("Gates run locally:", f"KG query:                 {query}\nGates run locally:"))

    result = _commit(kg_repo, MESSAGE)

    assert result.returncode == 0, result.stderr


@needs_git
def test_off_asks_for_no_line(gated_repo) -> None:
    _kg_mode(gated_repo, None)
    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(gated_repo, "scripts/tool.py", "print(1)\n")

    assert _commit(gated_repo, MESSAGE).returncode == 0


@needs_git
def test_report_says_what_is_missing_without_refusing(kg_repo) -> None:
    _kg_mode(kg_repo, "report")
    _write(kg_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(kg_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(kg_repo, "scripts/tool.py", "print(1)\n")

    result = _commit(kg_repo, MESSAGE)

    assert result.returncode == 0, result.stderr
    assert "KG query" in result.stdout + result.stderr


@needs_git
def test_a_repo_whose_graph_is_missing_says_so_rather_than_passing(kg_repo) -> None:
    """"No graph" and "the scope matches" are different answers."""
    (kg_repo / ".agent-rfc" / "fixtures" / "knowledge_graph.json").unlink()
    _git(kg_repo, "add", "-A")
    _git(kg_repo, "commit", "-qm", "chore: drop the graph", "--no-verify")
    _write(kg_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(kg_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(kg_repo, "scripts/tool.py", "print(1)\n")

    result = _commit(kg_repo, MESSAGE)

    assert result.returncode != 0
    assert "knowledge_graph.json" in result.stderr


@needs_git
def test_a_renaming_commit_has_one_scope_in_the_commit_gate_and_in_ci(kg_repo) -> None:
    """`git diff` detects the rename and names the new path; `git diff-tree`
    names the old one too. Both gates must compute the same hash for the same
    commit, or a change the commit gate accepts is one CI refuses."""
    _write(kg_repo, "scripts/old_name.py", "print(1)\n")
    _git(kg_repo, "add", "-A")
    _git(kg_repo, "commit", "-qm", "chore: a file to rename", "--no-verify")
    base = _git(kg_repo, "rev-parse", "HEAD").stdout.strip()
    _git(kg_repo, "mv", "scripts/old_name.py", "scripts/tool.py")
    # A rename deletes a gated path, so the design covers where it came from too.
    _write(kg_repo, ".agent-rfc/designs/change.md",
           DESIGN.replace("  - scripts/tool.py\n", "  - scripts/tool.py\n  - scripts/old_name.py\n"))
    _write(kg_repo, "CHANGELOG.md", "- renamed a script\n")  # the fixture's CHANGELOG rule, not this test's
    query = _expected(kg_repo, ["scripts/tool.py", ".agent-rfc/designs/change.md",
                                ".agent-rfc/reviews/change.md", "CHANGELOG.md"])
    _write(kg_repo, ".agent-rfc/reviews/change.md",
           REVIEW_CLEAN.replace("Gates run locally:", f"KG query:                 {query}\nGates run locally:"))

    committed = _commit(kg_repo, MESSAGE)
    ci = subprocess.run([sys.executable, str(kg_repo / "scripts" / "process_gate.py"), "ci",
                         "--base", base, "--head", "HEAD"],
                        cwd=kg_repo, capture_output=True, text=True, check=False)

    assert committed.returncode == 0, committed.stderr
    assert ci.returncode == 0, ci.stdout


@needs_git
def test_a_commit_carrying_a_binary_file_is_judged_by_both_gates_not_crashed_on(kg_repo) -> None:
    """The scope check reads every changed file to see that it still exists, and
    both readers decoded it as UTF-8 — so a gated commit that also carried an image,
    a font or a PDF crashed the commit gate and CI with UnicodeDecodeError instead
    of being judged. Found committing the portal's logos; the gate is vendored into
    every tenant (.agent-rfc/designs/gate-reads-binary-files.md)."""
    base = _git(kg_repo, "rev-parse", "HEAD").stdout.strip()
    _write(kg_repo, "scripts/tool.py", "print(1)\n")
    (kg_repo / "assets").mkdir()
    (kg_repo / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)))
    _write(kg_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(kg_repo, "CHANGELOG.md", "- a tool and its logo\n")  # the fixture's CHANGELOG rule, not this test's
    query = _expected(kg_repo, ["scripts/tool.py", "assets/logo.png", ".agent-rfc/designs/change.md",
                                ".agent-rfc/reviews/change.md", "CHANGELOG.md"])
    _write(kg_repo, ".agent-rfc/reviews/change.md",
           REVIEW_CLEAN.replace("Gates run locally:", f"KG query:                 {query}\nGates run locally:"))

    committed = _commit(kg_repo, MESSAGE)
    ci = subprocess.run([sys.executable, str(kg_repo / "scripts" / "process_gate.py"), "ci",
                         "--base", base, "--head", "HEAD"],
                        cwd=kg_repo, capture_output=True, text=True, check=False)

    assert "Traceback" not in committed.stderr, committed.stderr[-1500:]
    assert committed.returncode == 0, committed.stderr[-1500:]
    assert "Traceback" not in ci.stdout + ci.stderr, (ci.stdout + ci.stderr)[-1500:]
    assert ci.returncode == 0, ci.stdout[-1500:]


@needs_git
def test_renaming_a_gated_file_away_needs_a_design_at_commit_time_too(kg_repo) -> None:
    """Before this, the commit gate never saw a rename's old path, so moving a
    gated file out from under its design passed locally and failed in CI."""
    _kg_mode(kg_repo, "off")
    _write(kg_repo, "scripts/old_name.py", "print(1)\n")
    _git(kg_repo, "add", "-A")
    _git(kg_repo, "commit", "-qm", "chore: a file to rename", "--no-verify")
    _git(kg_repo, "mv", "scripts/old_name.py", "scripts/tool.py")
    _write(kg_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(kg_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)

    result = _commit(kg_repo, MESSAGE)

    assert result.returncode != 0
    assert "scripts/old_name.py" in result.stderr


# ── the framework holds itself to it ─────────────────────────────────────────


def test_agentsmith_declares_the_mode_it_ships() -> None:
    config = json.loads((REPO / ".agenticframework" / "process-gates.json").read_text(encoding="utf-8"))
    assert config.get("knowledge_graph") == "enforce"


def test_the_tenant_template_runs_the_same_freshness_check() -> None:
    """The inline version counted nodes in the committed file and never
    compared them — it could not see a stale graph at all."""
    template = (REPO / "workflow-templates" / "ci-python-fastapi.yml").read_text(encoding="utf-8")
    assert "verify_system.py --check-kg" in template
    kg_step = template.split("Validate Knowledge Graph")[1].split("- name:")[0]
    assert "continue-on-error" not in kg_step, "the graph blocks from G4"
