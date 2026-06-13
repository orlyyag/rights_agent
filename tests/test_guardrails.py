"""Guardrails: language detect, allowlist, rate cap, PII redaction — pure, LLM-free."""
from __future__ import annotations

import config
from rag import guardrails


def test_detect_lang():
    assert guardrails.detect_lang("שלום, מה מגיע לי?") == "he"
    assert guardrails.detect_lang("Здравствуйте, какие права?") == "ru"
    assert guardrails.detect_lang("hello there") == config.AUTO_LANG
    assert guardrails.detect_lang("", default="ru") == "ru"


def test_detect_lang_can_keep_legacy_he_ru_mode(monkeypatch):
    monkeypatch.setattr(config, "ANSWER_LANGUAGE_MODE", "he_ru")
    assert guardrails.detect_lang("hello there") == "he"


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


def test_too_long(monkeypatch):
    monkeypatch.setattr(config, "MAX_QUESTION_CHARS", 500)
    assert guardrails.too_long("a" * 500) is False             # boundary inclusive
    assert guardrails.too_long("a" * 501) is True
    assert guardrails.too_long("מה מגיע לי אחרי לידה?") is False
    assert guardrails.too_long("") is False
    assert guardrails.too_long("x" * 12, max_chars=10) is True


def test_rate_limiter_sliding_window():
    clock = {"t": 0.0}
    rl = guardrails.RateLimiter(per_min=2, now=lambda: clock["t"])
    assert rl.allow(7) is True
    assert rl.allow(7) is True
    assert rl.allow(7) is False          # cap hit
    clock["t"] = 61.0                     # window slides past 60s
    assert rl.allow(7) is True


def test_daily_quota_caps_per_chat():
    """A chat can ask up to `cap` questions, then is blocked the same day."""
    clock = {"t": 1_000_000.0}            # fixed instant → same local day
    q = guardrails.DailyQuota(cap=3, now=lambda: clock["t"])
    assert [q.allow(7) for _ in range(4)] == [True, True, True, False]
    assert q.remaining(7) == 0


def test_daily_quota_resets_next_day():
    clock = {"t": 1_000_000.0}
    q = guardrails.DailyQuota(cap=2, now=lambda: clock["t"])
    assert q.allow(7) and q.allow(7)
    assert q.allow(7) is False            # day-1 cap hit
    clock["t"] += 86_400                  # advance one full day
    assert q.allow(7) is True             # fresh allowance
    assert q.remaining(7) == 1


def test_daily_quota_isolated_per_chat():
    clock = {"t": 1_000_000.0}
    q = guardrails.DailyQuota(cap=1, now=lambda: clock["t"])
    assert q.allow(1) is True
    assert q.allow(1) is False
    assert q.allow(2) is True             # different chat unaffected


def test_daily_quota_zero_disables():
    q = guardrails.DailyQuota(cap=0)
    assert all(q.allow(7) for _ in range(50))
    assert q.remaining(7) == -1           # unlimited sentinel
