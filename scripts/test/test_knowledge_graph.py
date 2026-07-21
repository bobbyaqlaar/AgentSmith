"""
scripts/test/test_knowledge_graph.py — Knowledge Graph API + map_codebase
walker (TestCoverageReview-2026-07-21 gap 3).

Covers: upsert/persist/reload round-trip, import edges, incident injection,
subgraph context window, symbol/impact queries, stale-node purge, and the
incremental mtime skip added in ReviewFindings C2 (previously verified only
by hand in a scratch repo — now pinned here).

Runs entirely in a tmp repo root; requires networkx (in requirements.txt —
same dependency verify_system.py --check-kg already assumes in CI).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/

nx = pytest.importorskip("networkx")

from local_knowledge_graph import AgentKnowledgeGraph  # noqa: E402
import map_codebase  # noqa: E402


@pytest.fixture()
def repo(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ── AgentKnowledgeGraph API ──────────────────────────────────────────────────


def test_upsert_persist_reload_roundtrip(repo):
    kg = AgentKnowledgeGraph()
    kg.upsert_file("src/a.py", language="python", symbols=["main"])
    kg.upsert_guardrail("rfc:001", "No code without spec", "rfc/001.md", 1)
    kg.add_import("src/b.py", "src/a.py")

    kg2 = AgentKnowledgeGraph()  # fresh instance reloads from disk
    assert kg2._g.has_node("src/a.py")
    assert kg2._g.nodes["src/a.py"]["symbols"] == ["main"]
    assert kg2._g.has_edge("src/b.py", "src/a.py")
    counts = kg2.stats()
    assert counts["CodebaseFile"] == 2 and counts["Guardrail"] == 1


def test_inject_production_learning_links_file(repo):
    kg = AgentKnowledgeGraph()
    kg.upsert_file("src/a.py", language="python")
    kg.inject_production_learning(
        "incident:42",
        event="tool_selection_error",
        agent="developer",
        file_hint="src/a.py",
        resolution_summary="use search_flights for date queries",
        resolved_by="bobby",
    )
    assert kg._g.has_edge("src/a.py", "incident:42")
    window = kg.fetch_subgraph_context_window("src/a.py", hops=1)
    assert [i["id"] for i in window["incidents"]] == ["incident:42"]


def test_subgraph_context_window_hops_and_missing_anchor(repo):
    kg = AgentKnowledgeGraph()
    kg.add_import("a.py", "b.py")
    kg.add_import("b.py", "c.py")
    kg.add_import("c.py", "d.py")
    window = kg.fetch_subgraph_context_window("a.py", hops=2)
    ids = {n["id"] for n in window["nodes"]}
    assert ids == {"a.py", "b.py", "c.py"}  # d.py is 3 hops out
    empty = kg.fetch_subgraph_context_window("nope.py")
    assert empty["nodes"] == [] and empty["anchor"] == "nope.py"


def test_symbol_and_impact_queries(repo):
    kg = AgentKnowledgeGraph()
    kg.upsert_file("src/a.py", language="python", symbols=["route", "call"])
    kg.upsert_file("src/b.py", language="python", symbols=["other"])
    kg.add_import("src/b.py", "src/a.py")
    assert kg.find_files_by_symbol("route") == ["src/a.py"]
    assert kg.impacted_files("src/a.py") == ["src/b.py"]


def test_remove_file(repo):
    kg = AgentKnowledgeGraph()
    kg.upsert_file("gone.py")
    kg.remove_file("gone.py")
    assert not kg._g.has_node("gone.py")
    kg.remove_file("never-existed.py")  # no-op, must not raise


# ── map_codebase walker ──────────────────────────────────────────────────────


def _write_sample(repo: Path) -> None:
    (repo / "app.py").write_text("import helper\n\ndef main():\n    return 1\n")
    (repo / "helper.py").write_text("def util():\n    return 2\n")


def test_walker_upserts_symbols_and_edges(repo):
    _write_sample(repo)
    stats = map_codebase.run_map()
    assert stats["upserted"] == 2 and stats["unchanged"] == 0
    kg = AgentKnowledgeGraph()
    assert kg.find_files_by_symbol("main") == ["app.py"]
    assert kg._g.has_edge("app.py", "helper.py")  # resolved local import


def test_walker_incremental_skip_and_purge(repo):
    """Pin the C2 behavior: unchanged → skipped; touched → re-parsed;
    deleted → purged."""
    _write_sample(repo)
    map_codebase.run_map()

    s2 = map_codebase.run_map()
    assert s2 == {**s2, "upserted": 0, "unchanged": 2, "purged": 0}

    # mtime granularity is 1s in the stored ISO string — bump explicitly
    st = (repo / "app.py").stat()
    os.utime(repo / "app.py", (st.st_atime, st.st_mtime + 2))
    s3 = map_codebase.run_map()
    assert s3["upserted"] == 1 and s3["unchanged"] == 1

    (repo / "helper.py").unlink()
    s4 = map_codebase.run_map()
    assert s4["purged"] == 1
    assert not AgentKnowledgeGraph()._g.has_node("helper.py")


def test_walker_ignores_vendor_dirs(repo):
    _write_sample(repo)
    vendor = repo / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "index.js").write_text("export function x() {}\n")
    stats = map_codebase.run_map()
    assert stats["upserted"] == 2  # node_modules not walked


def test_walker_extracts_guardrails(repo):
    _write_sample(repo)
    (repo / ".cursorrules").write_text("## 1. Requirements & Design\nrules\n")
    rfc = repo / ".agent-rfc"
    rfc.mkdir()
    (rfc / "001-auth.md").write_text("# RFC 001 — Auth\n")
    stats = map_codebase.run_map()
    assert stats["guardrails"] == 2
