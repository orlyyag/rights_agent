"""One-time initial bilingual build: kz_pipeline_he + raw ru → kz_v2 → flip.

Why not ``scripts/sync.py he ru``: sync diffs against the stored manifest, and
the standalone RU crawl (``scripts/acquire.py ru``) already wrote it — so sync
would see ru changed=0 and never embed the Russian pages. This script reuses
the same blue-green machinery (copy-forward, embed, smoke, flip) but treats
the entire RU raw layer as fresh. Nothing is re-fetched from the wiki.

Run (from repo root):
    PYTHONPATH=.:src python scripts/build_bilingual.py [dest_collection]

Resumable — a re-run with the same dest skips chunks already embedded.
After this, routine updates go through ``scripts/sync.py he ru`` as usual.
To roll back: ``echo kz_pipeline_he > data/active_collection``.
"""
from __future__ import annotations

import sys
import time

import chromadb

import config
from ingest import acquire, chunk, clean, index
from ingest import sync as sync_mod


def main(dest: str) -> None:
    t0 = time.monotonic()
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    active = config.get_active_collection()
    src = client.get_collection(active)
    dst = index.get_or_create(dest, client=client)

    # he: real manifest-diff against upstream, so the new collection also picks
    # up any Hebrew pages that changed since the last build.
    he_diff = acquire.acquire("he")
    he_changed = {p.pageid for p in he_diff.to_fetch}
    skip = {("he", pid) for pid in he_changed | set(he_diff.deleted)}
    print(f"[he] changed={len(he_changed)} deleted={len(he_diff.deleted)}",
          flush=True)

    existing = set(dst.get(include=[])["ids"])
    if existing:
        print(f"Resuming into '{dest}' — {len(existing)} chunks already there.",
              flush=True)
    copied = sync_mod.copy_forward(src, dst, skip)
    print(f"Copied forward {copied} chunks from '{active}' (no re-embed).",
          flush=True)

    fresh = sync_mod.chunks_for_pages("he", he_changed) if he_changed else []
    pages = 0
    for raw in acquire.iter_raw("ru"):
        fresh.extend(chunk.chunk_doc(clean.clean(raw), source="pipeline"))
        pages += 1
        if pages % 500 == 0:
            print(f"  [ru] cleaned+chunked {pages} pages …", flush=True)
    print(f"[ru] {pages} raw pages → {len(fresh)} chunks total to embed",
          flush=True)

    todo = [c for c in fresh if c.id not in existing]
    if len(todo) < len(fresh):
        print(f"  {len(fresh) - len(todo)} already embedded — skipping.",
              flush=True)
    if todo:
        index.build_collection(todo, dest, collection=dst)

    # The bilingual collection must hold at least everything the he-only one
    # did; src.count() is a safe lower bound even with a few he deletions,
    # given the tens of thousands of ru chunks on top.
    if not sync_mod.smoke_ok(dst, min_count=src.count()):
        raise SystemExit(f"✗ Smoke check FAILED ({dst.count()} < {src.count()}) "
                         f"— pointer NOT flipped; '{active}' stays active.")

    # ANN-recall gate before the flip — a smoke check (count only) cannot catch
    # the query-dependent recall holes that the default HNSW build can produce
    # (this is exactly how kz_v2 shipped a hole). Never flip to a defective graph.
    if not sync_mod.recall_gate_ok(dst):
        raise SystemExit(f"✗ Recall gate FAILED — '{dest}' has ANN holes; "
                         f"pointer NOT flipped; '{active}' stays active.")

    config.set_active_collection(dest)
    mins = (time.monotonic() - t0) / 60
    print(f"\n✓ Done in {mins:.1f} min — active collection flipped → '{dest}'. "
          f"Rollback: echo {active} > data/active_collection", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "kz_v2")
