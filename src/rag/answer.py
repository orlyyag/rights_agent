"""Linear Tier-0 RAG: retrieve → generate (grounded) → cite → refuse-if-empty.

This is the POC-core path (§0 Tier-0): no agent loop yet. Tier-1 upgrades it to the
agentic ``graph.py`` (grade_docs + bounded re-retrieve). Provider-agnostic and
Telegram-free; returns an :class:`Answer` the bot renders to HTML.
"""
from __future__ import annotations

import config
from rag import llm, prompts, retriever
from schema import Answer, Citation, RetrievedChunk

# Prefixes the model emits when it follows the refusal template in prompts._SYSTEM.
# Detection lets us strip citations + caveat + disclaimer on refusal — a refusal isn't
# a "substantive answer" so the legal/AI notes don't apply.
_REFUSAL_PREFIXES: dict[str, tuple[str, ...]] = {
    "he": ("בהסתמך על המקורות",),
    "ru": ("В предоставленных источниках",),
}


def _is_template_refusal(text: str, lang: str) -> bool:
    head = text.lstrip()
    return any(head.startswith(p) for p in _REFUSAL_PREFIXES.get(lang, ()))


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
    ).strip()
    if not text:  # empty generation → treat as refusal, never send blank
        return Answer(text=prompts.refusal(lang), lang=lang, citations=[],
                      disclaimer="", refused=True)

    if _is_template_refusal(text, lang):
        # Model used the one-sentence refusal template — drop citations/caveat/disclaimer.
        return Answer(text=text, lang=lang, citations=[], disclaimer="", refused=True)

    return Answer(text=text, lang=lang, citations=_citations(keep),
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
