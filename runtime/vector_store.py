"""
runtime/vector_store.py — long-term semantic retrieval (RAG substrate).

VECTOR_BACKEND:
  memory (default) — in-process cosine search
  postgres         — pgvector table (requires vector extension + DATABASE_URL)

Usage:
    store = make_vector_store()
    store.add(ids=["1"], texts=["oil price spike"])
    hits = store.query("commodity volatility", k=5)
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

from runtime.embeddings import Embedder, make_embedder

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VectorHit:
    id: str
    text: str
    score: float
    metadata: dict[str, Any]


@runtime_checkable
class VectorStore(Protocol):
    def add(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None: ...

    def query(self, text: str, k: int = 5) -> list[VectorHit]: ...


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _retrieval_span(backend: str, k: int):
    """A span around a retrieval, or a no-op when tracing is off.

    The retrieval hop emitted NOTHING — not a span, not a duration. In the
    chain this framework advertises (API → orchestrator → vector DB →
    embedding → LLM → database) only the LLM hop was visible, so "the retriever
    was slow" and "the model was slow" were the same picture.
    """
    from runtime.tracing import agent_span

    return agent_span(f"retrieval.{backend}", kind="retrieval", k=k)


def _record_hits(span, hits: list, *, corpus: Optional[int] = None) -> None:
    """Chunk IDENTITIES and scores, not just a count.

    `agent.tool.result_count` was the only thing the framework recorded about a
    retrieval, and a count of 3 says nothing when the wrong three came back —
    which is the single most common question asked of a RAG system. The ids and
    the score range are what separate "the retriever failed" from "the model
    ignored good context".

    Text is deliberately NOT recorded: retrieved documents are the most likely
    place for PII to enter a span, and trace_redactor runs after this.
    """
    try:
        span.set_attribute("agent.retrieval.hit_count", len(hits))
        if corpus is not None:
            span.set_attribute("agent.retrieval.corpus_size", corpus)
        if hits:
            span.set_attribute(
                "agent.retrieval.hit_ids", [str(h.id) for h in hits][:20]
            )
            scores = [float(h.score) for h in hits]
            span.set_attribute("agent.retrieval.top_score", max(scores))
            span.set_attribute("agent.retrieval.min_score", min(scores))
    except Exception:  # fail-open: an attribute write must never break a query
        pass


class MemoryVectorStore:
    """In-memory vector index — default for CI and local without Postgres."""

    def __init__(self, embedder: Optional[Embedder] = None) -> None:
        self.embedder = embedder or make_embedder()
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metas: list[dict[str, Any]] = []
        self._vectors: list[list[float]] = []

    def add(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        if len(ids) != len(texts):
            raise ValueError("ids and texts must be the same length")
        metas = metadatas or [{} for _ in ids]
        if len(metas) != len(ids):
            raise ValueError("metadatas length must match ids")
        vectors = self.embedder.embed(texts)
        for vid, text, meta, vec in zip(ids, texts, metas, vectors):
            if vid in self._ids:
                idx = self._ids.index(vid)
                self._texts[idx] = text
                self._metas[idx] = dict(meta)
                self._vectors[idx] = vec
            else:
                self._ids.append(vid)
                self._texts.append(text)
                self._metas.append(dict(meta))
                self._vectors.append(vec)

    def query(self, text: str, k: int = 5) -> list[VectorHit]:
        with _retrieval_span("memory", k) as span:
            if not self._ids or k < 1:
                _record_hits(span, [], corpus=len(self._ids))
                return []
            q = self.embedder.embed([text])[0]
            scored = [
                VectorHit(
                    id=self._ids[i],
                    text=self._texts[i],
                    score=_cosine(q, self._vectors[i]),
                    metadata=dict(self._metas[i]),
                )
                for i in range(len(self._ids))
            ]
            scored.sort(key=lambda h: h.score, reverse=True)
            hits = scored[:k]
            _record_hits(span, hits, corpus=len(self._ids))
            return hits


class PgVectorStore:
    """
    Postgres + pgvector backend.

    Creates table agentsmith_embeddings if missing. Requires:
      CREATE EXTENSION vector;
    """

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        dsn: Optional[str] = None,
        dim: Optional[int] = None,
    ) -> None:
        self.embedder = embedder or make_embedder()
        self.dsn = dsn or os.environ.get("DATABASE_URL")
        if not self.dsn:
            raise RuntimeError("PgVectorStore requires DATABASE_URL")
        # Infer dim from a probe embed
        probe = self.embedder.embed(["dim-probe"])[0]
        self.dim = dim or len(probe)
        self._ensure_schema()

    def _connect(self) -> Any:
        # Pooled (runtime/pg_pool.py) — .close() releases to the pool, so the
        # `finally: conn.close()` call sites below stay correct as-is. Same
        # shape as dead_letter / idempotency / llm_gateway's budget store.
        #
        # This was the last raw `psycopg2.connect()` in the codebase, and the
        # store pg_pool's docstring forgot to list. It opened a fresh
        # connection per add() AND per query() — a TCP + auth round-trip on
        # every RAG lookup, which is precisely the cost ReviewFindings C1
        # removed everywhere else.
        #
        # It also leaked: the call sites used `with self._connect() as conn:`,
        # and psycopg2's connection context manager wraps the TRANSACTION, not
        # the connection — the socket stays open when the block exits. So they
        # are rewritten to try/finally. Keeping `with` here would be worse than
        # before, since an un-returned pooled connection exhausts the pool
        # rather than just leaking one socket.
        from runtime.pg_pool import connect as pg_connect

        return pg_connect(self.dsn)

    def _ensure_schema(self) -> None:
        import psycopg2

        conn = None
        try:
            conn = self._connect()
            with conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS agentsmith_embeddings (
                            id TEXT PRIMARY KEY,
                            text TEXT NOT NULL,
                            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                            embedding vector({self.dim}) NOT NULL
                        )
                        """
                    )
                conn.commit()
        except psycopg2.Error as exc:
            raise RuntimeError(
                "PgVectorStore needs Postgres with the pgvector extension. "
                f"Install pgvector or use VECTOR_BACKEND=memory. Underlying: {exc}"
            ) from exc
        finally:
            if conn is not None:
                conn.close()  # returns to the pool

    def add(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        if len(ids) != len(texts):
            raise ValueError("ids and texts must be the same length")
        metas = metadatas or [{} for _ in ids]
        vectors = self.embedder.embed(texts)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                for vid, text, meta, vec in zip(ids, texts, metas, vectors):
                    cur.execute(
                        """
                        INSERT INTO agentsmith_embeddings (id, text, metadata, embedding)
                        VALUES (%s, %s, %s::jsonb, %s::vector)
                        ON CONFLICT (id) DO UPDATE SET
                          text = EXCLUDED.text,
                          metadata = EXCLUDED.metadata,
                          embedding = EXCLUDED.embedding
                        """,
                        (vid, text, json.dumps(meta), "[" + ",".join(str(x) for x in vec) + "]"),
                    )
            conn.commit()
        finally:
            conn.close()  # returns to the pool

    def query(self, text: str, k: int = 5) -> list[VectorHit]:
        with _retrieval_span("pgvector", k) as span:
            return self._query(text, k, span)

    def _query(self, text: str, k: int, span) -> list[VectorHit]:
        if k < 1:
            _record_hits(span, [])
            return []
        q = self.embedder.embed([text])[0]
        q_literal = "[" + ",".join(str(x) for x in q) + "]"
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, text, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM agentsmith_embeddings
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (q_literal, q_literal, k),
                )
                rows = cur.fetchall()
        finally:
            conn.close()  # returns to the pool
        hits: list[VectorHit] = []
        for row in rows:
            meta = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
            hits.append(
                VectorHit(
                    id=row[0],
                    text=row[1],
                    score=float(row[3]),
                    metadata=meta,
                )
            )
        _record_hits(span, hits)
        return hits


def make_vector_store(embedder: Optional[Embedder] = None) -> VectorStore:
    backend = os.environ.get("VECTOR_BACKEND", "memory").strip().lower()
    emb = embedder or make_embedder()
    if backend in {"", "memory", "mem", "inmemory"}:
        return MemoryVectorStore(embedder=emb)
    if backend in {"postgres", "pgvector", "pg"}:
        return PgVectorStore(embedder=emb)
    raise ValueError(f"Unknown VECTOR_BACKEND={backend!r}; use memory or postgres")
