"""Fast-start loader: official Hebrew Paragraph Corpus → Chunks (source='corpus', §0 #2).

The corpus is throwaway scaffolding (cut over to the pipeline once validated). It is
pre-chunked (≤512 tok) JSON with fields ``doc_id / title / link / content / license``.

⚠ Verify against the real file once downloaded (T3-adjacent): exact field names and
whether ``doc_id`` is numeric. Tables are assumed flattened (R1) — Tier-0 demo curates
away from tabular benefit-amount questions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config
from schema import Chunk, ChunkMeta, chunk_id


def _coerce_pageid(doc_id: Any, fallback: int) -> int:
    """Real MediaWiki pageids are ints; if the corpus doc_id isn't numeric, derive a
    stable int (corpus citations use the URL, not the pageid, so this is safe here)."""
    s = str(doc_id)
    if s.isdigit():
        return int(s)
    return abs(hash(s)) % (10**9)


def corpus_record_to_chunk(rec: dict, idx: int, lang: str = "he", source: str = "corpus") -> Chunk:
    title = rec.get("title", "")
    url = rec.get("link", "") or rec.get("url", "")
    body = rec.get("content", "") or ""
    pageid = _coerce_pageid(rec.get("doc_id", idx), idx)
    text = f"{title}\n\n{body}".strip() if title else body.strip()
    meta = ChunkMeta(pageid=pageid, title=title, url=url, lang=lang,
                     section="", lastrevid=0, source=source)
    return Chunk(id=chunk_id(source, lang, pageid, idx), text=text, meta=meta)


def load_corpus_chunks(path: str | Path | None = None, *, lang: str = "he",
                       source: str = "corpus") -> list[Chunk]:
    """Read the corpus JSON (list of records, or dict keyed by doc_id) → Chunks."""
    path = Path(path) if path else (config.CORPUS_DIR / "corpus.json")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = list(data.values()) if isinstance(data, dict) else list(data)
    return [corpus_record_to_chunk(rec, i, lang, source) for i, rec in enumerate(records)]
