"""Embed + upsert chunks into a Chroma collection (blue-green target, §0 #4).

Builds into a named collection ``kz_v{N+1}`` (or a corpus collection for fast-start);
the caller flips the active pointer after a smoke check. Chroma is imported lazily so
this module is import-safe and the batching/upsert logic is testable with a fake client.
"""
from __future__ import annotations

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
                     client=None, batch_size: int = 100) -> object:
    """Embed (RETRIEVAL_DOCUMENT, Q1) and upsert all chunks into ``name``.

    Pass ``collection`` to inject a fake in tests. Upsert (not add) so re-indexing the
    same ids replaces rather than duplicates.
    """
    col = collection if collection is not None else get_or_create(name, client=client)
    chunks = list(chunks)
    for batch in _batched(chunks, batch_size):
        vectors = llm.embed([c.text for c in batch], task_type=config.EMBED_TASK_DOCUMENT)
        col.upsert(
            ids=[c.id for c in batch],
            embeddings=vectors,
            documents=[c.text for c in batch],
            metadatas=[c.meta.to_metadata() for c in batch],
        )
    return col
