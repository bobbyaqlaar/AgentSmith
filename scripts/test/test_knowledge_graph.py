"""
scripts/test/test_knowledge_graph.py — Knowledge Graph API + map_codebase
walker (TestCoverageReview-2026-07-21 gap 3).

Covers: upsert/persist/reload round-trip, import edges, incident injection,
subgraph context window, symbol/impact queries, stale-node purge, and the
full rebuild of every edge on every run that replaced the incremental mtime
skip of ReviewFindings C2 (P4-R8).

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


def test_walker_rebuilds_every_run_and_purges(repo):
    """Every run parses every file (P4-R8 replaced the C2 mtime skip, which only ever added
    edges); a second run over an unchanged tree builds the same graph; a deleted file's node
    goes."""
    _write_sample(repo)
    map_codebase.run_map()
    first = AgentKnowledgeGraph()._g

    s2 = map_codebase.run_map()
    assert s2 == {**s2, "upserted": 2, "unchanged": 0, "purged": 0}
    second = AgentKnowledgeGraph()._g
    assert set(second.edges) == set(first.edges)
    assert {n: d["symbols"] for n, d in second.nodes(data=True)} == \
        {n: d["symbols"] for n, d in first.nodes(data=True)}

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
    map_codebase.run_map()  # app.py is a node, so the incident links to it
    kg = AgentKnowledgeGraph()
    kg.inject_production_learning(
        "incident:2026-10-18-01", event="gateway timeout", agent="analyst",
        file_hint="app.py", resolution_summary="retry ladder widened",
    )

    map_codebase.run_map()

    graph = AgentKnowledgeGraph()._g
    assert graph.has_node("incident:2026-10-18-01")
    # The rebuild drops import edges only (P4-R8): the incident's link to its file is another tool's data.
    assert graph.has_edge("app.py", "incident:2026-10-18-01")


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
    just because .agent-rfc/ is empty or absent — see Tenant B,
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


# ── What git tracks, by repository-relative path (kg-maps-what-git-tracks.md) ──


@pytest.fixture()
def checkout(monkeypatch, tmp_path):
    """A real git repository: `repo` above fakes `.git`, which `git ls-files`
    cannot answer for."""
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text(".agent-rfc/fixtures/delivery_evidence.md\ngenerated/\n")
    (tmp_path / "app.py").write_text("def main():\n    return 1\n")
    (tmp_path / ".agent-rfc" / "fixtures").mkdir(parents=True)
    (tmp_path / ".agent-rfc" / "designs").mkdir()
    (tmp_path / ".agent-rfc" / "designs" / "a.md").write_text("# A design\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    return tmp_path


def _guardrails() -> dict:
    return {n: d for n, d in AgentKnowledgeGraph()._g.nodes(data=True) if d.get("node_type") == "Guardrail"}


def test_an_ignored_document_or_source_file_makes_no_node(checkout):
    """A generated, ignored document became a Guardrail node read as a rule in
    force (`delivery_evidence.md`, written by the evidence-pack gate)."""
    (checkout / ".agent-rfc" / "fixtures" / "delivery_evidence.md").write_text("# Delivery Model — evidence\n")
    (checkout / "generated").mkdir()
    (checkout / "generated" / "client.py").write_text("def made():\n    return 0\n")

    map_codebase.run_map()

    graph = AgentKnowledgeGraph()._g
    assert "rfc:fixtures/delivery_evidence.md" not in graph
    assert "generated/client.py" not in graph
    assert "rfc:designs/a.md" in graph and "app.py" in graph


def test_the_ignore_list_applies_inside_the_repository_only(monkeypatch, tmp_path):
    """A worktree named `coverage` emptied the graph: every source file's absolute
    path held an ignored name, and the run reported nothing wrong."""
    import subprocess

    root = tmp_path / "build" / "coverage" / "app"
    (root / "build").mkdir(parents=True)
    (root / "app.py").write_text("def main():\n    return 1\n")
    (root / "build" / "made.py").write_text("def made():\n    return 0\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    monkeypatch.chdir(root)

    map_codebase.run_map()

    graph = AgentKnowledgeGraph()._g
    assert "app.py" in graph, "the path leading to the repository is not the repository"
    assert "build/made.py" not in graph, "inside the repository, an ignored name is still ignored"


def test_a_node_for_a_file_that_became_ignored_is_purged(checkout):
    (checkout / ".agent-rfc" / "fixtures" / "delivery_evidence.md").write_text("# Delivery Model — evidence\n")
    (checkout / ".gitignore").write_text("")
    map_codebase.run_map()
    assert "rfc:fixtures/delivery_evidence.md" in AgentKnowledgeGraph()._g

    (checkout / ".gitignore").write_text(".agent-rfc/fixtures/delivery_evidence.md\n")
    map_codebase.run_map()

    assert "rfc:fixtures/delivery_evidence.md" not in AgentKnowledgeGraph()._g


def test_an_untracked_design_not_ignored_still_maps(checkout):
    """A design written before `git add` is the repository's: it must map."""
    (checkout / ".agent-rfc" / "designs" / "new.md").write_text("# A new design\n")
    map_codebase.run_map()
    assert "rfc:designs/new.md" in AgentKnowledgeGraph()._g


def test_source_file_is_repository_relative(checkout):
    (checkout / ".cursorrules").write_text("## 1. Requirements & Design\nrules\n")
    specs = checkout / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "001.md").write_text("# Spec 001\n")

    map_codebase.run_map()

    sources = {n: d["source_file"] for n, d in _guardrails().items()}
    assert sources == {"rfc:designs/a.md": ".agent-rfc/designs/a.md",
                       "cursorrules:pillar:1": ".cursorrules",
                       "superpowers:spec:specs/001.md": "docs/superpowers/specs/001.md"}


def test_outside_a_git_checkout_everything_maps(repo):
    """`repo` fakes `.git`, so git cannot say what it tracks. Unknown is not
    "nothing is tracked": the walk maps everything, as it always did."""
    _write_sample(repo)
    rfc = repo / ".agent-rfc"
    rfc.mkdir()
    (rfc / "001.md").write_text("# RFC 001\n")
    assert map_codebase._mapped(repo) is None
    map_codebase.run_map()
    assert "rfc:001.md" in AgentKnowledgeGraph()._g


# ── The 4.1.0 review's third pass: P3-R17 (.agent-rfc/designs/pass3-root-causes.md) ──

REPO = Path(__file__).resolve().parents[2]


def _python_edges(tmp_path: Path, files: dict[str, str], source: str) -> set[str]:
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    _symbols, raw = map_codebase._parse_python(tmp_path / source)
    found = {map_codebase._resolve_local_import(tmp_path / source, imp, tmp_path, "python") for imp in raw}
    return {f for f in found if f}


def test_a_python_import_keeps_its_full_module_path(tmp_path):
    """P3-R17: only the first component was kept, so `from agentsmith import compliance`
    resolved to nothing and `kg impact` named no Python dependents."""
    files = {"pkg/__init__.py": "", "pkg/mod.py": "", "pkg/sub/__init__.py": "", "pkg/sub/deep.py": "",
             "scripts/helper.py": "", "scripts/tool.py": "", "app.py": ""}
    files["app.py"] = "from pkg import mod\nimport pkg.sub.deep\n"
    assert _python_edges(tmp_path, files, "app.py") >= {"pkg/mod.py", "pkg/sub/deep.py"}
    files["pkg/sub/deep.py"] = "from .. import mod\nfrom . import x\n"
    assert "pkg/mod.py" in _python_edges(tmp_path, files, "pkg/sub/deep.py")
    files["scripts/tool.py"] = "import helper\n"  # a script beside it, on sys.path
    assert "scripts/helper.py" in _python_edges(tmp_path, files, "scripts/tool.py")


def test_a_typescript_import_through_a_tsconfig_alias_resolves(tmp_path):
    """P3-R17: the portal imports through `@/`, and every such edge was dropped."""
    (tmp_path / "portal/lib").mkdir(parents=True)
    (tmp_path / "portal/tsconfig.json").write_text('{"compilerOptions": {"paths": {"@/*": ["./*"]}}}')
    (tmp_path / "portal/lib/db.ts").write_text("export const pool = 1;\n")
    (tmp_path / "portal/lib/auth.ts").write_text("export const a = 1;\n")
    page = tmp_path / "portal/page.tsx"
    page.write_text('import { pool } from "@/lib/db";\n'
                    'export { a } from "./lib/auth";\n'
                    'const m = await import("@/lib/auth");\n')
    _symbols, raw = map_codebase._parse_typescript(page)
    found = {map_codebase._resolve_local_import(page, imp, tmp_path, "typescript") for imp in raw}
    assert {"portal/lib/db.ts", "portal/lib/auth.ts"} <= found


def test_the_committed_graph_knows_who_imports_the_compliance_runtime():
    """The two files the third review measured: 22 and 37 importers, and 0 edges in the graph."""
    import json

    graph = json.loads((REPO / ".agent-rfc/fixtures/knowledge_graph.json").read_text())
    importers = lambda target: {e["source"] for e in graph["edges"] if e["target"] == target}  # noqa: E731
    assert len(importers("agentsmith/compliance.py")) >= 15
    assert len(importers("agentsmith/llm_gateway.py")) >= 25
    assert len(importers("portal/lib/db.ts")) >= 10


def test_a_graph_built_by_another_parser_is_parsed_again_whole(repo):
    """P3-R17: the incremental walk kept a file's edges until the file changed, so a parser
    fix never reached the graph. Every run is whole now, whatever version built the graph."""
    _write_sample(repo)
    map_codebase.run_map()
    kg = AgentKnowledgeGraph()
    kg._g.remove_edge("app.py", "helper.py")
    kg._g.graph["parser_version"] = map_codebase.PARSER_VERSION - 1
    kg.save()
    stats = map_codebase.run_map()  # no file changed
    assert stats["unchanged"] == 0
    graph = AgentKnowledgeGraph()._g
    assert graph.has_edge("app.py", "helper.py")
    assert graph.graph["parser_version"] == map_codebase.PARSER_VERSION


# ── P4-R8: rebuild, don't add (.agent-rfc/designs/pass4-majors.md) ───────────
#
# A re-parsed file's imports were added to the edges it already had, and an unchanged file was
# not looked at, so an import removed from the code stayed in the graph until its file was
# deleted. Edges depend on the whole tree, so every run now builds them from nothing.


def _imports(repo: Path) -> set[tuple[str, str]]:
    graph = AgentKnowledgeGraph()._g
    return {(s, t) for s, t, d in graph.edges(data=True) if d.get("edge_type") == "IMPORTS"}


def _fresh_imports(repo: Path, tmp_path: Path, monkeypatch) -> set[tuple[str, str]]:
    """The same tree, copied to a directory with no graph, built there."""
    import shutil
    fresh = tmp_path / "fresh"
    shutil.rmtree(fresh, ignore_errors=True)
    shutil.copytree(repo, fresh, ignore=shutil.ignore_patterns(".agent-rfc"))
    monkeypatch.chdir(fresh)
    try:
        map_codebase.run_map()
        return _imports(fresh)
    finally:
        monkeypatch.chdir(repo)


def _bump(path: Path) -> None:
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime + 2))


def test_a_file_that_stops_importing_loses_its_edge(repo):
    _write_sample(repo)
    map_codebase.run_map()
    assert ("app.py", "helper.py") in _imports(repo)
    (repo / "app.py").write_text("def main():\n    return 1\n")
    _bump(repo / "app.py")
    map_codebase.run_map()
    assert ("app.py", "helper.py") not in _imports(repo)


def test_an_edge_no_file_makes_does_not_survive_a_build(repo):
    """No file changed, so nothing was re-parsed, and the invented edge stayed (E11)."""
    _write_sample(repo)
    map_codebase.run_map()
    kg = AgentKnowledgeGraph()
    kg.add_import("helper.py", "app.py")
    map_codebase.run_map()
    assert _imports(repo) == {("app.py", "helper.py")}


def test_a_new_file_an_unchanged_file_already_imports_gets_its_edge(repo):
    """`import helper` in an untouched app.py resolves once helper.py exists (E5)."""
    (repo / "app.py").write_text("import helper\n")
    map_codebase.run_map()
    assert _imports(repo) == set()
    (repo / "helper.py").write_text("X = 1\n")
    map_codebase.run_map()
    assert _imports(repo) == {("app.py", "helper.py")}


def test_any_edit_sequence_builds_what_a_fresh_tree_builds(repo, tmp_path, monkeypatch):
    (repo / "pkg").mkdir()
    (repo / "pkg/__init__.py").write_text("")
    (repo / "a.py").write_text("import b\nimport pkg.c\n")
    (repo / "b.py").write_text("import pkg.c\n")
    (repo / "pkg/c.py").write_text("X = 1\n")
    steps = [
        lambda: (repo / "a.py").write_text("import pkg.c\n"),            # an import removed
        lambda: (repo / "b.py").rename(repo / "d.py"),                   # importer unchanged, target renamed
        lambda: (repo / "b.py").write_text("Y = 2\n"),                   # the old name comes back
        lambda: (repo / "pkg/c.py").unlink(),                            # a target deleted
        lambda: (repo / "d.py").write_text("from pkg import c\nimport a\n"),
    ]
    map_codebase.run_map()
    for step in steps:
        step()
        for path in repo.rglob("*.py"):
            _bump(path)
        map_codebase.run_map()
        assert _imports(repo) == _fresh_imports(repo, tmp_path, monkeypatch)


def test_the_check_fails_on_a_committed_edge_no_file_makes(monkeypatch, tmp_path):
    """`--check-kg` compared the committed graph with what the same additive builder made of it,
    so the stale edges passed it (P4-R8). It now compares with a build from nothing."""
    import subprocess
    import verify_system
    repo = tmp_path / "tracked"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    monkeypatch.chdir(repo)
    _write_sample(repo)
    map_codebase.run_map()
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    assert verify_system.check_kg_fresh() is True
    AgentKnowledgeGraph().add_import("helper.py", "app.py")
    assert verify_system.check_kg_fresh() is False
