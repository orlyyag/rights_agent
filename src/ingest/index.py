"""Embed + upsert chunks into a Chroma collection (blue-green target, §0 #4).

Builds into a named collection ``kz_v{N+1}`` (or a corpus collection for fast-start);
the caller flips the active pointer after a smoke check. Chroma is imported lazily so
this module is import-safe and the batching/upsert logic is testable with a fake client.
"""
from __future__ import annotations

import time
from collections.abc import Iterable, Iterator

import config
from rag import llm
from schema import Chunk


def _batched(items: list[Chunk], n: int) -> Iterator[list[Chunk]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


def get_or_create(name: str, *, client=None):
    """Open/create a cosine-space collection. Lazy — needs chromadb installed."""
    import chromadb

    client = client or chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})


def build_collection(chunks: Iterable[Chunk], name: str, *, collection=None,
                     client=None, batch_size: int = 100,
                     inter_batch_sleep_s: float | None = None) -> object:
    """Embed (RETRIEVAL_DOCUMENT, Q1) and upsert all chunks into ``name``.

    Pass ``collection`` to inject a fake in tests. Upsert (not add) so re-indexing the
    same ids replaces rather than duplicates. ``inter_batch_sleep_s`` paces against the
    Gemini embedding TPM cap (defaults to ``config.INTER_BATCH_SLEEP_S``; pass 0 in tests).
    """
    col = collection if collection is not None else get_or_create(name, client=client)
    sleep_s = config.INTER_BATCH_SLEEP_S if inter_batch_sleep_s is None else inter_batch_sleep_s
    chunks = list(chunks)
    total = len(chunks)
    batches = list(_batched(chunks, batch_size))
    done = 0
    for i, batch in enumerate(batches):
        vectors = llm.embed([c.text for c in batch], task_type=config.EMBED_TASK_DOCUMENT)
        col.upsert(
            ids=[c.id for c in batch],
            embeddings=vectors,
            documents=[c.text for c in batch],
            metadatas=[c.meta.to_metadata() for c in batch],
        )
        done += len(batch)
        print(f"  embedded {done}/{total} chunks", flush=True)
        if sleep_s and i < len(batches) - 1:
            time.sleep(sleep_s)
    return col
