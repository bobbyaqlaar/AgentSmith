"""
runtime/test/test_pg_pool_coverage.py — every Postgres-backed store borrows
from the pool, and pg_pool's own docstring lists all of them.

`runtime/pg_pool.py` exists because each store used to open a fresh
`psycopg2.connect()` per operation (ReviewFindings C1). Three stores were
converted; `vector_store.PgVectorStore` was missed and kept connecting per
`add()` and per `query()` — a TCP + auth round-trip on every RAG lookup. It was
missed partly because the pool's docstring enumerated three stores as though
that were the full set.

PgVectorStore's call sites also used `with psycopg2.connect(...) as conn:`,
where psycopg2's context manager wraps the transaction and leaves the socket
open — so the old code leaked a connection per call rather than merely
failing to reuse one.
"""

from __future__ import annotations

import re
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]


def _sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in RUNTIME.glob("*.py")}


def _strip_comments(src: str) -> str:
    """Drop `#` lines so prose describing a defect isn't matched as one."""
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )


def test_no_store_opens_a_raw_connection() -> None:
    """The pool is only a pool if nothing bypasses it."""
    offenders = {
        name: [
            i + 1
            for i, line in enumerate(src.splitlines())
            if "psycopg2.connect(" in line and not line.lstrip().startswith("#")
        ]
        for name, src in _sources().items()
        if name != "pg_pool.py"
    }
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, (
        f"raw psycopg2.connect() outside pg_pool.py: {offenders} — route it "
        f"through runtime.pg_pool.connect() so the connection is reused"
    )


def test_pooled_connections_are_released_not_context_managed() -> None:
    """`with pg_pool.connect(dsn) as conn:` borrows and never returns.

    The proxy's __enter__/__exit__ delegate to psycopg2's connection context
    manager, which manages the TRANSACTION — it does not call .close(), and
    .close() is what hands the connection back. So a `with` on the borrow
    exhausts the pool, which is strictly worse than the leak it replaced.
    """
    # Comments are stripped first: this file's own `_connect` docstring quotes
    # the old `with self._connect() as conn:` pattern to explain why it went
    # away, and a naive scan flags the explanation as the defect.
    src = _strip_comments((RUNTIME / "vector_store.py").read_text(encoding="utf-8"))
    assert not re.search(r"with\s+self\._connect\(\)\s+as\b", src), (
        "vector_store borrows a pooled connection with `with` — it will never "
        "be returned; use `conn = self._connect()` + `finally: conn.close()`"
    )
    # Every borrow is balanced by a release.
    assert src.count("self._connect()") == src.count("conn.close()"), (
        "every borrow must be matched by a release"
    )


def test_pool_docstring_lists_every_postgres_store() -> None:
    """A stale enumeration is what let PgVectorStore stay unconverted."""
    doc = (RUNTIME / "pg_pool.py").read_text(encoding="utf-8").split('"""')[1]
    stores = {
        "vector_store.py": "PgVectorStore",
        "dead_letter.py": "DeadLetterQueue",
        "idempotency.py": "_PostgresBackend",
        "llm_gateway.py": "_PostgresBudgetBackend",
    }
    for filename, symbol in stores.items():
        src = (RUNTIME / filename).read_text(encoding="utf-8")
        if "pg_pool" not in src:
            continue
        assert symbol in doc, (
            f"{filename} uses the pool but pg_pool.py's docstring does not "
            f"list {symbol} — keep the enumeration complete"
        )
