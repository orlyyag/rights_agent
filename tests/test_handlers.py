"""render_answer (HTML, R6) + build_reply core — pure, LLM-free."""
from __future__ import annotations

import config
from bot import handlers
from rag import guardrails
from schema import Answer, Citation


def test_render_answer_escapes_and_formats():
    ans = Answer(
        text="A & B <ok>",
        lang="he",
        citations=[Citation(title="זכאות <x>", url="https://kz/a?b=1&c=2")],
        disclaimer="כללי בלבד",
    )
    out = handlers.render_answer(ans)
    assert "A &amp; B &lt;ok&gt;" in out          # body HTML-escaped
    assert '<a href="https://kz/a?b=1&amp;c=2">זכאות &lt;x&gt;</a>' in out
    assert "📄" in out
    assert out.endswith("<i>כללי בלבד</i>")        # disclaimer italic, last


def test_render_refusal_is_body_only():
    ans = Answer(text="לא מצאתי", lang="he", citations=[], disclaimer="", refused=True)
    out = handlers.render_answer(ans)
    assert out == "לא מצאתי"
    assert "<i>" not in out and "📄" not in out
    assert "תשובה מבוססת AI" not in out  # no caveat when no citations


def test_render_converts_markdown_bold_and_bullets():
    """Gemini emits **bold** + line-start `* ` (per system prompt); we convert to HTML."""
    ans = Answer(
        text="**דמי לידה:**\n* שבועות 15\n* שבועות 8\nשורה רגילה",
        lang="he", citations=[], disclaimer="",
    )
    out = handlers.render_answer(ans)
    assert "<b>דמי לידה:</b>" in out
    assert "• שבועות 15" in out
    assert "• שבועות 8" in out
    assert "שורה רגילה" in out
    assert "**" not in out                 # no literal asterisks left in the output
    assert "\n* " not in out                # no bullet asterisks left


def test_render_inserts_ai_caveat_between_body_and_citations():
    ans = Answer(text="גוף תשובה", lang="he",
                 citations=[Citation(title="A", url="https://a")],
                 disclaimer="כללי בלבד")
    out = handlers.render_answer(ans)
    body_i = out.find("גוף תשובה")
    caveat_i = out.find("תשובה מבוססת AI")
    cite_i = out.find("📄")
    disc_i = out.find("כללי בלבד")
    assert -1 < body_i < caveat_i < cite_i < disc_i
    assert "<i>" + handlers._esc(handlers.AI_CAVEAT["he"]) + "</i>" in out


def test_render_uses_russian_caveat_when_lang_ru():
    ans = Answer(text="ответ", lang="ru",
                 citations=[Citation(title="A", url="https://a")],
                 disclaimer="дисклеймер")
    out = handlers.render_answer(ans)
    assert "Ответ сгенерирован ИИ" in out


def test_build_reply_blocks_unallowed(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset({1}))
    called = {"n": 0}
    def fake_answer(q, l):
        called["n"] += 1
        return Answer(text="x", lang=l, citations=[], disclaimer="")
    out = handlers.build_reply(2, "שלום", answer_fn=fake_answer)
    assert "דמו פרטי" in out
    assert called["n"] == 0                         # answer never invoked for blocked user


def test_build_reply_answers_allowed_and_detects_lang(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    seen = {}
    def fake_answer(q, l):
        seen["lang"] = l
        return Answer(text="ответ", lang=l, citations=[], disclaimer="дисклеймер")
    rl = guardrails.RateLimiter(per_min=10, now=lambda: 0.0)
    out = handlers.build_reply(5, "Какие у меня права?", answer_fn=fake_answer, rate=rl)
    assert seen["lang"] == "ru"
    assert "ответ" in out and "<i>дисклеймер</i>" in out


def test_build_reply_rejects_too_long_without_calling_answer(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    monkeypatch.setattr(config, "MIN_QUESTION_WORDS", 3)
    monkeypatch.setattr(config, "MAX_QUESTION_CHARS", 50)
    called = {"n": 0}
    def fa(q, l):
        called["n"] += 1
        return Answer(text="x", lang=l, citations=[], disclaimer="")
    rl = guardrails.RateLimiter(per_min=10, now=lambda: 0.0)
    long_he = "מה מגיע לי " * 20  # > 50 chars, > 3 words
    out = handlers.build_reply(8, long_he, answer_fn=fa, rate=rl)
    assert "ארוכה" in out
    assert called["n"] == 0


def test_build_reply_rejects_too_short_without_calling_answer(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    monkeypatch.setattr(config, "MIN_QUESTION_WORDS", 3)
    called = {"n": 0}
    def fa(q, l):
        called["n"] += 1
        return Answer(text="x", lang=l, citations=[], disclaimer="")
    rl = guardrails.RateLimiter(per_min=10, now=lambda: 0.0)
    out = handlers.build_reply(7, "שלום", answer_fn=fa, rate=rl)
    assert "שלוש מילים" in out
    assert called["n"] == 0  # never reached the answer path
    # Russian variant
    out_ru = handlers.build_reply(7, "привет", answer_fn=fa, rate=rl)
    assert "не менее трёх слов" in out_ru


def test_build_reply_rate_limited(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    rl = guardrails.RateLimiter(per_min=1, now=lambda: 0.0)
    ans = lambda q, l: Answer(text="x", lang=l, citations=[], disclaimer="")
    handlers.build_reply(9, "שלום", answer_fn=ans, rate=rl)   # uses the one allowance
    out = handlers.build_reply(9, "שלום", answer_fn=ans, rate=rl)
    assert "יותר מדי" in out
