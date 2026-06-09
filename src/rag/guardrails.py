"""Guardrails (§7). Input: language detection, allowlist, rate cap, non-text handling;
PII redaction for logs. Output faithfulness/grounding checks are Tier-1 (the linear
Tier-0 path already does refuse-if-empty + citations in ``answer.py``).
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque

import config

_HEBREW = re.compile("[֐-׿]")     # Hebrew block
_CYRILLIC = re.compile("[Ѐ-ӿ]")   # Cyrillic block
_IL_ID = re.compile(r"\b\d{9}\b")               # 9-digit Israeli ID (heuristic)
_PHONE = re.compile(r"\b0\d{1,2}[-\s]?\d{7}\b")  # IL phone with optional separator


def detect_lang(text: str, default: str = "he") -> str:
    """Script-based he/ru detection (§0 Lang-detect). Latin/empty → default."""
    he = len(_HEBREW.findall(text or ""))
    ru = len(_CYRILLIC.findall(text or ""))
    if ru > he:
        return "ru"
    if he:
        return "he"
    return default


def is_allowed(chat_id: int) -> bool:
    """Allowlist check (§0 #5). Empty allowlist = allow all (dev); set
    ALLOWED_CHAT_IDS for the private demo."""
    return not config.ALLOWED_CHAT_IDS or chat_id in config.ALLOWED_CHAT_IDS


def too_short(text: str, min_words: int | None = None) -> bool:
    """A real question is at least :data:`config.MIN_QUESTION_WORDS` whitespace-
    separated tokens. Greetings ("שלום", "привет") retrieve noisy unrelated chunks
    and waste an LLM call, so reject before the answer path."""
    threshold = config.MIN_QUESTION_WORDS if min_words is None else min_words
    return len((text or "").split()) < threshold


def too_long(text: str, max_chars: int | None = None) -> bool:
    """Cap question length at :data:`config.MAX_QUESTION_CHARS`. Long inputs
    blur the query embedding, balloon LLM cost, and expand the prompt-injection
    surface — none of which serve a real rights question."""
    threshold = config.MAX_QUESTION_CHARS if max_chars is None else max_chars
    return len(text or "") > threshold


def redact_pii(text: str) -> str:
    """Heuristic redaction before logging (§0 Grill Q8). Over-redacts by design;
    raw user text is never written to the log. NOTE: bare 10-digit mobiles may slip —
    logs are local + gitignored, so this is defense-in-depth, not the only control."""
    text = _PHONE.sub("[PHONE]", text or "")
    return _IL_ID.sub("[ID]", text)


class RateLimiter:
    """Per-chat sliding-window cap (§0 #5). In-memory → resets on restart (Q7)."""

    def __init__(self, per_min: int | None = None, *, now=time.monotonic):
        self.per_min = per_min if per_min is not None else config.RATE_LIMIT_PER_MIN
        self._now = now
        self._hits: dict[int, deque] = defaultdict(deque)

    def allow(self, chat_id: int) -> bool:
        t = self._now()
        q = self._hits[chat_id]
        while q and t - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_min:
            return False
        q.append(t)
        return True
