"""
runtime/embeddings.py — pluggable text embedders for vector retrieval.

EMBEDDER env:
  hash (default in tests / when unset and sentence-transformers missing)
  sentence-transformers | st  — local SentenceTransformer model

EMBEDDING_MODEL — model id for sentence-transformers (default all-MiniLM-L6-v2)
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


class HashEmbedder:
    """Deterministic fake embedder for tests/CI — no model download."""

    def __init__(self, dim: int = 384) -> None:
        if dim < 8:
            raise ValueError("dim must be >= 8")
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Expand digest to dim floats in [-1, 1], then L2-normalize
        vals: list[float] = []
        seed = digest
        while len(vals) < self.dim:
            for i in range(0, len(seed) - 3, 4):
                if len(vals) >= self.dim:
                    break
                (n,) = struct.unpack(">I", seed[i : i + 4])
                vals.append((n / 0xFFFFFFFF) * 2.0 - 1.0)
            seed = hashlib.sha256(seed).digest()
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]


class SentenceTransformerEmbedder:
    """Local embeddings via sentence-transformers (lazy import)."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.environ.get(
            "EMBEDDING_MODEL", "all-MiniLM-L6-v2"
        )
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. "
                "pip install 'sentence-transformers>=3.0,<4.0' "
                "or set EMBEDDER=hash for tests."
            ) from exc
        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # The embedding hop emitted nothing, and it is the one most likely to
        # be the latency this framework's users are hunting: a local
        # sentence-transformers model can take longer than the LLM call it
        # feeds. Instrumented on the REAL embedder only — HashEmbedder is
        # arithmetic, and a span per call would be noise per SPECS' own
        # "trace what can be slow" rule.
        from runtime.tracing import agent_span

        with agent_span(
            "embedding.encode", kind="embedding", model=self.model_name, count=len(texts)
        ) as span:
            self._load()
            assert self._model is not None
            vectors = self._model.encode(texts, normalize_embeddings=True)
            out = [list(map(float, row)) for row in vectors]
            try:
                if out:
                    span.set_attribute("agent.embedding.dimensions", len(out[0]))
            except Exception:  # fail-open
                pass
            return out


def make_embedder() -> Embedder:
    kind = os.environ.get("EMBEDDER", "").strip().lower()
    if kind in {"st", "sentence-transformers", "sentence_transformers", "local"}:
        return SentenceTransformerEmbedder()
    if kind in {"", "hash", "fake", "test"}:
        return HashEmbedder()
    raise ValueError(f"Unknown EMBEDDER={kind!r}; use hash or sentence-transformers")
