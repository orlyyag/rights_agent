"""Citation language policy — ru questions get ru links, he/auto get he links.
LLM/network-free: ``_live_langlinks`` is monkeypatched."""
from __future__ import annotations

from rag import answer, citations
from schema import ChunkMeta, RetrievedChunk

RU_TITLE = "Пособие при рождении ребёнка"


def _meta(lang="he", pageid=466, title="מענק לידה",
          url="https://www.kolzchut.org.il/he/%D7%9E%D7%A2%D7%A0%D7%A7"):
    return ChunkMeta(pageid=pageid, title=title, url=url, lang=lang,
                     section="", lastrevid=1, source="pipeline")


def _rc(meta):
    return RetrievedChunk(text="body", meta=meta, score=0.9)


def _fresh_cache(monkeypatch):
    monkeypatch.setattr(citations, "_cache", {})


def test_desired_citation_lang():
    assert citations.desired_citation_lang("ru") == "ru"
    assert citations.desired_citation_lang("he") == "he"
    assert citations.desired_citation_lang("auto") == "he"
    assert citations.desired_citation_lang("xx") == "he"


def test_localize_same_language_makes_no_lookup(monkeypatch):
    _fresh_cache(monkeypatch)
    def boom(meta):
        raise AssertionError("langlinks must not be called for same-language")
    monkeypatch.setattr(citations, "_live_langlinks", boom)
    m = _meta(lang="he")
    assert citations.localize(m, "he") == (m.title, m.url)


def test_localize_maps_hebrew_page_to_russian(monkeypatch):
    _fresh_cache(monkeypatch)
    monkeypatch.setattr(citations, "_live_langlinks", lambda meta: {"ru": RU_TITLE})
    title, url = citations.localize(_meta(lang="he"), "ru")
    assert title == RU_TITLE
    assert url.startswith("https://www.kolzchut.org.il/ru/")
    assert " " not in url            # spaces become underscores, then quoted


def test_localize_no_translation_keeps_original(monkeypatch):
    _fresh_cache(monkeypatch)
    monkeypatch.setattr(citations, "_live_langlinks", lambda meta: {})
    m = _meta(lang="he")
    assert citations.localize(m, "ru") == (m.title, m.url)


def test_localize_api_failure_keeps_original_and_is_not_cached(monkeypatch):
    _fresh_cache(monkeypatch)
    calls = {"n": 0}
    def flaky(meta):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("WAF hiccup")
        return {"ru": RU_TITLE}
    monkeypatch.setattr(citations, "_live_langlinks", flaky)
    m = _meta(lang="he")
    assert citations.localize(m, "ru") == (m.title, m.url)   # failure → original
    assert citations.localize(m, "ru")[0] == RU_TITLE        # retry succeeds


def test_localize_caches_successful_lookups(monkeypatch):
    _fresh_cache(monkeypatch)
    calls = {"n": 0}
    def counting(meta):
        calls["n"] += 1
        return {"ru": RU_TITLE}
    monkeypatch.setattr(citations, "_live_langlinks", counting)
    m = _meta(lang="he")
    citations.localize(m, "ru")
    citations.localize(m, "ru")
    assert calls["n"] == 1


def test_localize_caches_missing_translation(monkeypatch):
    _fresh_cache(monkeypatch)
    calls = {"n": 0}
    def counting(meta):
        calls["n"] += 1
        return {}
    monkeypatch.setattr(citations, "_live_langlinks", counting)
    m = _meta(lang="he")
    citations.localize(m, "ru")
    citations.localize(m, "ru")
    assert calls["n"] == 1           # "no translation" is cached too


# ── answer._citations integration (policy end-to-end) ────────────────────────
def test_russian_question_gets_russian_links_for_hebrew_chunks(monkeypatch):
    _fresh_cache(monkeypatch)
    monkeypatch.setattr(citations, "_live_langlinks", lambda meta: {"ru": RU_TITLE})
    out = answer._citations([_rc(_meta(lang="he"))], "ru")
    assert len(out) == 1
    assert out[0].title == RU_TITLE
    assert "/ru/" in out[0].url


def test_russian_question_keeps_hebrew_link_when_no_translation(monkeypatch):
    """Attribution is never dropped — a he link beats no link (license + R6)."""
    _fresh_cache(monkeypatch)
    monkeypatch.setattr(citations, "_live_langlinks", lambda meta: {})
    out = answer._citations([_rc(_meta(lang="he"))], "ru")
    assert len(out) == 1
    assert "/he/" in out[0].url


def test_auto_question_maps_russian_chunk_to_hebrew_link(monkeypatch):
    _fresh_cache(monkeypatch)
    monkeypatch.setattr(citations, "_live_langlinks", lambda meta: {"he": "מענק לידה"})
    ru_chunk = _rc(_meta(lang="ru", pageid=777, title=RU_TITLE,
                         url="https://www.kolzchut.org.il/ru/X"))
    out = answer._citations([ru_chunk], "auto")
    assert out[0].title == "מענק לידה"
    assert "/he/" in out[0].url


def test_citations_dedup_across_languages(monkeypatch):
    """The he and ru chunks of the same underlying page collapse to ONE citation
    once both localize to the same target URL (fixes the redundant-slot corner)."""
    _fresh_cache(monkeypatch)
    monkeypatch.setattr(citations, "_live_langlinks", lambda meta: {"ru": RU_TITLE})
    ru_url = citations._title_to_url(RU_TITLE, "ru")
    he_chunk = _rc(_meta(lang="he", pageid=466))
    ru_chunk = _rc(_meta(lang="ru", pageid=777, title=RU_TITLE, url=ru_url))
    out = answer._citations([he_chunk, ru_chunk], "ru")
    assert len(out) == 1
    assert out[0].url == ru_url


def test_hebrew_question_with_hebrew_chunks_is_untouched(monkeypatch):
    _fresh_cache(monkeypatch)
    def boom(meta):
        raise AssertionError("no lookup expected")
    monkeypatch.setattr(citations, "_live_langlinks", boom)
    m = _meta(lang="he")
    out = answer._citations([_rc(m)], "he")
    assert out[0].url == m.url
