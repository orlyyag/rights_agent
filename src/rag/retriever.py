"""Chroma similarity over the ACTIVE collection — lang filter, top-k, lenient floor.

The floor is a LENIENT pre-filter only (R3): grade_docs (Tier-1) is the authoritative
gate. Reads the active-collection pointer per request (R7) so a sync flip needs no
restart. Chroma + the genai client are imported lazily so this module is import-safe
and unit-testable with a fake collection.
"""
from __future__ import annotations

import config
from rag import llm
from schema import ChunkMeta, RetrievedChunk

_client = None


def _get_collection(name: str | None = None):
    """Open the active (or named) Chroma collection. Lazy — needs chromadb installed."""
    global _client
    import chromadb

    if _client is None:
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client.get_collection(name or config.get_active_collection())


def _distance_to_similarity(distance: float) -> float:
    """Chroma cosine distance → similarity. Collections are built with cosine space."""
    return 1.0 - float(distance)


def _to_chunks(result: dict, lang: str) -> list[RetrievedChunk]:
    """Map a Chroma query result → scored chunks, dropping anything below the lenient floor."""
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    dists = result["distances"][0]
    floor = config.SIMILARITY_FLOOR_BY_LANG.get(lang, config.SIMILARITY_FLOOR)

    out: list[RetrievedChunk] = []
    for doc, meta, dist in zip(docs, metas, dists):
        score = _distance_to_similarity(dist)
        if score < floor:  # lenient pre-filter (R3)
            continue
        out.append(RetrievedChunk(text=doc, meta=ChunkMeta.from_metadata(meta), score=score))
    return out


def retrieve(query: str, lang: str, *, top_k: int | None = None, collection=None) -> list[RetrievedChunk]:
    """Embed the query (asymmetric, Q1) and return up to ``top_k`` lang-filtered chunks
    above the lenient floor. Pass ``collection`` to inject a fake in tests."""
    top_k = top_k or config.TOP_K
    (qvec,) = llm.embed([query], task_type=config.EMBED_TASK_QUERY)
    col = collection if collection is not None else _get_collection()
    result = col.query(
        query_embeddings=[qvec],
        n_results=top_k,
        where={"lang": lang},
        include=["documents", "metadatas", "distances"],
    )
    return _to_chunks(result, lang)
