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
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/

nx = pytest.importorskip("networkx")

from local_knowledge_graph import AgentKnowledgeGraph
import map_codebase


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


def test_remove_node(repo):
    kg = AgentKnowledgeGraph()
    kg.upsert_file("gone.py")
    kg.remove_node("gone.py")
    assert not kg._g.has_node("gone.py")
    kg.remove_node("never-existed.py")  # no-op, must not raise


def test_remove_node_removes_any_node_type(repo):
    """The behaviour the old name (`remove_file`) denied, and which the
    guardrail purge in `map_codebase.run_map` depends on: the id is the only
    thing that matters, whatever type of node carries it.

    Untested until the rename, because a method called remove_file invited
    tests about files — and the purge that needed this had to carry a comment
    saying the name was wrong.
    """
    kg = AgentKnowledgeGraph()
    kg.upsert_guardrail("rfc:designs/gone.md", "A design since deleted", ".agent-rfc/designs/gone.md", 1)
    kg.upsert_file("app.py")
    kg.inject_production_learning("incident:01", event="timeout", agent="analyst", file_hint="app.py")

    kg.remove_node("rfc:designs/gone.md")
    kg.remove_node("incident:01")

    assert not kg._g.has_node("rfc:designs/gone.md")
    assert not kg._g.has_node("incident:01")
    assert kg._g.has_node("app.py"), "only the ids asked for are removed"


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


def test_walker_ignores_a_checkout_living_inside_the_repo(repo):
    """A git worktree or clone inside the tree is another branch's code, not
    this repository's. This IDE puts one at .claude/worktrees/<name>/, and on
    2026-10-16 that put 196 foreign nodes — a quarter of the graph — into the
    committed fixture, which then differed by machine and failed an unrelated
    allowlist test on names only the stale copy still had.

    A worktree's `.git` is a FILE and a clone's is a DIRECTORY: both are asked
    the same way, and either marks a directory that is not part of this tree.
    """
    _write_sample(repo)

    worktree = repo / ".claude" / "worktrees" / "some-branch"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/some-branch\n")
    # No real retired name goes in here: test_documented_env_vars_exist.py reads
    # every tracked source file, and one in this string would read as "that name
    # is referenced in code again" — which is exactly how this test's first
    # version re-broke the check that found the defect.
    (worktree / "stale.py").write_text("OLD_SETTING = 'x'\n\ndef retired():\n    return 1\n")

    clone = repo / "vendor" / "other-project"
    clone.mkdir(parents=True)
    (clone / ".git").mkdir()
    (clone / "theirs.py").write_text("def theirs():\n    return 2\n")

    stats = map_codebase.run_map()
    assert stats["upserted"] == 2, "only app.py and helper.py belong to this repository"
    kg = AgentKnowledgeGraph()
    assert kg.find_files_by_symbol("retired") == []
    assert kg.find_files_by_symbol("theirs") == []
    assert kg.find_files_by_symbol("main") == ["app.py"]  # the repo's own file is still mapped


def test_a_file_the_walker_no_longer_claims_is_purged(repo):
    """Purging asked two questions — "not seen" AND "gone from disk" — so a
    node the walker stopped claiming survived forever while its file existed.
    That is why adding an ignore rule could not clean a graph that already held
    196 nodes from an IDE worktree: the files were still there.

    Not seen by the walk IS the answer; the file existing somewhere under the
    root is not a reason to keep a node for it.
    """
    _write_sample(repo)
    other = repo / "vendor" / "other-project"
    other.mkdir(parents=True)
    (other / "theirs.py").write_text("def theirs():\n    return 2\n")

    assert map_codebase.run_map()["upserted"] == 3          # walked as ours, for now
    assert AgentKnowledgeGraph().find_files_by_symbol("theirs") == ["vendor/other-project/theirs.py"]

    (other / ".git").mkdir()                                # it is its own checkout after all
    stats = map_codebase.run_map()

    assert stats["purged"] == 1, "the node must go even though the file is still on disk"
    assert AgentKnowledgeGraph().find_files_by_symbol("theirs") == []
    assert AgentKnowledgeGraph().find_files_by_symbol("main") == ["app.py"]


def test_a_guardrail_whose_document_is_gone_is_purged(repo):
    """A design, review or RFC becomes a `rfc:<path>` Guardrail node, and until
    this nothing ever removed one: delete the document and the node stayed
    forever, read by `fetch_subgraph_context_window` as a rule still in force.

    Seen for real on 2026-10-17 (`rfc:designs/shell-gate-one-walk.md` surviving
    a file that was not on disk) and reproduced on this checkout the next day
    with a throwaway probe document.
    """
    _write_sample(repo)
    rfc = repo / ".agent-rfc"
    rfc.mkdir()
    (rfc / "001-auth.md").write_text("# RFC 001 — Auth\n")
    (rfc / "002-probe.md").write_text("# RFC 002 — a document about to be deleted\n")

    map_codebase.run_map()
    assert AgentKnowledgeGraph()._g.has_node("rfc:002-probe.md")

    (rfc / "002-probe.md").unlink()
    stats = map_codebase.run_map()

    kg = AgentKnowledgeGraph()
    assert not kg._g.has_node("rfc:002-probe.md"), "the document is gone; so is its guardrail"
    assert kg._g.has_node("rfc:001-auth.md"), "the one still on disk stays"
    assert stats["purged"] >= 1


def test_a_pillar_removed_from_cursorrules_is_purged(repo):
    """The sibling case, and the reason the test is "did this walk claim it?"
    rather than "is the file gone?": `.cursorrules` is still there, but it no
    longer produces that pillar."""
    _write_sample(repo)
    rules = repo / ".cursorrules"
    rules.write_text("## 1. Requirements & Design\nr\n## 2. Build Architecture\nr\n")
    map_codebase.run_map()
    assert AgentKnowledgeGraph()._g.has_node("cursorrules:pillar:2")

    rules.write_text("## 1. Requirements & Design\nr\n")
    map_codebase.run_map()

    kg = AgentKnowledgeGraph()
    assert not kg._g.has_node("cursorrules:pillar:2")
    assert kg._g.has_node("cursorrules:pillar:1")


def test_a_production_incident_survives_the_walk(repo):
    """ProductionIncident nodes are injected by other tooling, never produced by
    a walk. A purge keyed on "not seen" alone would delete them on the next
    run — the node TYPE is the filter, as it is for files."""
    _write_sample(repo)
    kg = AgentKnowledgeGraph()
    kg.inject_production_learning(
        "incident:2026-10-18-01", event="gateway timeout", agent="analyst",
        file_hint="app.py", resolution_summary="retry ladder widened",
    )

    map_codebase.run_map()

    assert AgentKnowledgeGraph()._g.has_node("incident:2026-10-18-01")


def test_walker_extracts_guardrails(repo):
    _write_sample(repo)
    (repo / ".cursorrules").write_text("## 1. Requirements & Design\nrules\n")
    rfc = repo / ".agent-rfc"
    rfc.mkdir()
    (rfc / "001-auth.md").write_text("# RFC 001 — Auth\n")
    stats = map_codebase.run_map()
    assert stats["guardrails"] == 2


def test_walker_extracts_superpowers_guardrails_alongside_rfc(repo):
    """A repo using the superpowers skill's docs/superpowers/{specs,plans}
    instead of (or alongside) .agent-rfc/ must not go invisible to the graph
    just because .agent-rfc/ is empty or absent — see AqlaarTeleologyStudio,
    the tenant this was found against."""
    _write_sample(repo)
    specs = repo / "docs" / "superpowers" / "specs"
    plans = repo / "docs" / "superpowers" / "plans"
    specs.mkdir(parents=True)
    plans.mkdir(parents=True)
    (specs / "001-ingest.md").write_text("# Spec 001 — Ingest pipeline\n")
    (plans / "001-ingest.md").write_text("# Plan 001 — Ingest pipeline\n")
    stats = map_codebase.run_map()
    assert stats["guardrails"] == 2

    kg = AgentKnowledgeGraph()
    rule_ids = {
        n
        for n, d in kg._g.nodes(data=True)
        if d.get("node_type") == "Guardrail"
    }
    assert "superpowers:spec:specs/001-ingest.md" in rule_ids
    assert "superpowers:plan:plans/001-ingest.md" in rule_ids
