"""Retriever logic (lang filter, lenient floor, scoring) — LLM-free via fakes."""
from __future__ import annotations

import pytest

import config
from rag import llm, retriever


class _FakeCol:
    def __init__(self, result):
        self.result = result
        self.captured = {}

    def query(self, **kw):
        self.captured = kw
        return self.result


def _meta(title="t"):
    return {"pageid": 1, "title": title, "url": "https://kz/x", "lang": "he",
            "section": "", "lastrevid": 0, "source": "corpus"}


def test_retrieve_passes_lang_filter_and_drops_below_floor(monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda texts, task_type: [[0.1, 0.2]])
    monkeypatch.setattr(config, "SIMILARITY_FLOOR_BY_LANG", {"he": 0.5})
    result = {
        "documents": [["good", "weak"]],
        "metadatas": [[_meta("good"), _meta("weak")]],
        "distances": [[0.2, 0.9]],   # similarities 0.8 (keep), 0.1 (drop)
    }
    col = _FakeCol(result)

    out = retriever.retrieve("q", "he", collection=col)

    assert col.captured["where"] == {"lang": "he"}
    assert len(out) == 1
    assert out[0].text == "good"
    assert out[0].score == pytest.approx(0.8)


def test_retrieve_uses_query_task_type(monkeypatch):
    seen = {}
    def fake_embed(texts, task_type):
        seen["task"] = task_type
        return [[0.0, 0.0]]
    monkeypatch.setattr(llm, "embed", fake_embed)
    empty = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    retriever.retrieve("q", "he", collection=_FakeCol(empty))
    assert seen["task"] == config.EMBED_TASK_QUERY
