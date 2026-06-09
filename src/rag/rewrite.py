"""History-aware query rewrite (R5).

Two jobs in one node:
1. **Condense follow-ups.** Elliptical user messages like "ולעצמאים?"
   ("and for freelancers?") are non-retrievable on their own; the rewriter folds
   the last ~2–3 turns into a self-contained standalone query.
2. **Frankenquery guard.** When the user switches topics ("maternity benefits →
   parking fines"), DO NOT fuse them. Detect new-topic and pass through.

Also handles **terminology broadening** for the agent's re-retrieve step (R4)
— given a grade_docs "narrow_terminology" verdict, the same LLM expands the
query toward Kol Zchut's official vocabulary.

If history is empty (Tier-0 case), the rewriter is a no-op pass-through
WITHOUT an LLM call — keeps live cost down.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

import config
from rag import llm

_REWRITE_SYSTEM = (
    "You are a query rewriter for a Hebrew/Russian rights assistant.\n"
    "Given the recent conversation (last 2–3 turns) and the user's CURRENT message, "
    "decide whether the current message is a follow-up to the prior topic or a fresh "
    "new question, then produce ONE standalone search query.\n\n"
    "Rules:\n"
    "- If the current message is a follow-up (elliptical / refers to prior topic), "
    "fold the prior topic into a self-contained query. e.g. prior was about maternity "
    "benefits, current is 'and for freelancers?' → 'maternity benefits for self-employed'.\n"
    "- If the current message switches topic, treat as new — return the current message "
    "verbatim as the query. Do NOT fuse unrelated topics.\n"
    "- Keep the query in the user's language.\n\n"
    "Respond with STRICT JSON ONLY:\n"
    '{"query": "<standalone query>", "is_follow_up": <bool>, "reason": "<short>"}'
)

_BROADEN_SYSTEM = (
    "You are a query rewriter for the Kol Zchut rights database. "
    "The user's query as written did not match any relevant documents. "
    "Rewrite it using broader / more official Kol Zchut terminology — replace "
    "colloquialisms with the formal legal/benefit term (e.g. 'money for new moms' "
    "→ 'מענק לידה' / 'дотация при рождении'). Keep the user's language.\n\n"
    "Respond with STRICT JSON ONLY:\n"
    '{"query": "<broadened query>", "reason": "<short>"}'
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class RewriteResult:
    query: str
    is_follow_up: bool
    reason: str = ""


def _parse_json(text: str) -> dict:
    m = _JSON_RE.search(text or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _format_history(history: Iterable[tuple[str, str]], n: int) -> str:
    pairs = list(history)[-n:]
    lines = []
    for role, text in pairs:
        tag = "User" if role == "user" else "Assistant"
        snippet = (text or "").strip().replace("\n", " ")
        if len(snippet) > 240:
            snippet = snippet[:240] + "…"
        lines.append(f"{tag}: {snippet}")
    return "\n".join(lines)


def rewrite_query(question: str, history: list[tuple[str, str]] | None = None,
                  *, generate_fn=None) -> RewriteResult:
    """Condense a follow-up into a standalone query. No history → pass-through
    (no LLM call). Failed JSON parse → pass-through (defensive)."""
    question = (question or "").strip()
    if not history:
        return RewriteResult(query=question, is_follow_up=False, reason="no_history")

    generate_fn = generate_fn or llm.generate
    n = config.REWRITE_HISTORY_TURNS
    user = (
        f"Recent conversation:\n{_format_history(history, n)}\n\n"
        f"Current user message:\n{question}\n\n"
        "Return the JSON described in the system prompt."
    )
    raw = generate_fn(user, system=_REWRITE_SYSTEM)
    data = _parse_json(raw)
    q = (data.get("query") or "").strip() or question
    return RewriteResult(
        query=q,
        is_follow_up=bool(data.get("is_follow_up")),
        reason=str(data.get("reason") or ""),
    )


def broaden_terminology(question: str, *, generate_fn=None) -> RewriteResult:
    """Used by the re-retrieve transform when grade_docs returns
    ``narrow_terminology`` (R4). One LLM call → broader query in same language."""
    generate_fn = generate_fn or llm.generate
    raw = generate_fn(
        f"Original query: {question}\n\nReturn the JSON described in the system prompt.",
        system=_BROADEN_SYSTEM,
    )
    data = _parse_json(raw)
    q = (data.get("query") or "").strip() or question
    return RewriteResult(query=q, is_follow_up=False, reason=str(data.get("reason") or ""))
