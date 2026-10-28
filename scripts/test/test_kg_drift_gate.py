"""
scripts/test/test_kg_drift_gate.py — the Knowledge Graph gate detects drift.

`--check-kg` regenerated the graph and then asserted things about the graph it
had just written, so it only ever proved the mapper runs. A committed graph 703
lines behind the code passed it every time (observed 2026-08-24).

The gate compares SHAPE — which files exist, their language, their symbols, and
the import edges — because the raw bytes carry mtimes that churn legitimately,
and it counts only GIT-TRACKED files because the mapper walks the filesystem and
picks up build output that CI never has.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _shared import load_script

MTIME_A = "2020-01-01T00:00:00Z"
MTIME_B = "2026-08-24T09:15:00Z"


TRACKED = {"scripts/a.py", "scripts/b.py"}


@pytest.fixture
def vs(monkeypatch):
    """`_git_tracked_files` is stubbed so these fixtures' synthetic paths count.

    Without the stub every node would be filtered out as untracked and every
    shape would compare equal — the tests would pass having examined nothing,
    which is the defect the module exists to prevent.
    """
    module = load_script("verify_system")
    monkeypatch.setattr(module, "_git_tracked_files", lambda: set(TRACKED))
    return module


@pytest.fixture
def write_graph(tmp_path: Path):
    """Write a graph to its own file and return the path.

    Each call gets a distinct filename so two graphs can be compared without
    one overwriting the other.
    """
    counter = iter(range(1000))

    def _write(
        symbols: list[str],
        mtime: str = MTIME_B,
        rails: list[dict] | None = None,
    ) -> Path:
        graph = {
            "nodes": [
                {
                    "id": "scripts/a.py",
                    "node_type": "CodebaseFile",
                    "language": "python",
                    "symbols": symbols,
                    "last_modified": mtime,
                },
                *(rails or []),
            ],
            "edges": [
                {
                    "source": "scripts/a.py",
                    "target": "scripts/b.py",
                    "edge_type": "imports",
                }
            ],
        }
        path = tmp_path / f"kg_{next(counter)}.json"
        path.write_text(json.dumps(graph))
        return path

    return _write


def test_shape_ignores_mtime(vs, write_graph) -> None:
    """`actions/checkout` stamps the working tree at checkout time, so every
    `last_modified` in a CI-built graph differs from the committed one. A byte
    compare would red-build every run, and a gate that always fails is as
    useless as one that never does."""
    assert vs._kg_shape(write_graph(["f"], MTIME_A)) == vs._kg_shape(
        write_graph(["f"], MTIME_B)
    )


def test_shape_catches_a_new_symbol(vs, write_graph) -> None:
    """Code gained a function and nobody regenerated — the case the gate is for."""
    assert vs._kg_shape(write_graph(["f"])) != vs._kg_shape(write_graph(["f", "g"]))


def test_shape_ignores_symbol_order(vs, write_graph) -> None:
    """Order is an artifact of the parse, not of content."""
    assert vs._kg_shape(write_graph(["f", "g"])) == vs._kg_shape(write_graph(["g", "f"]))


def test_untracked_nodes_are_excluded(vs, write_graph, monkeypatch) -> None:
    """The mapper walks the filesystem, so a graph built on a machine that has
    run `next build` carries portal/next-env.d.ts and a Guardrail node sourced
    from a gitignored, generated file — with an ABSOLUTE path in it. Comparing
    those failed on every CI run, which is a worse gate than the weak one it
    replaced, because the fix is to delete it."""
    graph_with_extra = json.loads(write_graph(["f"]).read_text())
    graph_with_extra["nodes"].append(
        {
            "id": "portal/next-env.d.ts",
            "node_type": "CodebaseFile",
            "language": "typescript",
            "symbols": ["Generated"],
            "last_modified": MTIME_B,
        }
    )
    graph_with_extra["nodes"].append(
        {
            "id": "rfc:fixtures/delivery_evidence.md",
            "node_type": "Guardrail",
            "source_file": "/Users/someone/checkout/.agent-rfc/fixtures/delivery_evidence.md",
        }
    )
    polluted = write_graph(["f"])
    polluted.write_text(json.dumps(graph_with_extra))

    assert vs._kg_shape(polluted) == vs._kg_shape(write_graph(["f"]))


def test_shape_is_none_when_git_cannot_answer(vs, write_graph, monkeypatch) -> None:
    """None makes the caller skip the comparison rather than guess. Treating
    "git unavailable" as "nothing is tracked" would compare two empty shapes
    and call the graph up to date having examined no nodes."""
    monkeypatch.setattr(vs, "_git_tracked_files", lambda: None)
    assert vs._kg_shape(write_graph(["f"])) is None


def test_missing_or_unreadable_graph_is_none(vs, tmp_path: Path) -> None:
    """None, not an empty shape. "No graph" must not compare equal to a graph
    that legitimately has no nodes — that is the conflation the gate exists to
    stop, one level up."""
    assert vs._kg_shape(tmp_path / "absent.json") is None

    unreadable = tmp_path / "bad.json"
    unreadable.write_text("{not json")
    assert vs._kg_shape(unreadable) is None


def test_an_empty_graph_has_a_shape_and_is_not_none(vs, tmp_path: Path) -> None:
    """The other side of the same distinction: a graph with no nodes is a real
    answer, and must be distinguishable from a graph that could not be read."""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"nodes": [], "edges": []}))
    assert vs._kg_shape(empty) is not None


def test_the_gate_forces_a_full_rebuild(monkeypatch) -> None:
    """`check_kg`'s regeneration is the reference the committed graph is
    measured against, so it must not inherit whatever the incremental path last
    left behind.

    The incremental skip can only repair a node whose FILE changed. A graph
    wrong for any other reason — a hand edit, a bad merge, a truncated write —
    is invisible to it and survives every run. One reached a public repo on
    2026-08-24 with a node's symbols replaced by a test string, and three
    regenerations left it untouched because middleware.ts had not been edited.
    """
    vs = load_script("verify_system")
    import map_codebase

    seen: dict = {}

    def fake_run_map(*args, **kwargs):
        seen.update(kwargs)
        return {"upserted": 0}

    monkeypatch.setattr(map_codebase, "run_map", fake_run_map)
    monkeypatch.setattr(vs, "_kg_shape", lambda _p: "same")
    vs.check_kg()

    assert seen.get("force") is True, "check_kg must force a full re-parse"


# ── Guardrail nodes: tracked ones are compared, generated ones are not ───────
#
# The gate reported "✅ knowledge_graph.json is up to date with the code" over a
# graph missing rfc:reviews/design-tree-drift-is-a-pytest-test.md (beeb838,
# 2026-10-26), and 11 CI checks passed over it, because _kg_shape excluded the
# whole Guardrail node type. The exclusion existed for untracked, GENERATED rfc
# docs; these pin the narrower rule that replaced it.


def _rail(
    path: str,
    title: str = "A design",
    pillar: str | None = None,
    created: str = MTIME_A,
) -> dict:
    """A Guardrail node as the mapper writes one: `source_file` is the document's
    repository-relative path, and the id is that path without `.agent-rfc/`."""
    return {
        "id": "rfc:" + path.split(".agent-rfc/", 1)[-1],
        "node_type": "Guardrail",
        "title": title,
        "source_file": path,
        "pillar": pillar,
        "created_at": created,
    }


@pytest.fixture
def vs_rfc(vs, monkeypatch):
    """`vs` with the rfc documents these tests name counted as tracked.

    Every test below needed the same two lines to stub `_git_tracked_files`
    wider; one fixture states it once. The stub matters for the same reason the
    `vs` docstring gives: without it every Guardrail is filtered out as
    untracked, every shape compares equal, and the tests pass having examined
    nothing — which is the defect this file exists to prevent.
    """
    monkeypatch.setattr(
        vs,
        "_git_tracked_files",
        lambda: TRACKED | {".agent-rfc/designs/d.md", ".agent-rfc/reviews/r.md"},
    )
    return vs


def test_shape_catches_a_removed_guardrail(vs_rfc, write_graph) -> None:
    """The staleness that got through: a committed review record with no node.

    This is the exact shape of beeb838 — the graph was regenerated before the
    review file existed, so the file is tracked and the node is absent.
    """
    both = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md"), _rail(".agent-rfc/reviews/r.md")])
    one = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md")])
    assert vs_rfc._kg_shape(both) != vs_rfc._kg_shape(one)


def test_shape_catches_a_retitled_guardrail(vs_rfc, write_graph) -> None:
    """A design renamed in its heading is a different guardrail to anyone
    reading the graph, and the mapper stores the title, so the graph is stale
    until it is regenerated."""
    before = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md", title="The old name")])
    after = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md", title="The new name")])
    assert vs_rfc._kg_shape(before) != vs_rfc._kg_shape(after)


def test_shape_catches_a_changed_pillar(vs_rfc, write_graph) -> None:
    """`pillar` is one of the three fields compared, and nothing else here varies
    it — so dropping it from the tuple would change no test result, which is a
    branch no input reaches rather than a guard. The .cursorrules extractor
    writes it, and a rule moving between pillars is a graph that needs
    regenerating."""
    p2 = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md", pillar="2")])
    p7 = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md", pillar="7")])
    assert vs_rfc._kg_shape(p2) != vs_rfc._kg_shape(p7)


def test_untracked_guardrails_are_excluded(vs_rfc, write_graph) -> None:
    """Why the whole node type was excluded in the first place, kept as a rule.

    `agentsmith delivery evidence` writes .agent-rfc/fixtures/delivery_evidence.md,
    which is gitignored. A machine that has run it has that Guardrail and a fresh
    runner does not, so comparing it failed every CI run — and a gate that always
    fails gets deleted, which is worse than the weak one it replaced.
    """
    without = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md")])
    with_generated = write_graph(["f"], rails=[
        _rail(".agent-rfc/designs/d.md"),
        _rail(".agent-rfc/fixtures/delivery_evidence.md", title="Delivery evidence"),
    ])
    assert vs_rfc._kg_shape(without) == vs_rfc._kg_shape(with_generated)


def test_absolute_source_paths_are_excluded(vs_rfc, write_graph) -> None:
    """The same rule covers the absolute-path case without a special branch:
    _git_tracked_files returns repo-relative paths, so an absolute one is never
    a member."""
    plain = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md")])
    absolute = write_graph(["f"], rails=[
        _rail(".agent-rfc/designs/d.md"),
        _rail("/Users/someone/repo/.agent-rfc/fixtures/delivery_evidence.md"),
    ])
    assert vs_rfc._kg_shape(plain) == vs_rfc._kg_shape(absolute)


def test_shape_ignores_guardrail_created_at(vs_rfc, write_graph) -> None:
    """add_guardrail preserves an existing node's created_at and stamps now()
    only for a new node, which already differs by its presence. Comparing the
    timestamp would make the shape depend on a clock — what last_modified is
    excluded for."""
    old = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md", created=MTIME_A)])
    new = write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md", created=MTIME_B)])
    assert vs_rfc._kg_shape(old) == vs_rfc._kg_shape(new)


def test_guardrails_are_actually_in_the_shape(vs_rfc, write_graph) -> None:
    """Guards the guard. Every assertion above compares two shapes, so all of
    them would pass over a shape that dropped guardrails entirely — which is the
    state this slice is fixing. This one looks."""
    shape = vs_rfc._kg_shape(write_graph(["f"], rails=[_rail(".agent-rfc/designs/d.md", title="A design")]))
    assert "rfc:designs/d.md" in shape and "A design" in shape
