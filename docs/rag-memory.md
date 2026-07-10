# Memory & RAG (v1)

Short-term conversation buffer + long-term vector retrieval for Delivery
Model need #4 (standard RAG functions).

## Short-term — `runtime/conversation_memory.py`

```python
from runtime.conversation_memory import ConversationMemory

mem = ConversationMemory(token_budget=4000)
mem.add("user", "long conversation…")
mem.add("assistant", "…")
gateway.complete(mem.as_messages())
```

Evicts **oldest** messages when over budget (`tiktoken`; char/4 fallback).
Summarization eviction is v2.

## Long-term — `runtime/vector_store.py` + `runtime/embeddings.py`

```python
from runtime.vector_store import make_vector_store

store = make_vector_store()  # VECTOR_BACKEND=memory (default)
store.add(ids=["doc1"], texts=["UAE Falcon residency checklist…"])
hits = store.query("data residency", k=3)
```

| Env | Meaning |
|---|---|
| `VECTOR_BACKEND=memory` | In-process cosine (CI / default) |
| `VECTOR_BACKEND=postgres` | pgvector table `agentsmith_embeddings` (needs `CREATE EXTENSION vector` + `DATABASE_URL`) |
| `EMBEDDER=hash` | Deterministic fake vectors (default / tests) |
| `EMBEDDER=sentence-transformers` | Local model (`EMBEDDING_MODEL`, default `all-MiniLM-L6-v2`) |

Install local embedder:

```bash
pip install 'sentence-transformers>=3.0,<4.0'
export EMBEDDER=sentence-transformers
```

## Not included (yet)

- Automatic RAG pipeline inside `llm_gateway.complete()` (tenant wires retrieve → prompt)
- Chunking / document ingest CLI
- Hybrid KG + vector fusion

See `FIXES_AND_CLEANUP.md` Memory Management.
