"""Corpus loader + index build (batching, upsert, DOCUMENT task) — LLM-free via fakes."""
from __future__ import annotations

import json

import config
from ingest import corpus, index
from rag import llm
from schema import Chunk, ChunkMeta, chunk_id


def test_corpus_record_mapping():
    rec = {"doc_id": "123", "title": "דמי לידה", "link": "https://kz/x", "content": "גוף"}
    ch = corpus.corpus_record_to_chunk(rec, 0)
    assert ch.meta.source == "corpus" and ch.meta.lang == "he"
    assert ch.meta.pageid == 123 and ch.meta.url == "https://kz/x"
    assert ch.text.startswith("דמי לידה")
    assert ch.id == "corpus:he:123:0"


def test_corpus_nonnumeric_docid_is_stable_int():
    rec = {"doc_id": "some_slug", "title": "t", "link": "u", "content": "c"}
    a = corpus.corpus_record_to_chunk(rec, 0)
    b = corpus.corpus_record_to_chunk(rec, 0)
    assert isinstance(a.meta.pageid, int) and a.meta.pageid == b.meta.pageid


def test_load_corpus_accepts_list_and_dict(tmp_path):
    rec = {"doc_id": 1, "title": "a", "link": "u1", "content": "c1"}
    lst = tmp_path / "list.json"
    lst.write_text(json.dumps([rec]), encoding="utf-8")
    assert len(corpus.load_corpus_chunks(lst)) == 1

    dct = tmp_path / "dict.json"
    dct.write_text(json.dumps({"1": rec}), encoding="utf-8")
    assert len(corpus.load_corpus_chunks(dct)) == 1


def test_load_corpus_column_oriented_with_scalar_column(tmp_path):
    """Pandas df.to_json default with a uniform column (``license``) written as a
    scalar — the actual on-disk shape of the real Webiks corpus."""
    column = {
        "doc_id":  {"0": 11, "1": 22},
        "title":   {"0": "A", "1": "B"},
        "link":    {"0": "ua", "1": "ub"},
        "content": {"0": "a-body", "1": "b-body"},
        "license": "Creative Commons BY-NC-SA 2.5",  # scalar — broadcast across rows
    }
    p = tmp_path / "cols.json"
    p.write_text(json.dumps(column), encoding="utf-8")
    chunks = corpus.load_corpus_chunks(p)
    assert len(chunks) == 2
    assert chunks[0].meta.pageid == 11 and chunks[0].meta.title == "A"
    assert chunks[1].meta.url == "ub" and "b-body" in chunks[1].text


class _FakeUpsertCol:
    def __init__(self):
        self.calls = []

    def upsert(self, **kw):
        self.calls.append(kw)


def _chunk(i):
    meta = ChunkMeta(pageid=i, title=f"t{i}", url=f"u{i}", lang="he",
                     section="", lastrevid=0, source="pipeline")
    return Chunk(id=chunk_id("pipeline", "he", i, 0), text=f"body {i}", meta=meta)


def test_build_collection_batches_and_upserts(monkeypatch):
    seen = {}
    def fake_embed(texts, task_type):
        seen["task"] = task_type
        return [[0.0] for _ in texts]
    monkeypatch.setattr(llm, "embed", fake_embed)

    col = _FakeUpsertCol()
    index.build_collection([_chunk(i) for i in range(5)], "kz_v2",
                           collection=col, batch_size=2)

    assert len(col.calls) == 3                      # 2 + 2 + 1
    all_ids = [i for c in col.calls for i in c["ids"]]
    assert len(all_ids) == 5 and len(set(all_ids)) == 5
    assert seen["task"] == config.EMBED_TASK_DOCUMENT  # chunks embed as DOCUMENT (Q1)
