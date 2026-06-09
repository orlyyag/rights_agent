"""Guardrails: language detect, allowlist, rate cap, PII redaction — pure, LLM-free."""
from __future__ import annotations

import config
from rag import guardrails


def test_detect_lang():
    assert guardrails.detect_lang("שלום, מה מגיע לי?") == "he"
    assert guardrails.detect_lang("Здравствуйте, какие права?") == "ru"
    assert guardrails.detect_lang("hello there") == "he"      # Latin → default
    assert guardrails.detect_lang("", default="ru") == "ru"


def test_is_allowed(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    assert guardrails.is_allowed(999) is True                 # empty = allow all
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset({1, 2}))
    assert guardrails.is_allowed(1) is True
    assert guardrails.is_allowed(999) is False


def test_redact_pii():
    assert "[ID]" in guardrails.redact_pii("מספר זהות 123456789 בבקשה")
    assert "[PHONE]" in guardrails.redact_pii("התקשרו 050-1234567")
    assert "123456789" not in guardrails.redact_pii("123456789")


def test_too_short(monkeypatch):
    monkeypatch.setattr(config, "MIN_QUESTION_WORDS", 3)
    assert guardrails.too_short("שלום") is True
    assert guardrails.too_short("מה זה?") is True              # 2 words
    assert guardrails.too_short("מה מגיע לי") is False         # 3 words
    assert guardrails.too_short("") is True
    assert guardrails.too_short("hello world there", min_words=2) is False


def test_rate_limiter_sliding_window():
    clock = {"t": 0.0}
    rl = guardrails.RateLimiter(per_min=2, now=lambda: clock["t"])
    assert rl.allow(7) is True
    assert rl.allow(7) is True
    assert rl.allow(7) is False          # cap hit
    clock["t"] = 61.0                     # window slides past 60s
    assert rl.allow(7) is True
