"""The traceability graph's builder (.agent-rfc/designs/pass3-root-causes.md)."""

from __future__ import annotations

import json
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


def test_a_commits_design_trailer_is_an_observed_link_and_requirement_links_are_inferred():
    document = _built(history=True)
    kinds = {(e["type"], e["kind"]) for e in document["edges"]}
    assert ("implements", "observed") in kinds and ("changes", "observed") in kinds
    assert all(e["kind"] == "inferred" for e in document["edges"] if e["type"] == "designed_by")
    assert document["built_from"]


COMMIT_KEYS = {"id", "type", "change", "in_range", "files", "fix"}


def test_a_commit_node_holds_identifiers_and_no_text_from_history():
    """Even on request, a commit is identifiers: the history output is shared and scanned like the rest."""
    commits = [n for n in _built(history=True)["nodes"] if n["type"] == "commit"]
    assert commits
    for node in commits:
        assert set(node) <= COMMIT_KEYS, f"{node['id']} carries {set(node) - COMMIT_KEYS}"


def test_a_range_the_checkout_cannot_resolve_is_recorded_not_fatal():
    """A tagless or shallow CI clone has no `v4.0.1`: the graph builds, with no range, and says so."""
    document = trace_graph.Builder(REPO).build("no-such-tag-anywhere", history=True)
    assert document["since"] is None and document["since_asked"] == "no-such-tag-anywhere"
    assert not any(n.get("in_range") for n in document["nodes"] if n["type"] == "commit")
