"""The traceability graph's builder (.agent-rfc/designs/pass3-root-causes.md)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import trace_graph


def _built(history: bool = False) -> dict:
    return trace_graph.Builder(REPO).build("v4.0.1" if history else "", history=history)


def test_every_link_says_how_it_is_known():
    document = _built()
    assert {e["kind"] for e in document["edges"]} <= set(trace_graph.KINDS)
    assert {"requirement", "design", "review", "file", "test"} <= set(document["summary"]["counts"])


def test_imports_come_from_the_knowledge_graph_not_a_second_resolver():
    """One resolver: the knowledge graph's. The reviewer's builder resolved imports itself."""
    graph = json.loads((REPO / ".agent-rfc/fixtures/knowledge_graph.json").read_text())
    builder = trace_graph.Builder(REPO)
    expected = {(e["source"], e["target"]) for e in graph["edges"]
                if e["source"] in builder.tset and e["target"] in builder.tset and e["source"] != e["target"]}
    document = builder.build()
    assert {(e["from"], e["to"]) for e in document["edges"] if e["type"] == "imports"} == expected


def test_the_committed_graph_is_what_the_tree_builds():
    """A committed fixture nobody checks goes stale. It is a function of the tree, so CI rebuilds and compares."""
    assert trace_graph.main(["--check"]) == 0, "run `agentsmith gate kg build` and commit the trace graph"


def test_the_committed_graph_holds_no_git_history():
    """History is not the tree: a committed file cannot hold the commit that carries it, history only grows, and
    every scan of tracked files would read its text (a commit subject brought in a private name and an env var)."""
    committed = json.loads((REPO / trace_graph.OUT).read_text())
    assert committed["history"] is False
    assert not [n for n in committed["nodes"] if n["type"] == "commit"]
    assert not [e for e in committed["edges"] if e["type"] in ("implements", "reviewed_by", "changes", "built")]
    assert "built_from" not in committed and committed["summary"]["files_no_design"] is None


def test_history_never_writes_or_checks_the_committed_graph():
    for argv in (["--history", "--out", trace_graph.OUT], ["--history", "--check"]):
        with pytest.raises(SystemExit):
            trace_graph.main(argv)


# The history tests build a repository of their own. This repository's history depends on how it was cloned: CI
# checks out the pull request's merge commit at depth 1, with no tags and no trailers (P4-R10, then this).
INPUTS = ("docs/PRODUCT_BACKLOG.md", "fixtures/compliance/catalogue.json", "scripts/compliance_checks.py",
          ".agent-rfc/fixtures/knowledge_graph.json")


@pytest.fixture()
def history_repo(tmp_path: Path) -> Path:
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")
    for rel in INPUTS:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, tmp_path / rel)
    design = tmp_path / ".agent-rfc/designs/d.md"
    design.parent.mkdir(parents=True)
    design.write_text("---\nstatus: active\nscope:\n  - app/a.py\n---\n# d\n")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "chore: inputs")
    git("tag", "v1")
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "fix(a): a private-looking subject\n\nDesign: .agent-rfc/designs/d.md")
    return tmp_path


def test_a_commits_design_trailer_is_an_observed_link_and_requirement_links_are_inferred(history_repo):
    document = trace_graph.Builder(history_repo).build("v1", history=True)
    kinds = {(e["type"], e["kind"]) for e in document["edges"]}
    assert ("implements", "observed") in kinds and ("changes", "observed") in kinds
    assert ("built", "derived") in kinds
    assert all(e["kind"] == "inferred" for e in document["edges"] if e["type"] == "designed_by")
    assert document["built_from"] and document["since"] == "v1"
    assert [f for f, _ in document["summary"]["hot_fixes_since"]] == ["app/a.py"]


COMMIT_KEYS = {"id", "type", "change", "in_range", "files", "fix"}


def test_a_commit_node_holds_identifiers_and_no_text_from_history(history_repo):
    """Even on request, a commit is identifiers: the history output is shared and scanned like the rest."""
    commits = [n for n in trace_graph.Builder(history_repo).build("v1", history=True)["nodes"]
               if n["type"] == "commit"]
    assert len(commits) == 2
    for node in commits:
        assert set(node) <= COMMIT_KEYS, f"{node['id']} carries {set(node) - COMMIT_KEYS}"
    assert "private-looking" not in json.dumps(commits)


def test_a_range_the_checkout_cannot_resolve_is_recorded_not_fatal(history_repo):
    """A tagless or shallow CI clone has no release tag: the graph builds, with no range, and says so."""
    document = trace_graph.Builder(history_repo).build("no-such-tag-anywhere", history=True)
    assert document["since"] is None and document["since_asked"] == "no-such-tag-anywhere"
    assert not any(n.get("in_range") for n in document["nodes"] if n["type"] == "commit")
