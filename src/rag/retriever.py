"""Chroma similarity over the ACTIVE collection — lang filter, top-k, lenient floor.

The floor is a LENIENT pre-filter only (R3): grade_docs (Tier-1) is the authoritative
gate. Reads the active-collection pointer per request (R7) so a sync flip needs no
restart. Chroma + the genai client are imported lazily so this module is import-safe
and unit-testable with a fake collection.
"""
from __future__ import annotations

import config
from rag import llm
from rag.llm import traceable  # share the optional-langsmith decorator
from schema import ChunkMeta, RetrievedChunk

_client = None
# Per-collection cache of which langs actually have chunks. Lazily populated by
# a metadata-only probe so we don't waste a second vector query on every Russian
# request when the active collection is Hebrew-only. Keyed by collection name so
# a sync flip to a new collection re-probes the new one.
_lang_availability: dict[str, dict[str, bool]] = {}


def _get_collection(name: str | None = None):
    """Open the active (or named) Chroma collection. Lazy — needs chromadb installed."""
    global _client
    import chromadb

    if _client is None:
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client.get_collection(name or config.get_active_collection())


def _lang_present(col_name: str, col, lang: str) -> bool:
    """Cheap metadata-only probe: does ``col`` have any chunk with ``lang``?

    Cached per-collection. ``col.get(where=..., limit=1)`` skips the vector index
    so the probe is far cheaper than a real query. Fails open (True) so a probe
    error never turns into a silent retrieval miss."""
    cache = _lang_availability.setdefault(col_name, {})
    if lang in cache:
        return cache[lang]
    try:
        res = col.get(where={"lang": lang}, limit=1)
        present = bool(res and res.get("ids"))
    except Exception:  # noqa: BLE001 — probe failure must not block retrieval
        present = True
    cache[lang] = present
    return present


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


def _query(col, qvec: list[float], top_k: int, *, where: dict | None = None) -> dict:
    query_kwargs = {
        "query_embeddings": [qvec],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where is not None:
        query_kwargs["where"] = where
    return col.query(**query_kwargs)


@traceable(name="retrieve", run_type="retriever")
def retrieve(query: str, lang: str, *, top_k: int | None = None, collection=None,
             relax_filter: bool = False) -> list[RetrievedChunk]:
    """Embed the query (asymmetric, Q1) and return up to ``top_k`` lang-filtered chunks
    above the lenient floor. Pass ``collection`` to inject a fake in tests.

    ``relax_filter=True`` drops the ``lang`` filter — used by the agent's
    re-retrieve when grade_docs returns ``cross_lingual_thin`` (R2/R4): retrieve
    in the other language and let generate translate per its system prompt.
    ``lang="auto"`` (non-he/ru question) prefers the **Hebrew** sources — the
    most complete corpus, and the citation policy presents Hebrew links for
    non-Russian questions. If the language-filtered query returns no chunks
    above the floor, retry once without the filter — this keeps every language
    usable whatever the active collection contains.
    """
    top_k = top_k or config.TOP_K
    (qvec,) = llm.embed([query], task_type=config.EMBED_TASK_QUERY)
    filter_lang = None
    if not relax_filter:
        if lang in config.LANGS:
            filter_lang = lang
        elif lang == config.AUTO_LANG:
            filter_lang = "he"   # non-Russian questions ground in Hebrew sources
    if collection is None:
        col_name = config.get_active_collection()
        col = _get_collection(col_name)
        # Probe once whether the active collection actually has chunks for this
        # lang; skip the filter on absence so we don't pay 2x Chroma queries per
        # request (e.g. ru questions while the collection is still Hebrew-only).
        if filter_lang is not None and not _lang_present(col_name, col, filter_lang):
            filter_lang = None
    else:
        col = collection
    where = {"lang": filter_lang} if filter_lang is not None else None
    chunks = _to_chunks(_query(col, qvec, top_k, where=where), lang)
    if chunks or where is None:
        return chunks
    return _to_chunks(_query(col, qvec, top_k), lang)
