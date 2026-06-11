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


def test_auto_no_docs_localizes_refusal_with_llm():
    a = answer.answer(
        "What is the weather today?",
        "auto",
        retrieve_fn=lambda q, l: [],
        generate_fn=lambda p, system=None: "[REFUSAL] I could not find that in Kol Zchut.",
    )
    assert a.refused is True
    assert a.text == "I could not find that in Kol Zchut."
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


def test_refusal_marker_strips_citations_for_any_language():
    chunks = [_rc("A", "https://a")]
    a = answer.answer("?", "auto", retrieve_fn=lambda q, l: chunks,
                      generate_fn=lambda p, system=None: "[REFUSAL] No hay información en las fuentes.")
    assert a.refused is True
    assert a.text == "No hay información en las fuentes."
    assert a.citations == []


def test_grounded_answer_with_deduped_citations():
    chunks = [_rc("A", "https://a"), _rc("A", "https://a"), _rc("B", "https://b")]
    a = answer.answer("q", "he", retrieve_fn=lambda q, l: chunks,
                      generate_fn=lambda p, system=None: "grounded answer")
    assert a.refused is False
    assert a.text == "grounded answer"
    assert a.lang == "he"
    assert a.disclaimer == prompts.disclaimer("he")
    assert [c.url for c in a.citations] == ["https://a", "https://b"]  # deduped, order kept


def test_auto_answer_extracts_disclaimer_tag_into_disclaimer_field():
    """Auto mode: parse the [DISCLAIMER] tag out of the body so the renderer
    appends it once, and the body itself stays clean."""
    chunks = [_rc("A", "https://a")]
    body = (
        "**Rights:** general info about your situation.\n"
        "[DISCLAIMER]Esta es información general de Kol Zchut y no constituye asesoramiento legal.[/DISCLAIMER]"
    )
    a = answer.answer("?", "auto", retrieve_fn=lambda q, l: chunks,
                      generate_fn=lambda p, system=None: body)
    assert a.refused is False
    assert "[DISCLAIMER]" not in a.text and "[/DISCLAIMER]" not in a.text
    assert a.text.startswith("**Rights:**")
    assert "Kol Zchut" in a.disclaimer
    assert "asesoramiento legal" in a.disclaimer


def test_auto_answer_falls_back_to_english_disclaimer_when_tag_missing():
    """If the model forgets the tags, §7 still holds: we ship a real disclaimer."""
    chunks = [_rc("A", "https://a")]
    a = answer.answer("?", "auto", retrieve_fn=lambda q, l: chunks,
                      generate_fn=lambda p, system=None: "answer without the tag")
    assert a.refused is False
    assert a.text == "answer without the tag"
    assert a.disclaimer == prompts.disclaimer("auto")
    assert "Kol Zchut" in a.disclaimer and "not legal advice" in a.disclaimer


def test_auto_answer_falls_back_when_disclaimer_tag_is_empty():
    chunks = [_rc("A", "https://a")]
    body = "the answer.\n[DISCLAIMER]   [/DISCLAIMER]"
    a = answer.answer("?", "auto", retrieve_fn=lambda q, l: chunks,
                      generate_fn=lambda p, system=None: body)
    assert "[DISCLAIMER]" not in a.text
    assert a.disclaimer == prompts.disclaimer("auto")
