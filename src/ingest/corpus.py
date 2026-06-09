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


_EXPECTED_FIELDS = {"doc_id", "title", "link", "content"}


def _records(data: Any) -> list[dict]:
    """Normalize the corpus JSON to a list of record dicts. Supports three shapes:
    (a) list of records, (b) dict keyed by doc_id with record values, and
    (c) column-oriented pandas-style {field: {row_idx: value}} — the actual on-disk
    shape (verified 2026-06-09, 24,487 rows, 143 MB)."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        raise ValueError(f"unsupported corpus shape: {type(data).__name__}")
    if _EXPECTED_FIELDS & set(data.keys()):  # column-oriented
        # Some columns (e.g. ``license``) may be a scalar instead of a per-row dict
        # when the value is uniform — broadcast those across rows. Use the first
        # actual per-row dict column to determine the row index.
        first_col = next(c for c in data.values() if isinstance(c, dict))
        row_keys = list(first_col.keys())
        rows: list[dict] = []
        for k in row_keys:
            row = {}
            for field, col in data.items():
                row[field] = col[k] if isinstance(col, dict) else col
            rows.append(row)
        return rows
    return list(data.values())  # dict-of-records


def load_corpus_chunks(path: str | Path | None = None, *, lang: str = "he",
                       source: str = "corpus") -> list[Chunk]:
    """Read the corpus JSON → Chunks (handles list / id-keyed dict / column-oriented dict)."""
    path = Path(path) if path else (config.CORPUS_DIR / "corpus.json")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [corpus_record_to_chunk(rec, i, lang, source) for i, rec in enumerate(_records(data))]
