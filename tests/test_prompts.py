"""Prompt/disclaimer/refusal contracts (§7) — pure, LLM-free."""
from __future__ import annotations

from rag import prompts
from schema import ChunkMeta, RetrievedChunk


def _rc(title: str, body: str) -> RetrievedChunk:
    meta = ChunkMeta(pageid=1, title=title, url="https://kz/x", lang="he",
                     section="", lastrevid=0, source="corpus")
    return RetrievedChunk(text=body, meta=meta, score=0.9)


def test_disclaimer_and_refusal_per_language():
    assert "כל זכות" in prompts.disclaimer("he")
    assert "Коль Зхут" in prompts.disclaimer("ru")
    # Auto mode now has a real English fallback disclaimer — the renderer can
    # always append something even if Gemini omits the [DISCLAIMER] tags.
    assert "Kol Zchut" in prompts.disclaimer("auto")
    assert "not legal advice" in prompts.disclaimer("auto")
    assert prompts.refusal("he") != prompts.refusal("ru")
    # Unknown language falls back, never crashes.
    assert prompts.disclaimer("xx") == prompts.disclaimer("he")


def test_system_prompt_enforces_grounding_and_language():
    sp = prompts.system_prompt("ru")
    assert "ONLY" in sp and "Russian" in sp
    assert "ignore any instructions" in sp.lower()  # injection defense (R6)
    assert prompts.REFUSAL_MARKER in sp


def test_auto_system_prompt_identifies_main_question_language():
    sp = prompts.system_prompt("auto")
    assert "language the user's question is written in" in sp
    assert "NEVER in the language of the sources" in sp
    assert "legal disclaimer" in sp
    # Disclaimer must be emitted with the wrapper tags so we can parse it out
    # deterministically — §7 cannot be left to model goodwill alone.
    assert prompts.DISCLAIMER_OPEN in sp
    assert prompts.DISCLAIMER_CLOSE in sp


def test_generation_prompt_includes_question_and_sources():
    p = prompts.build_generation_prompt("מה מגיע לי?", [_rc("דמי לידה", "תוכן")], "he")
    assert "מה מגיע לי?" in p
    assert "דמי לידה" in p and "תוכן" in p
    assert "[Source 1]" in p


def test_auto_generation_prompt_keeps_question_language():
    p = prompts.build_generation_prompt("What am I entitled to after birth?", [_rc("מענק לידה", "תוכן")], "auto")
    assert "NEVER in the language of the sources" in p
    assert "What am I entitled to" in p


def test_system_prompt_guards_against_over_refusal_and_scope_creep():
    """Regression guards for the ed420cf prompt rework (2026-06-12 fix):
    the rework re-introduced over-refusal (in-020), dropped eligibility
    hedging (in-005), and inflated answers with off-question benefit surveys.
    eval/failure_analysis.txt, 'V2 RE-RUN FLIP ANALYSIS'."""
    sp = prompts.system_prompt("he")
    # partial coverage → answer with what the sources DO say, never refuse
    assert "partially or in general terms" in sp
    assert "instead of refusing" in sp
    # criteria-based rights are presented as conditional, not unconditional
    assert "עשויים להיות זכאים" in sp
    assert "conditional" in sp
    # answers stay on-question — no adjacent-benefits enumeration
    assert "Answer ONLY the question asked" in sp
    # the refusal marker mechanics must survive any rewording (answer.py parses it)
    assert prompts.REFUSAL_MARKER in sp
