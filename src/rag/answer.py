"""Linear Tier-0 RAG: retrieve → generate (grounded) → cite → refuse-if-empty.

This is the POC-core path (§0 Tier-0): no agent loop yet. Tier-1 upgrades it to the
agentic ``graph.py`` (grade_docs + bounded re-retrieve). Provider-agnostic and
Telegram-free; returns an :class:`Answer` the bot renders to HTML.
"""
from __future__ import annotations

import re

import config
from rag import citations as citations_mod
from rag import llm, prompts, retriever, rewrite
from rag.llm import _set_thread_id, traceable
from schema import Answer, Citation, RetrievedChunk

_DISCLAIMER_RE = re.compile(
    re.escape(prompts.DISCLAIMER_OPEN) + r"(.+?)" + re.escape(prompts.DISCLAIMER_CLOSE),
    re.DOTALL,
)

# Prefixes the model emits when it follows the refusal template in prompts._SYSTEM.
# Detection lets us strip citations + caveat + disclaimer on refusal — a refusal isn't
# a "substantive answer" so the legal/AI notes don't apply.
_REFUSAL_PREFIXES: dict[str, tuple[str, ...]] = {
    "he": ("בהסתמך על המקורות",),
    "ru": ("В предоставленных источниках",),
}


def _strip_refusal_marker(text: str) -> str | None:
    head = (text or "").lstrip()
    if not head.startswith(prompts.REFUSAL_MARKER):
        return None
    return head[len(prompts.REFUSAL_MARKER):].lstrip(" :-—").strip()


def _is_template_refusal(text: str, lang: str) -> bool:
    head = text.lstrip()
    if _strip_refusal_marker(head) is not None:
        return True
    return any(head.startswith(p) for p in _REFUSAL_PREFIXES.get(lang, ()))


def _refusal_text(text: str, lang: str) -> str:
    marked = _strip_refusal_marker(text)
    if marked is not None:
        return marked
    return text


def _extract_disclaimer(text: str, lang: str) -> tuple[str, str]:
    """Split a substantive answer into (body, disclaimer).

    he/ru: disclaimer comes from the static per-language table.
    auto: pull [DISCLAIMER]...[/DISCLAIMER] out of the body. Fall back to the
    English disclaimer if the model omitted the tags, so §7 always holds.
    """
    if lang != config.AUTO_LANG:
        return text, prompts.disclaimer(lang)
    m = _DISCLAIMER_RE.search(text or "")
    if not m:
        return text, prompts.disclaimer(config.AUTO_LANG)
    body = (text[: m.start()] + text[m.end():]).strip()
    disc = m.group(1).strip()
    return body, disc or prompts.disclaimer(config.AUTO_LANG)


def _localized_empty_refusal(question: str, lang: str, generate_fn) -> str:
    """Return a no-context refusal. Auto mode spends one small LLM call so the
    fixed refusal can be in the question's language instead of English/Hebrew."""
    if lang != config.AUTO_LANG:
        return prompts.refusal(lang)
    try:
        text = generate_fn(
            prompts.build_refusal_prompt(question, lang),
            system=prompts.system_prompt(lang),
        ).strip()
    except Exception:  # noqa: BLE001 — no-context fallback must never crash
        return prompts.refusal(lang)
    return _refusal_text(text, lang) or prompts.refusal(lang)


@traceable(name="answer:linear", run_type="chain")
def answer(question: str, lang: str,
           history: list[tuple[str, str]] | None = None,
           *, retrieve_fn=None, generate_fn=None, rewrite_fn=None,
           thread_id: str | None = None) -> Answer:
    """Answer one question. ``retrieve_fn``/``generate_fn``/``rewrite_fn`` are
    injectable for tests. ``history`` is the recent (role, text) turns from the
    per-chat session; when present, an elliptical follow-up ("ולעצמאים?") is
    condensed into a self-contained retrieval query (R5) so conversational memory
    carries across turns instead of each message being answered from scratch.
    ``thread_id`` groups this call with its child traces in LangSmith (set by the
    bot to chat_id, by the eval to the question id)."""
    _set_thread_id(thread_id)
    retrieve_fn = retrieve_fn or retriever.retrieve
    generate_fn = generate_fn or llm.generate
    rewrite_fn = rewrite_fn or rewrite.rewrite_query

    # History-aware condense (R5): fold a follow-up into a standalone query before
    # retrieval. No history → no LLM call (Tier-0 stays cheap), retrieval runs on
    # the raw question. Generation below still uses the original ``question``,
    # matching the agent path (graph.node_generate) so both paths answer identically.
    search_q = question
    if history:
        search_q = rewrite_fn(question, history=history, generate_fn=generate_fn).query or question

    docs = retrieve_fn(search_q, lang)
    if not docs:  # nothing above the floor → refuse, don't invent (§0 #6)
        return Answer(text=_localized_empty_refusal(question, lang, generate_fn), lang=lang, citations=[],
                      disclaimer="", refused=True)

    keep = docs[: config.KEEP_K]
    text = generate_fn(
        prompts.build_generation_prompt(question, keep, lang),
        system=prompts.system_prompt(lang),
    ).strip()
    if not text:  # empty generation → treat as refusal, never send blank
        return Answer(text=_localized_empty_refusal(question, lang, generate_fn), lang=lang, citations=[],
                      disclaimer="", refused=True)

    if _is_template_refusal(text, lang):
        # Model used the one-sentence refusal template — drop citations/caveat/disclaimer.
        return Answer(text=_refusal_text(text, lang), lang=lang, citations=[],
                      disclaimer="", refused=True)

    body, disc = _extract_disclaimer(text, lang)
    return Answer(text=body, lang=lang, citations=_citations(keep, lang),
                  disclaimer=disc, refused=False)


def answer_agent(question: str, lang: str,
                 history: list[tuple[str, str]] | None = None,
                 *, thread_id: str | None = None) -> Answer:
    """Tier-1 agent path entrypoint (drop-in for :func:`answer`).

    Delegates to ``rag.graph.run_agent`` — rewrite → retrieve → grade → (re-retrieve
    ×1) → generate. Imports ``rag.graph`` lazily so tests of the linear path don't
    need langgraph installed.
    """
    from rag import graph  # noqa: PLC0415 — lazy to keep the linear path import-light
    return graph.run_agent(question, lang, history=history, thread_id=thread_id)


def answer_default(question: str, lang: str,
                   history: list[tuple[str, str]] | None = None,
                   *, thread_id: str | None = None) -> Answer:
    """Route by :data:`config.ANSWER_PATH`. The bot calls this; flipping
    ``KZ_ANSWER_PATH=agent`` in .env switches every Telegram message over.
    ``thread_id`` propagates to LangSmith so we can group all calls in one
    conversation/eval-question."""
    if (config.ANSWER_PATH or "").lower() == "agent":
        return answer_agent(question, lang, history=history, thread_id=thread_id)
    return answer(question, lang, history=history, thread_id=thread_id)


def _citations(chunks: list[RetrievedChunk], lang: str = "he") -> list[Citation]:
    """Up to MAX_CITATIONS unique sources, in retrieval order (R6).

    Links follow the citation language policy: ru questions get ru links,
    he/auto get he links — cross-language chunks are mapped via langlinks
    (``rag.citations``). Dedup runs AFTER localization, so the he and ru
    chunks of the same underlying page collapse into one citation.
    """
    target = citations_mod.desired_citation_lang(lang)
    seen: set[str] = set()
    out: list[Citation] = []
    for c in chunks:
        title, url = citations_mod.localize(c.meta, target)
        key = url or title
        if key in seen:
            continue
        seen.add(key)
        out.append(Citation(title=title, url=url))
        if len(out) >= config.MAX_CITATIONS:
            break
    return out
