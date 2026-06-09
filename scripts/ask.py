"""Telegram-free smoke: ask the live RAG path one question and print the result.

Usage (from repo root, with deps installed + an index built + GEMINI_API_KEY set):
    PYTHONPATH=.:src python scripts/ask.py "מה מגיע לי אחרי לידה?"
    PYTHONPATH=.:src python scripts/ask.py "какие права у меня после рождения ребёнка?" ru

Exercises retriever (Chroma over the active collection) + generate (Gemini) end to end.
"""
from __future__ import annotations

import sys

from rag import answer, guardrails


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('usage: ask.py "your question" [he|ru]')
    question = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else guardrails.detect_lang(question)

    a = answer.answer(question, lang)
    print(f"\n[lang={a.lang}  refused={a.refused}]\n{a.text}\n")
    for c in a.citations:
        print(f"  📄 {c.title} — {c.url}")
    if a.disclaimer:
        print(f"\n{a.disclaimer}")


if __name__ == "__main__":
    main()
