"""Build the pipeline index from the raw layer + flip the active pointer.

Reads ``data/raw/{lang}/*.json`` (populated by ``scripts/acquire.py``), cleans,
chunks, embeds, and upserts into ``kz_pipeline_{lang}``. Resumable — re-runs
skip chunks already in the collection (same idempotent upsert pattern as
``scripts/load_corpus.py``). On success, flips ``config.ACTIVE_POINTER`` so the
bot's next request reads from the new collection (R7 — no bot restart needed).

Run (from repo root):
    PYTHONPATH=.:src python scripts/build_pipeline.py he
    PYTHONPATH=.:src python scripts/build_pipeline.py ru

To roll back: ``echo kz_corpus_he > data/active_collection``.
"""
from __future__ import annotations

import argparse
import sys
import time

import config
from ingest import acquire, chunk, clean, index, sync


def main(lang: str, *, flip: bool = True) -> None:
    collection_name = f"kz_pipeline_{lang}"
    t0 = time.monotonic()

    # Stream the raw layer through clean → chunk. No reason to hold all pages in
    # memory at once — clean each, chunk, and append.
    print(f"Reading raw layer data/raw/{lang}/ …", flush=True)
    pages = 0
    chunks: list = []
    for raw in acquire.iter_raw(lang):
        cleaned = clean.clean(raw)
        chunks.extend(chunk.chunk_doc(cleaned, source="pipeline"))
        pages += 1
        if pages % 500 == 0:
            print(f"  cleaned+chunked {pages} pages → {len(chunks)} chunks so far",
                  flush=True)
    print(f"Total: {pages} pages → {len(chunks)} chunks "
          f"({(time.monotonic()-t0):.1f}s)", flush=True)

    if not chunks:
        raise SystemExit(f"No chunks produced — is data/raw/{lang}/ populated? "
                         f"Run scripts/acquire.py {lang} first.")

    # Resumable: skip ids already in the collection so a re-run after a 429/crash
    # only embeds what's missing.
    col = index.get_or_create(collection_name)
    existing = set(col.get(include=[])["ids"])
    remaining = [c for c in chunks if c.id not in existing]
    print(f"\nEmbedding → {collection_name}: {len(existing)} already there, "
          f"{len(remaining)} remaining", flush=True)
    if remaining:
        index.build_collection(remaining, collection_name, collection=col)

    if flip:
        # Same recall gate the sync path uses — a from-scratch build can ship an
        # ANN-defective graph just as a sync can (this is how the kz_v2 hole
        # shipped). Never flip the pointer to a graph that fails the gate.
        if not sync.recall_gate_ok(col):
            raise SystemExit(f"✗ Recall gate FAILED — '{collection_name}' has ANN "
                             f"holes; pointer NOT flipped. Rebuild before flipping.")
        config.set_active_collection(collection_name)
        print(f"\n✓ Active collection flipped to '{collection_name}' "
              f"(read per-request, R7 — bot picks it up on next message).",
              flush=True)
    else:
        print(f"\n✓ Built '{collection_name}' but did NOT flip the pointer. "
              f"Run `echo {collection_name} > data/active_collection` when ready.",
              flush=True)

    print(f"\nTotal wall time: {(time.monotonic()-t0)/60:.1f} min")


def cli() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("lang", choices=["he", "ru"])
    ap.add_argument("--no-flip", action="store_true",
                    help="Build the collection but don't flip the active pointer")
    args = ap.parse_args()
    main(args.lang, flip=not args.no_flip)


if __name__ == "__main__":
    sys.exit(cli())
