"""The traceability graph's builder (.agent-rfc/designs/pass3-root-causes.md)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import trace_graph


def _built() -> dict:
    return trace_graph.Builder(REPO).build("v4.0.1")


def test_every_link_says_how_it_is_known():
    document = _built()
    assert {e["kind"] for e in document["edges"]} <= set(trace_graph.KINDS)
    assert {"requirement", "design", "review", "commit", "file", "test"} <= set(document["summary"]["counts"])


def test_imports_come_from_the_knowledge_graph_not_a_second_resolver():
    """One resolver: the knowledge graph's. The reviewer's builder resolved imports itself."""
    graph = json.loads((REPO / ".agent-rfc/fixtures/knowledge_graph.json").read_text())
    builder = trace_graph.Builder(REPO)
    expected = {(e["source"], e["target"]) for e in graph["edges"]
                if e["source"] in builder.tset and e["target"] in builder.tset and e["source"] != e["target"]}
    document = builder.build("v4.0.1")
    assert {(e["from"], e["to"]) for e in document["edges"] if e["type"] == "imports"} == expected


def test_a_commits_design_trailer_is_an_observed_link_and_requirement_links_are_inferred():
    document = _built()
    kinds = {(e["type"], e["kind"]) for e in document["edges"]}
    assert ("implements", "observed") in kinds and ("changes", "observed") in kinds
    assert all(e["kind"] == "inferred" for e in document["edges"] if e["type"] == "designed_by")
    assert document["built_from"]
