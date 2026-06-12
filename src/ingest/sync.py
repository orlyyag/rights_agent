"""Blue-green incremental sync (Brick 5, §0 #4, §5.3, R7).

One cycle = acquire (manifest-diff) → build ``kz_v{N+1}`` → smoke → flip pointer:

1. ``acquire(lang)`` fetches added/changed pages into the raw layer and returns
   the diff. No changes anywhere → no-op, the active collection stays.
2. The new collection is built **incrementally**: every chunk of the active
   collection is copied forward verbatim — ids, embeddings, documents, metadata —
   EXCEPT chunks of changed/deleted pages. No re-embedding of unchanged content,
   so a typical sync costs cents, not the ~$2.40 full build.
3. Only the changed pages run clean → chunk → embed into the new collection.
4. A smoke check + an ANN-recall gate guard the flip; the previous collection
   is retained so rollback is one line: ``echo <old-name> > data/active_collection``.

The bot reads the pointer per-request (R7), so the flip needs no restart.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import config
from ingest import acquire, chunk, clean, index, recall_gate
from rag import llm

_VERSION_RE = re.compile(rf"^{re.escape(config.COLLECTION_PREFIX)}(\d+)$")
_COPY_BATCH = 500


@dataclass
class SyncResult:
    """Summary of one sync cycle (printed by the CLI, asserted in tests)."""

    changed: dict[str, int] = field(default_factory=dict)   # lang → fetched pages
    deleted: dict[str, int] = field(default_factory=dict)   # lang → removed pages
    old_collection: str = ""
    new_collection: str = ""        # "" → no-op (nothing changed)
    copied: int = 0                 # chunks copied forward without re-embedding
    embedded: int = 0               # fresh chunks embedded from changed pages
    flipped: bool = False

    @property
    def noop(self) -> bool:
        return not self.new_collection


def next_version_name(existing: list[str]) -> str:
    """``kz_v{N+1}`` where N is the highest existing version (min result: kz_v2)."""
    versions = [int(m.group(1)) for name in existing
                if (m := _VERSION_RE.match(name))]
    return f"{config.COLLECTION_PREFIX}{max(versions, default=1) + 1}"


def copy_forward(src, dst, skip: set[tuple[str, int]], *,
                 batch: int = _COPY_BATCH) -> int:
    """Copy all chunks from ``src`` to ``dst`` except those whose
    ``(lang, pageid)`` is in ``skip``. Embeddings move verbatim — zero API cost."""
    copied = 0
    offset = 0
    while True:
        page = src.get(limit=batch, offset=offset,
                       include=["embeddings", "documents", "metadatas"])
        ids = page.get("ids") or []
        if not len(ids):
            return copied
        offset += len(ids)
        keep = [i for i, meta in enumerate(page["metadatas"])
                if (meta.get("lang"), meta.get("pageid")) not in skip]
        if keep:
            dst.upsert(
                ids=[ids[i] for i in keep],
                embeddings=[page["embeddings"][i] for i in keep],
                documents=[page["documents"][i] for i in keep],
                metadatas=[page["metadatas"][i] for i in keep],
            )
            copied += len(keep)


def chunks_for_pages(lang: str, pageids: set[int]) -> list:
    """clean → chunk for just the given raw pages (same path as build_pipeline)."""
    out: list = []
    for raw in acquire.iter_raw(lang):
        if raw["pageid"] in pageids:
            out.extend(chunk.chunk_doc(clean.clean(raw), source="pipeline"))
    return out


def smoke_ok(dst, *, min_count: int = 1) -> bool:
    """Cheap pre-flip guard: the new collection must not be empty/half-built."""
    try:
        return dst.count() >= min_count
    except Exception:  # noqa: BLE001 — a broken collection must never get flipped to
        return False


_GOLDEN_FILES = ("eval/golden_he.jsonl", "eval/golden_ru.jsonl")


def _golden_questions() -> list[str]:
    out: list[str] = []
    for path in _GOLDEN_FILES:
        p = Path(path)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("category") == "in_scope":
                out.append(item["question"])
    return out


def recall_gate_ok(dst, *, log=print, check_fn=None) -> bool:
    """ANN-vs-true-NN gate (the kz_v2 incident): a graph with recall holes must
    never get flipped to. Fails CLOSED on detected holes; fails OPEN (with a
    loud log line) on infrastructure errors — an embed-API hiccup is not
    evidence of a bad graph. ``check_fn`` is injectable for tests."""
    try:
        questions = _golden_questions()
        if not questions:
            log("Recall gate: no golden questions found — SKIPPED.")
            return True
        vecs = llm.embed(questions, task_type=config.EMBED_TASK_QUERY)
        rep = (check_fn or recall_gate.check)(dst, vecs)
        if rep.ok:
            log(f"Recall gate: {rep.queries} queries, ANN == true-NN on all ✓")
            return True
        worst = max(rep.failed, key=lambda f: f[-1])
        log(f"✗ Recall gate FAILED on {len(rep.failed)}/{rep.queries} queries "
            f"(worst hole: gap {worst[-1]:.4f}; true top-1 {worst[1]:.4f}, "
            f"ANN top-1 {worst[2]:.4f}).")
        return False
    except Exception as e:  # noqa: BLE001 — infra error ≠ recall hole
        log(f"Recall gate errored ({e!r}) — flip proceeds; check manually.")
        return True


def sync(langs: tuple[str, ...] = ("he",), *, client=None,
         acquire_fn=acquire.acquire, flip: bool = True,
         log=print) -> SyncResult:
    """Run one full sync cycle. ``client``/``acquire_fn`` are injectable for tests."""
    res = SyncResult(old_collection=config.get_active_collection())

    skip: set[tuple[str, int]] = set()
    delta_pages: dict[str, set[int]] = {}
    for lang in langs:
        diff = acquire_fn(lang)
        changed_ids = {p.pageid for p in diff.to_fetch}
        delta_pages[lang] = changed_ids
        res.changed[lang] = len(changed_ids)
        res.deleted[lang] = len(diff.deleted)
        skip |= {(lang, pid) for pid in changed_ids}
        skip |= {(lang, pid) for pid in diff.deleted}
        log(f"[{lang}] changed={len(changed_ids)} deleted={len(diff.deleted)}")

    if not skip:
        log("No changes — active collection stays "
            f"'{res.old_collection}'.")
        return res

    if client is None:
        import chromadb
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    existing = [c.name for c in client.list_collections()]
    res.new_collection = next_version_name(existing)
    src = client.get_collection(res.old_collection)
    dst = index.get_or_create(res.new_collection, client=client)
    log(f"Building '{res.new_collection}' from '{res.old_collection}' …")

    res.copied = copy_forward(src, dst, skip)
    log(f"Copied forward {res.copied} unchanged chunks (no re-embed).")

    for lang, pageids in delta_pages.items():
        if not pageids:
            continue
        fresh = chunks_for_pages(lang, pageids)
        if fresh:
            index.build_collection(fresh, res.new_collection, collection=dst)
            res.embedded += len(fresh)
    log(f"Embedded {res.embedded} fresh chunks from changed pages.")

    if not smoke_ok(dst):
        log(f"✗ Smoke check FAILED — pointer NOT flipped; "
            f"'{res.old_collection}' stays active.")
        return res

    if not recall_gate_ok(dst, log=log):
        log(f"✗ Pointer NOT flipped; '{res.old_collection}' stays active. "
            f"The new graph has ANN recall holes — rebuild before flipping.")
        return res

    if flip:
        config.set_active_collection(res.new_collection)
        res.flipped = True
        log(f"✓ Active collection flipped → '{res.new_collection}' "
            f"(per-request pointer, no restart needed). "
            f"Rollback: echo {res.old_collection} > data/active_collection")
    else:
        log(f"Built '{res.new_collection}' without flipping (--no-flip).")
    return res
