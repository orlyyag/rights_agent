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


class _FakeSeqCol:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def query(self, **kw):
        self.calls.append(kw)
        return self.results.pop(0)


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


def test_auto_language_drops_lang_filter(monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda texts, task_type: [[0.0, 0.0]])
    empty = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    col = _FakeCol(empty)
    retriever.retrieve("q", config.AUTO_LANG, collection=col)
    assert "where" not in col.captured


def test_same_language_empty_falls_back_to_unfiltered(monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda texts, task_type: [[0.0, 0.0]])
    monkeypatch.setattr(config, "SIMILARITY_FLOOR_BY_LANG", {"ru": 0.5})
    empty = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    hit = {
        "documents": [["hebrew chunk"]],
        "metadatas": [[_meta("he fallback")]],
        "distances": [[0.2]],
    }
    col = _FakeSeqCol([empty, hit])

    out = retriever.retrieve("русский вопрос", "ru", collection=col)

    assert col.calls[0]["where"] == {"lang": "ru"}
    assert "where" not in col.calls[1]
    assert [c.text for c in out] == ["hebrew chunk"]


class _FakeProbedCol:
    """A fake that records both metadata probes (get) and vector queries."""

    def __init__(self, present_langs: set[str], query_result: dict):
        self._present = set(present_langs)
        self._query_result = query_result
        self.get_calls: list[dict] = []
        self.query_calls: list[dict] = []

    def get(self, **kw):
        self.get_calls.append(kw)
        lang = (kw.get("where") or {}).get("lang")
        if lang in self._present:
            return {"ids": ["x"], "metadatas": [_meta()]}
        return {"ids": [], "metadatas": []}

    def query(self, **kw):
        self.query_calls.append(kw)
        return self._query_result


def test_lang_present_caches_probes_per_collection(monkeypatch):
    monkeypatch.setattr(retriever, "_lang_availability", {})
    col = _FakeProbedCol(present_langs={"he"}, query_result={
        "documents": [[]], "metadatas": [[]], "distances": [[]],
    })

    assert retriever._lang_present("kz_v1", col, "he") is True
    assert retriever._lang_present("kz_v1", col, "ru") is False
    # Second call must hit the cache (no new probe).
    assert retriever._lang_present("kz_v1", col, "ru") is False
    ru_probes = [c for c in col.get_calls if c["where"] == {"lang": "ru"}]
    assert len(ru_probes) == 1


def test_lang_present_fails_open_when_probe_raises(monkeypatch):
    """A probe failure must never silently kill retrieval."""
    monkeypatch.setattr(retriever, "_lang_availability", {})

    class _BrokenCol:
        def get(self, **_kw):
            raise RuntimeError("chroma down")

    assert retriever._lang_present("any", _BrokenCol(), "ru") is True


def test_production_path_skips_lang_filter_when_lang_is_absent(monkeypatch):
    """When the active collection has no chunks for the requested lang, we
    skip the filter entirely — no wasted vector query that would return [].

    This exercises the ``collection is None`` branch by injecting a stub
    ``_get_collection``."""
    monkeypatch.setattr(retriever, "_lang_availability", {})
    monkeypatch.setattr(llm, "embed", lambda texts, task_type: [[0.0, 0.0]])
    monkeypatch.setattr(config, "get_active_collection", lambda: "kz_he_only")
    col = _FakeProbedCol(present_langs={"he"}, query_result={
        "documents": [["hebrew chunk"]],
        "metadatas": [[_meta("he")]],
        "distances": [[0.1]],
    })
    monkeypatch.setattr(retriever, "_get_collection", lambda name=None: col)
    monkeypatch.setattr(config, "SIMILARITY_FLOOR_BY_LANG", {"ru": 0.3})

    out = retriever.retrieve("русский вопрос", "ru")

    # The probe ran once, decided ru is absent, so we issued exactly ONE
    # vector query — unfiltered — instead of querying-then-retrying.
    ru_probes = [c for c in col.get_calls if c["where"] == {"lang": "ru"}]
    assert len(ru_probes) == 1
    assert len(col.query_calls) == 1
    assert "where" not in col.query_calls[0]
    assert [c.text for c in out] == ["hebrew chunk"]


def test_production_path_still_filters_when_lang_is_present(monkeypatch):
    monkeypatch.setattr(retriever, "_lang_availability", {})
    monkeypatch.setattr(llm, "embed", lambda texts, task_type: [[0.0, 0.0]])
    monkeypatch.setattr(config, "get_active_collection", lambda: "kz_bilingual")
    col = _FakeProbedCol(present_langs={"he", "ru"}, query_result={
        "documents": [["ru chunk"]],
        "metadatas": [[_meta("ru")]],
        "distances": [[0.2]],
    })
    monkeypatch.setattr(retriever, "_get_collection", lambda name=None: col)
    monkeypatch.setattr(config, "SIMILARITY_FLOOR_BY_LANG", {"ru": 0.3})

    out = retriever.retrieve("вопрос", "ru")

    assert len(col.query_calls) == 1
    assert col.query_calls[0]["where"] == {"lang": "ru"}
    assert [c.text for c in out] == ["ru chunk"]
