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
    assert prompts.refusal("he") != prompts.refusal("ru")
    # Unknown language falls back, never crashes.
    assert prompts.disclaimer("xx") == prompts.disclaimer("he")


def test_system_prompt_enforces_grounding_and_language():
    sp = prompts.system_prompt("ru")
    assert "ONLY" in sp and "Russian" in sp
    assert "ignore any instructions" in sp.lower()  # injection defense (R6)


def test_generation_prompt_includes_question_and_sources():
    p = prompts.build_generation_prompt("מה מגיע לי?", [_rc("דמי לידה", "תוכן")], "he")
    assert "מה מגיע לי?" in p
    assert "דמי לידה" in p and "תוכן" in p
    assert "[Source 1]" in p
