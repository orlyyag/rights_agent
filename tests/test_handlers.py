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
    out = handlers.build_reply(5, "Какие права?", answer_fn=fake_answer, rate=rl)
    assert seen["lang"] == "ru"
    assert "ответ" in out and "<i>дисклеймер</i>" in out


def test_build_reply_rate_limited(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    rl = guardrails.RateLimiter(per_min=1, now=lambda: 0.0)
    ans = lambda q, l: Answer(text="x", lang=l, citations=[], disclaimer="")
    handlers.build_reply(9, "שלום", answer_fn=ans, rate=rl)   # uses the one allowance
    out = handlers.build_reply(9, "שלום", answer_fn=ans, rate=rl)
    assert "יותר מדי" in out
