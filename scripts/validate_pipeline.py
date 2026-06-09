"""Tier-1 brick 1 end-to-end validation.

Walks 10 HE pages through the full pipeline: acquire → clean → chunk. Reports
per-page stats (sections, chunks, tables preserved) plus a side-by-side spot
check against the Webiks corpus for the same pageid (when present).

This validates the R1 fix: that tables in the source HTML come through as
markdown tables (numbers preserved), not flattened prose.

Run (from repo root):
    PYTHONPATH=.:src python scripts/validate_pipeline.py
"""
from __future__ import annotations

import json
from pathlib import Path

import chromadb

import config
from ingest import acquire, chunk, clean, mediawiki

N_PAGES = 10


def _table_count(doc: clean.CleanedDoc) -> int:
    return sum(1 for s in doc.sections if "|---|" in s.text)


def _corpus_chunks_for(pageid: int, collection) -> list[dict]:
    """Pull chunks from the Webiks corpus for this pageid (if any)."""
    res = collection.get(where={"pageid": pageid}, include=["documents", "metadatas"])
    return [{"text": d, "meta": m} for d, m in zip(res["documents"], res["metadatas"])]


def main() -> None:
    client = mediawiki.MediaWikiClient("he", request_interval_s=1.0)
    chroma = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    corpus_col = chroma.get_collection("kz_corpus_he")

    print(f"{'pageid':>6} | {'title':40s} | sect | chunks | tables(md) | "
          f"corpus#chunks | overlap?")
    print("-" * 110)

    selected = []
    for info in client.manifest(batch_size=N_PAGES):
        selected.append(info)
        if len(selected) >= N_PAGES:
            break

    sample_with_table = None
    for info in selected:
        parsed = client.parse(info.pageid)
        # Write to the actual raw layer so the pipeline state is real.
        raw_path = acquire.write_raw("he", info, parsed.get("html", ""))
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        cleaned = clean.clean(raw)
        chunks = chunk.chunk_doc(cleaned)

        n_sec = len(cleaned.sections)
        n_chunks = len(chunks)
        n_tables = _table_count(cleaned)

        corpus = _corpus_chunks_for(info.pageid, corpus_col)
        n_corpus = len(corpus)
        overlap = "—"
        if n_corpus and chunks:
            # Rough overlap proxy: any 8+ word substring shared between any
            # corpus chunk and any pipeline chunk for this pageid.
            corpus_text = " ".join(c["text"] for c in corpus)
            pipeline_text = " ".join(c.text for c in chunks)
            corpus_words = corpus_text.split()
            shared = False
            for i in range(0, len(corpus_words) - 8, 4):
                phrase = " ".join(corpus_words[i:i + 8])
                if phrase in pipeline_text:
                    shared = True
                    break
            overlap = "yes" if shared else "no"

        print(f"{info.pageid:>6} | {info.title[:38]:38s} | {n_sec:>4} | {n_chunks:>6} | "
              f"{n_tables:>10} | {n_corpus:>13} | {overlap:>7}")

        if n_tables > 0 and sample_with_table is None:
            sample_with_table = (info, cleaned, chunks)

    if sample_with_table:
        info, cleaned, chunks = sample_with_table
        print("\n" + "=" * 100)
        print(f"Spot check (R1 table preservation) — pageid {info.pageid}: {info.title}")
        print("=" * 100)
        for sec in cleaned.sections:
            if "|---|" in sec.text:
                print(f"\n--- Section: {sec.heading or '(lead)'} ---")
                print(sec.text[:1200] + ("…" if len(sec.text) > 1200 else ""))
                break
    else:
        print("\n(no tables found in the first 10 pages — try a wider sample)")


if __name__ == "__main__":
    main()
