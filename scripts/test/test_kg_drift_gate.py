"""
scripts/test/test_kg_drift_gate.py — the Knowledge Graph gate detects drift.

`--check-kg` regenerated the graph and then asserted things about the graph it
had just written, so it only ever proved the mapper runs. A committed graph 703
lines behind the code passed it every time (observed 2026-08-24).

The gate compares SHAPE — which files exist, their language, their symbols, and
the import edges — because the raw bytes carry mtimes that churn legitimately.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _shared import load_script  # noqa: E402

MTIME_A = "2020-01-01T00:00:00Z"
MTIME_B = "2026-08-24T09:15:00Z"


@pytest.fixture
def vs():
    return load_script("verify_system")


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
