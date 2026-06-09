"""Tier-0 fast-start entrypoint: load the Hebrew corpus → Chroma → flip the active pointer.

Usage (from repo root):
    PYTHONPATH=.:src python scripts/load_corpus.py [path/to/corpus.json]

Requires chromadb + google-genai installed and GEMINI_API_KEY set.
"""
from __future__ import annotations

import sys

import config
from ingest import corpus, index


def main(path: str | None = None, collection: str = "kz_corpus_he") -> None:
    chunks = corpus.load_corpus_chunks(path)
    print(f"Loaded {len(chunks)} corpus chunks; embedding + upserting → {collection} …")
    index.build_collection(chunks, collection)
    config.set_active_collection(collection)
    print(f"Done. Active collection flipped to '{collection}' (read per-request, R7).")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
