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
        if not self._ids or k < 1:
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
        return scored[:k]


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
        import psycopg2

        return psycopg2.connect(self.dsn)

    def _ensure_schema(self) -> None:
        import psycopg2

        try:
            with self._connect() as conn:
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
        with self._connect() as conn:
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

    def query(self, text: str, k: int = 5) -> list[VectorHit]:
        if k < 1:
            return []
        q = self.embedder.embed([text])[0]
        q_literal = "[" + ",".join(str(x) for x in q) + "]"
        with self._connect() as conn:
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
        return hits


def make_vector_store(embedder: Optional[Embedder] = None) -> VectorStore:
    backend = os.environ.get("VECTOR_BACKEND", "memory").strip().lower()
    emb = embedder or make_embedder()
    if backend in {"", "memory", "mem", "inmemory"}:
        return MemoryVectorStore(embedder=emb)
    if backend in {"postgres", "pgvector", "pg"}:
        return PgVectorStore(embedder=emb)
    raise ValueError(f"Unknown VECTOR_BACKEND={backend!r}; use memory or postgres")
