"""Linear Tier-0 RAG path: refuse-if-empty, grounded answer, deduped citations."""
from __future__ import annotations

from rag import answer, prompts
from schema import ChunkMeta, RetrievedChunk


def _rc(title, url):
    meta = ChunkMeta(pageid=1, title=title, url=url, lang="he",
                     section="", lastrevid=0, source="corpus")
    return RetrievedChunk(text="body", meta=meta, score=0.9)


def test_refuses_when_no_docs():
    a = answer.answer("q", "ru", retrieve_fn=lambda q, l: [])
    assert a.refused is True
    assert a.text == prompts.refusal("ru")
    assert a.citations == [] and a.disclaimer == ""


def test_refuses_when_generation_blank():
    a = answer.answer("q", "he",
                      retrieve_fn=lambda q, l: [_rc("T", "https://a")],
                      generate_fn=lambda p, system=None: "   ")
    assert a.refused is True


def test_template_refusal_strips_citations_and_disclaimer():
    """When the model returns the refusal template, drop citations + disclaimer."""
    chunks = [_rc("A", "https://a")]
    refusal_text = "בהסתמך על המקורות שסופקו, אין בטקסטים מידע שעונה על השאלה לגבי מזג האוויר."
    a = answer.answer("?", "he", retrieve_fn=lambda q, l: chunks,
                      generate_fn=lambda p, system=None: refusal_text)
    assert a.refused is True
    assert a.text == refusal_text
    assert a.citations == []
    assert a.disclaimer == ""


def test_template_refusal_russian():
    chunks = [_rc("A", "https://a")]
    ru_refusal = "В предоставленных источниках нет информации, отвечающей на вопрос о погоде."
    a = answer.answer("?", "ru", retrieve_fn=lambda q, l: chunks,
                      generate_fn=lambda p, system=None: ru_refusal)
    assert a.refused is True and a.citations == []


def test_grounded_answer_with_deduped_citations():
    chunks = [_rc("A", "https://a"), _rc("A", "https://a"), _rc("B", "https://b")]
    a = answer.answer("q", "he", retrieve_fn=lambda q, l: chunks,
                      generate_fn=lambda p, system=None: "grounded answer")
    assert a.refused is False
    assert a.text == "grounded answer"
    assert a.lang == "he"
    assert a.disclaimer == prompts.disclaimer("he")
    assert [c.url for c in a.citations] == ["https://a", "https://b"]  # deduped, order kept
