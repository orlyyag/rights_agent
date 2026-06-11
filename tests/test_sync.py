"""Blue-green incremental sync (Brick 5) — LLM-free via fakes."""
from __future__ import annotations

import config
from ingest import acquire, sync
from ingest.mediawiki import PageInfo


# ── Fakes ────────────────────────────────────────────────────────────────────
class _FakeCol:
    def __init__(self, name, rows=None):
        self.name = name
        self.rows = {r["id"]: r for r in (rows or [])}  # id → row

    def get(self, *, limit=None, offset=0, include=None):
        ids = sorted(self.rows)[offset: offset + (limit or len(self.rows))]
        return {
            "ids": ids,
            "embeddings": [self.rows[i]["embedding"] for i in ids],
            "documents": [self.rows[i]["document"] for i in ids],
            "metadatas": [self.rows[i]["metadata"] for i in ids],
        }

    def upsert(self, *, ids, embeddings, documents, metadatas):
        for i, e, d, m in zip(ids, embeddings, documents, metadatas):
            self.rows[i] = {"id": i, "embedding": e, "document": d, "metadata": m}

    def count(self):
        return len(self.rows)


class _FakeClient:
    def __init__(self, cols):
        self.cols = {c.name: c for c in cols}

    def list_collections(self):
        return list(self.cols.values())

    def get_collection(self, name):
        return self.cols[name]

    def get_or_create_collection(self, name, metadata=None):
        if name not in self.cols:
            self.cols[name] = _FakeCol(name)
        return self.cols[name]


def _row(id_, lang, pageid, doc="text"):
    return {"id": id_, "embedding": [0.1, 0.2], "document": doc,
            "metadata": {"lang": lang, "pageid": pageid, "title": "t",
                         "url": "https://kz/x", "section": "", "lastrevid": 1,
                         "source": "pipeline"}}


def _info(pageid, lastrevid=2):
    return PageInfo(pageid=pageid, title=f"p{pageid}", url=f"https://kz/{pageid}",
                    lastrevid=lastrevid)


def _diff(changed=(), deleted=()):
    return acquire.Diff(added=[], changed=[_info(p) for p in changed],
                        deleted=list(deleted))


# ── next_version_name ────────────────────────────────────────────────────────
def test_next_version_name_increments_highest():
    assert sync.next_version_name(["kz_v1", "kz_v3", "kz_corpus_he"]) == "kz_v4"


def test_next_version_name_defaults_to_v2():
    assert sync.next_version_name(["kz_pipeline_he"]) == "kz_v2"


# ── copy_forward ─────────────────────────────────────────────────────────────
def test_copy_forward_skips_changed_and_deleted_pages():
    src = _FakeCol("old", [_row("a", "he", 1), _row("b", "he", 2), _row("c", "ru", 1)])
    dst = _FakeCol("new")
    copied = sync.copy_forward(src, dst, skip={("he", 2)}, batch=2)
    assert copied == 2
    assert set(dst.rows) == {"a", "c"}          # he/2 dropped; ru/1 same pageid kept


def test_copy_forward_preserves_embeddings_verbatim():
    src = _FakeCol("old", [_row("a", "he", 1)])
    dst = _FakeCol("new")
    sync.copy_forward(src, dst, skip=set())
    assert dst.rows["a"]["embedding"] == [0.1, 0.2]   # no re-embed


# ── sync orchestration ───────────────────────────────────────────────────────
def _patch_pointer(monkeypatch, tmp_path, active="kz_v1"):
    ptr = tmp_path / "active_collection"
    ptr.write_text(active + "\n", encoding="utf-8")
    monkeypatch.setattr(config, "ACTIVE_POINTER", ptr)


def test_sync_noop_when_nothing_changed(monkeypatch, tmp_path):
    _patch_pointer(monkeypatch, tmp_path)
    res = sync.sync(("he",), client=_FakeClient([]), acquire_fn=lambda l: _diff(),
                    log=lambda *a: None)
    assert res.noop is True
    assert res.flipped is False
    assert config.get_active_collection() == "kz_v1"


def test_sync_builds_new_collection_and_flips(monkeypatch, tmp_path):
    _patch_pointer(monkeypatch, tmp_path, active="kz_v1")
    old = _FakeCol("kz_v1", [_row("a", "he", 1), _row("b", "he", 2)])
    client = _FakeClient([old])
    monkeypatch.setattr(sync, "chunks_for_pages", lambda lang, pageids: [])

    res = sync.sync(("he",), client=client, acquire_fn=lambda l: _diff(changed=[2]),
                    log=lambda *a: None)

    assert res.new_collection == "kz_v2"
    assert res.copied == 1                       # page 1 copied, page 2 skipped
    assert set(client.cols["kz_v2"].rows) == {"a"}
    assert res.flipped is True
    assert config.get_active_collection() == "kz_v2"


def test_sync_embeds_delta_chunks(monkeypatch, tmp_path):
    _patch_pointer(monkeypatch, tmp_path, active="kz_v1")
    old = _FakeCol("kz_v1", [_row("a", "he", 1)])
    client = _FakeClient([old])
    from schema import Chunk, ChunkMeta
    fresh = [Chunk(id="new1", text="updated text",
                   meta=ChunkMeta(pageid=2, title="t", url="https://kz/2", lang="he",
                                  section="", lastrevid=2, source="pipeline"))]
    monkeypatch.setattr(sync, "chunks_for_pages",
                        lambda lang, pageids: fresh if pageids == {2} else [])
    captured = {}
    def fake_build(chunks, name, collection=None):
        captured["chunks"] = chunks
        collection.upsert(ids=[c.id for c in chunks],
                          embeddings=[[0.5, 0.5]] * len(chunks),
                          documents=[c.text for c in chunks],
                          metadatas=[c.meta.to_metadata() for c in chunks])
        return collection
    monkeypatch.setattr(sync.index, "build_collection", fake_build)

    res = sync.sync(("he",), client=client, acquire_fn=lambda l: _diff(changed=[2]),
                    log=lambda *a: None)

    assert res.embedded == 1
    assert captured["chunks"] == fresh
    assert set(client.cols["kz_v2"].rows) == {"a", "new1"}
    assert config.get_active_collection() == "kz_v2"


def test_sync_deleted_pages_are_dropped(monkeypatch, tmp_path):
    _patch_pointer(monkeypatch, tmp_path, active="kz_v1")
    old = _FakeCol("kz_v1", [_row("a", "he", 1), _row("b", "he", 9)])
    client = _FakeClient([old])
    monkeypatch.setattr(sync, "chunks_for_pages", lambda lang, pageids: [])

    res = sync.sync(("he",), client=client,
                    acquire_fn=lambda l: _diff(changed=[1], deleted=[9]),
                    log=lambda *a: None)

    assert set(client.cols["kz_v2"].rows) == set()   # 1 changed (re-embed), 9 deleted
    assert res.deleted == {"he": 1}


def test_sync_smoke_failure_blocks_flip(monkeypatch, tmp_path):
    """An empty/broken new collection must never become active."""
    _patch_pointer(monkeypatch, tmp_path, active="kz_v1")
    old = _FakeCol("kz_v1", [_row("a", "he", 1)])
    client = _FakeClient([old])
    monkeypatch.setattr(sync, "chunks_for_pages", lambda lang, pageids: [])
    # every chunk is "changed" → nothing copies forward and nothing embeds → empty dst
    res = sync.sync(("he",), client=client, acquire_fn=lambda l: _diff(changed=[1]),
                    log=lambda *a: None)
    assert res.flipped is False
    assert config.get_active_collection() == "kz_v1"


def test_sync_no_flip_flag(monkeypatch, tmp_path):
    _patch_pointer(monkeypatch, tmp_path, active="kz_v1")
    old = _FakeCol("kz_v1", [_row("a", "he", 1), _row("b", "he", 2)])
    client = _FakeClient([old])
    monkeypatch.setattr(sync, "chunks_for_pages", lambda lang, pageids: [])

    res = sync.sync(("he",), client=client, acquire_fn=lambda l: _diff(changed=[2]),
                    flip=False, log=lambda *a: None)

    assert res.flipped is False
    assert config.get_active_collection() == "kz_v1"   # pointer untouched
    assert "kz_v2" in client.cols                       # but the build happened
