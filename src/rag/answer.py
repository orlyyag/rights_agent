"""Linear Tier-0 RAG: retrieve → generate (grounded) → cite → refuse-if-empty.

This is the POC-core path (§0 Tier-0): no agent loop yet. Tier-1 upgrades it to the
agentic ``graph.py`` (grade_docs + bounded re-retrieve). Provider-agnostic and
Telegram-free; returns an :class:`Answer` the bot renders to HTML.
"""
from __future__ import annotations

import config
from rag import llm, prompts, retriever
from schema import Answer, Citation, RetrievedChunk


def answer(question: str, lang: str, *, retrieve_fn=None, generate_fn=None) -> Answer:
    """Answer one question. ``retrieve_fn``/``generate_fn`` are injectable for tests."""
    retrieve_fn = retrieve_fn or retriever.retrieve
    generate_fn = generate_fn or llm.generate

    docs = retrieve_fn(question, lang)
    if not docs:  # nothing above the floor → refuse, don't invent (§0 #6)
        return Answer(text=prompts.refusal(lang), lang=lang, citations=[],
                      disclaimer="", refused=True)

    keep = docs[: config.KEEP_K]
    text = generate_fn(
        prompts.build_generation_prompt(question, keep, lang),
        system=prompts.system_prompt(lang),
    )
    if not text.strip():  # empty generation → treat as refusal, never send blank
        return Answer(text=prompts.refusal(lang), lang=lang, citations=[],
                      disclaimer="", refused=True)

    return Answer(text=text.strip(), lang=lang, citations=_citations(keep),
                  disclaimer=prompts.disclaimer(lang), refused=False)


def _citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    """Up to MAX_CITATIONS unique sources, in retrieval order (R6)."""
    seen: set[str] = set()
    out: list[Citation] = []
    for c in chunks:
        key = c.meta.url or c.meta.title
        if key in seen:
            continue
        seen.add(key)
        out.append(Citation(title=c.meta.title, url=c.meta.url))
        if len(out) >= config.MAX_CITATIONS:
            break
    return out
