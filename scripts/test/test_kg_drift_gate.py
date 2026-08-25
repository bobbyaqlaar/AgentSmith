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

    def _write(symbols: list[str], mtime: str = MTIME_B) -> Path:
        graph = {
            "nodes": [
                {
                    "id": "scripts/a.py",
                    "node_type": "CodebaseFile",
                    "language": "python",
                    "symbols": symbols,
                    "last_modified": mtime,
                }
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
