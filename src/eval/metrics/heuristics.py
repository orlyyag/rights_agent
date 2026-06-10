"""Deterministic eval metrics — pure functions, no LLM, no network.

Anything knowable from pipeline outputs lives here (retrieval rank, citations,
language, refusal kind). Semantic judgments live in ``judges.py``.
"""
from __future__ import annotations

import re

_HEB = re.compile(r"[֐-׿]")
_LATIN_CYR = re.compile(r"[A-Za-zЀ-ӿ]")
_KZ_HE = re.compile(r"^https?://(www\.)?kolzchut\.org\.il/he/.+", re.IGNORECASE)


def _as_set(gold) -> set[str]:
    if gold is None:
        return set()
    if isinstance(gold, (set, list, tuple)):
        return {str(g) for g in gold}
    return {str(gold)}


def hit_at_k(retrieved_doc_ids: list[str], gold_doc_ids, k: int) -> bool:
    gold = _as_set(gold_doc_ids)
    if not gold:
        return False
    return bool(gold & {str(d) for d in retrieved_doc_ids[:k]})


def recall_at_k(retrieved_doc_ids: list[str], gold_doc_ids, k: int) -> float:
    gold = _as_set(gold_doc_ids)
    if not gold:
        return 0.0
    found = gold & {str(d) for d in retrieved_doc_ids[:k]}
    return len(found) / len(gold)


def mrr(retrieved_doc_ids: list[str], gold_doc_ids) -> float:
    gold = _as_set(gold_doc_ids)
    for rank, d in enumerate(retrieved_doc_ids, start=1):
        if str(d) in gold:
            return 1.0 / rank
    return 0.0


def context_precision_at_k(relevance_flags: list[bool], k: int) -> float:
    flags = relevance_flags[:k]
    if not flags:
        return 0.0
    return sum(1 for f in flags if f) / len(flags)


def citation_present(citation_urls: list[str]) -> bool:
    return any((u or "").strip() for u in (citation_urls or []))


def citation_valid(citation_urls: list[str]) -> float:
    """Fraction of citations that are well-formed Kol Zchut /he/ links."""
    urls = [u for u in (citation_urls or []) if (u or "").strip()]
    if not urls:
        return 0.0
    return sum(1 for u in urls if _KZ_HE.match(u)) / len(urls)


def language_match(text: str, expected: str = "he") -> bool:
    heb = len(_HEB.findall(text or ""))
    other = len(_LATIN_CYR.findall(text or ""))
    if heb + other == 0:
        return False
    ratio = heb / (heb + other)
    return ratio >= 0.5 if expected == "he" else ratio < 0.5


def refusal_kind(*, refused: bool, hit: bool) -> str:
    if not refused:
        return "answered"
    return "false_refusal" if hit else "justified_refusal"
