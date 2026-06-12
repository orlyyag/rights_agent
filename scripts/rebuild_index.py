"""One-off: rebuild the ACTIVE collection's HNSW graph (the kz_v2 incident).

Copies every chunk — ids, embeddings, documents, metadata — from the active
collection into ``kz_v{N+1}`` created with the explicit HNSW params in
``ingest.index`` (denser graph, deeper search), then runs the smoke check and
the brute-force ANN-recall gate before flipping the pointer. Zero re-embedding,
zero API cost beyond embedding the gate's golden questions.

    PYTHONPATH=.:src python scripts/rebuild_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import chromadb  # noqa: E402

import config  # noqa: E402
from ingest import index, sync  # noqa: E402


def main() -> int:
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    active = config.get_active_collection()
    src = client.get_collection(active)
    existing = [c.name for c in client.list_collections()]
    dest = sync.next_version_name(existing)

    print(f"Rebuilding '{active}' ({src.count()} chunks) → '{dest}' "
          f"with HNSW params {index.HNSW_PARAMS} …", flush=True)
    dst = index.get_or_create(dest, client=client)
    copied = sync.copy_forward(src, dst, skip=set())
    print(f"Copied {copied} chunks (embeddings verbatim, no re-embed).", flush=True)

    if not sync.smoke_ok(dst, min_count=src.count()):
        print(f"✗ Smoke FAILED — '{dest}' is incomplete; pointer NOT flipped.")
        return 1
    if not sync.recall_gate_ok(dst):
        print(f"✗ Recall gate FAILED — '{dest}' has ANN holes; pointer NOT flipped.")
        return 1

    config.set_active_collection(dest)
    print(f"✓ Active collection flipped → '{dest}'. "
          f"Rollback: echo {active} > data/active_collection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
