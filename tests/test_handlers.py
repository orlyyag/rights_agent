"""render_answer (HTML, R6) + build_reply core — pure, LLM-free."""
from __future__ import annotations

import config
from bot import handlers, session
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


def test_render_uses_auto_caveat_for_other_languages():
    ans = Answer(text="answer", lang="auto",
                 citations=[Citation(title="A", url="https://a")],
                 disclaimer="")
    out = handlers.render_answer(ans)
    assert "AI-generated answer" in out


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


def test_build_reply_routes_latin_text_to_auto_language(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    seen = {}
    def fake_answer(q, l, **kw):
        seen["lang"] = l
        return Answer(text="English answer", lang=l, citations=[], disclaimer="")
    rl = guardrails.RateLimiter(per_min=10, now=lambda: 0.0)
    out = handlers.build_reply(5, "What rights do I have after birth?", answer_fn=fake_answer, rate=rl)
    assert seen["lang"] == config.AUTO_LANG
    assert "English answer" in out


def test_build_reply_passes_history_and_records_turns(monkeypatch):
    """R5: prior turns flow into answer_fn; the new exchange is recorded after."""
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    chat_id = 4242
    session.reset(chat_id)
    session.add_turn(chat_id, "user", "מה מגיע לי אחרי לידה?")
    session.add_turn(chat_id, "assistant", "מענק לידה ודמי לידה.")
    seen = {}

    def fake_answer(q, l, history=None, **kw):
        seen["history"] = history
        return Answer(text="גם לעצמאים יש דמי לידה.", lang=l, citations=[], disclaimer="")

    rl = guardrails.RateLimiter(per_min=10, now=lambda: 0.0)
    handlers.build_reply(chat_id, "ומה לגבי עצמאים?", answer_fn=fake_answer, rate=rl)

    # answer_fn got ONLY the prior exchange, not the current message
    assert seen["history"] == [("user", "מה מגיע לי אחרי לידה?"),
                               ("assistant", "מענק לידה ודמי לידה.")]
    # the current exchange was recorded for the NEXT turn
    assert session.history(chat_id)[-2:] == [
        ("user", "ומה לגבי עצמאים?"),
        ("assistant", "גם לעצמאים יש דמי לידה."),
    ]
    session.reset(chat_id)


def test_build_reply_history_isolated_per_chat(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    a, b = 111, 222
    session.reset(a)
    session.reset(b)
    histories = {}

    def fake_answer(q, l, history=None, **kw):
        histories[q] = list(history or [])
        return Answer(text=f"ans:{q}", lang=l, citations=[], disclaimer="")

    rl = guardrails.RateLimiter(per_min=10, now=lambda: 0.0)
    handlers.build_reply(a, "שאלה ראשונה של איי", answer_fn=fake_answer, rate=rl)
    handlers.build_reply(b, "שאלה ראשונה של בי", answer_fn=fake_answer, rate=rl)

    assert histories["שאלה ראשונה של איי"] == []
    assert histories["שאלה ראשונה של בי"] == []  # chat A's turn must not leak into B
    session.reset(a)
    session.reset(b)


def test_followup_preserves_memory_on_default_linear_path(monkeypatch):
    """Reported bug: on the DEFAULT linear path, a follow-up ('what if I'm
    self-employed?') was answered from scratch — session history never reached
    retrieval. This drives the REAL answer_default (no answer_fn injected), so it
    exercises the routing that used to drop history. Memory must persist across
    turns and clear only on /reset.
    """
    from rag import llm, retriever
    from schema import ChunkMeta, RetrievedChunk

    monkeypatch.setattr(config, "ANSWER_PATH", "linear")
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    chat_id = 9001
    session.reset(chat_id)

    retrieval_queries: list[str] = []

    def fake_retrieve(query, lang, **kw):
        retrieval_queries.append(query)
        meta = ChunkMeta(pageid=1, title="דמי אבטלה", url="https://kz/unemployment",
                         lang="he", section="", lastrevid=0, source="corpus")
        return [RetrievedChunk(text="body", meta=meta, score=0.9)]

    def fake_generate(prompt, system=None):
        # The history-aware rewrite step and the answer generation share
        # llm.generate; distinguish by the rewrite system prompt.
        if system and "query rewriter" in system:
            return ('{"query": "דמי אבטלה לעצמאים", "is_follow_up": true, '
                    '"reason": "follow-up about self-employment"}')
        return "grounded answer about unemployment rights"

    monkeypatch.setattr(retriever, "retrieve", fake_retrieve)
    monkeypatch.setattr(llm, "generate", fake_generate)
    rl = guardrails.RateLimiter(per_min=100, now=lambda: 0.0)

    # Turn 1 — the original question about unemployment rights.
    handlers.build_reply(chat_id, "מה הזכויות שלי בתקופת אבטלה?", rate=rl)
    # Turn 2 — elliptical follow-up; must be read as "...for the self-employed".
    handlers.build_reply(chat_id, "ומה אם אני עצמאי?", rate=rl)

    # Turn 1 retrieved with the raw question (no prior turns yet).
    assert retrieval_queries[0] == "מה הזכויות שלי בתקופת אבטלה?"
    # Turn 2 retrieved with the REWRITTEN standalone query — proves history was
    # used instead of answering from scratch.
    assert retrieval_queries[1] == "דמי אבטלה לעצמאים"

    # /reset clears memory: the next identical follow-up is no longer fused with
    # the prior topic — it retrieves on the raw message.
    session.reset(chat_id)
    handlers.build_reply(chat_id, "ומה אם אני עצמאי?", rate=rl)
    assert retrieval_queries[2] == "ומה אם אני עצמאי?"
    session.reset(chat_id)


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
    out_en = handlers.build_reply(7, "hello", answer_fn=fa, rate=rl)
    assert "at least three words" in out_en


def test_build_reply_rate_limited(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    rl = guardrails.RateLimiter(per_min=1, now=lambda: 0.0)
    ans = lambda q, l: Answer(text="x", lang=l, citations=[], disclaimer="")
    handlers.build_reply(9, "שלום", answer_fn=ans, rate=rl)   # uses the one allowance
    out = handlers.build_reply(9, "שלום", answer_fn=ans, rate=rl)
    assert "יותר מדי" in out


# ── Concurrency (§0 #5 capacity: 20 parallel users) ──────────────────────────

def _slow_answer(delay: float):
    import time as _t

    def fa(q, l, **kw):
        _t.sleep(delay)
        return Answer(text="ok", lang=l, citations=[], disclaimer="")
    return fa


def test_build_reply_parallel_across_chats(monkeypatch):
    """20 different chats must not serialize: wall clock ≈ one answer, not 20."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    rl = guardrails.RateLimiter(per_min=100, now=lambda: 0.0)
    fa = _slow_answer(0.4)
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=20) as ex:
        outs = list(ex.map(
            lambda cid: handlers.build_reply(10_000 + cid, "מה מגיע לי אחרי לידה",
                                             answer_fn=fa, rate=rl),
            range(20)))
    wall = time.monotonic() - t0
    assert all("ok" in o for o in outs)
    # serial would be ≥ 8.0s; parallel one-deep is ~0.4s. Generous CI margin:
    assert wall < 2.0, f"20 chats serialized: wall={wall:.2f}s"


def test_build_reply_same_chat_serialized(monkeypatch):
    """Two messages in the SAME chat must not interleave history writes."""
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    chat_id = 31337
    session.reset(chat_id)
    rl = guardrails.RateLimiter(per_min=100, now=lambda: 0.0)
    fa = _slow_answer(0.15)
    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(
            lambda q: handlers.build_reply(chat_id, q, answer_fn=fa, rate=rl),
            ["שאלה ראשונה שלי כאן", "שאלה שנייה שלי כאן"]))
    hist = session.history(chat_id)
    roles = [r for r, _ in hist]
    # atomic per-turn pairs — never user,user,assistant,assistant
    assert roles == ["user", "assistant", "user", "assistant"], roles
    session.reset(chat_id)


def test_on_text_offloads_blocking_core(monkeypatch):
    """on_text must keep the event loop free while build_reply blocks."""
    import asyncio

    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    monkeypatch.setattr(handlers.answer_mod, "answer_default", _slow_answer(0.3))

    class _Msg:
        text = "מה מגיע לי אחרי לידה"

        async def reply_text(self, text, **kw):
            self.sent = text

    class _Chat:
        def __init__(self, cid):
            self.id = cid

    class _Update:
        def __init__(self, cid):
            self.effective_message = _Msg()
            self.effective_chat = _Chat(cid)

    class _Bot:
        async def send_chat_action(self, **kw):
            pass

    class _Ctx:
        bot = _Bot()

    async def main():
        import time
        ups = [_Update(20_000 + i) for i in range(5)]
        t0 = time.monotonic()
        await asyncio.gather(*(handlers.on_text(u, _Ctx()) for u in ups))
        return time.monotonic() - t0, ups

    wall, ups = asyncio.run(main())
    assert all(getattr(u.effective_message, "sent", "") for u in ups)
    # serial-on-loop would be ≥ 1.5s; offloaded is ~0.3s
    assert wall < 1.0, f"event loop was blocked: wall={wall:.2f}s"


def test_app_enables_concurrent_updates(monkeypatch):
    """PTB must dispatch updates concurrently, or the offload never gets a chance."""
    import pytest
    pytest.importorskip("telegram")
    from bot import telegram_app

    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123456:TEST-token")
    app = telegram_app.build_app()
    assert app.concurrent_updates and app.concurrent_updates > 1


# ── Daily budget cap (abuse / cost guard) ────────────────────────────────────

def test_build_reply_daily_cap_blocks_after_n(monkeypatch):
    """A chat is answered up to the daily cap, then gets the daily-limit message."""
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    rl = guardrails.RateLimiter(per_min=100, now=lambda: 0.0)
    q = guardrails.DailyQuota(cap=2, now=lambda: 1_000_000.0)
    ans = lambda txt, l, **kw: Answer(text="ok", lang=l, citations=[], disclaimer="")
    out1 = handlers.build_reply(5, "מה מגיע לי אחרי לידה", answer_fn=ans, rate=rl, quota=q)
    out2 = handlers.build_reply(5, "מה מגיע לי אחרי לידה", answer_fn=ans, rate=rl, quota=q)
    out3 = handlers.build_reply(5, "מה מגיע לי אחרי לידה", answer_fn=ans, rate=rl, quota=q)
    assert "ok" in out1 and "ok" in out2
    assert "מכסת השאלות היומית" in out3            # 3rd blocked


def test_build_reply_rejected_input_does_not_burn_quota(monkeypatch):
    """Too-short input must not consume a daily slot."""
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    monkeypatch.setattr(config, "MIN_QUESTION_WORDS", 3)
    rl = guardrails.RateLimiter(per_min=100, now=lambda: 0.0)
    q = guardrails.DailyQuota(cap=1, now=lambda: 1_000_000.0)
    ans = lambda txt, l, **kw: Answer(text="ok", lang=l, citations=[], disclaimer="")
    handlers.build_reply(6, "שלום", answer_fn=ans, rate=rl, quota=q)        # too short
    assert q.remaining(6) == 1                                              # slot intact
    out = handlers.build_reply(6, "מה מגיע לי אחרי לידה", answer_fn=ans, rate=rl, quota=q)
    assert "ok" in out                                                      # real Q answered


# ── Global cap + load-shedding (botnet / DOS backstops) ──────────────────────

def test_build_reply_global_cap_blocks_across_chats(monkeypatch):
    """The global cap trips regardless of which chat asks (botnet of accounts)."""
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    rl = guardrails.RateLimiter(per_min=100, now=lambda: 0.0)
    q = guardrails.DailyQuota(cap=100, now=lambda: 1_000_000.0)
    g = guardrails.GlobalLimiter(per_min=0, per_day=2, now=lambda: 1_000_000.0)
    ans = lambda t, l, **k: Answer(text="ok", lang=l, citations=[], disclaimer="")
    # three DIFFERENT chats, each under its own per-chat caps
    o1 = handlers.build_reply(1, "מה מגיע לי אחרי לידה", answer_fn=ans, rate=rl, quota=q, global_limiter=g)
    o2 = handlers.build_reply(2, "מה מגיע לי אחרי לידה", answer_fn=ans, rate=rl, quota=q, global_limiter=g)
    o3 = handlers.build_reply(3, "מה מגיע לי אחרי לידה", answer_fn=ans, rate=rl, quota=q, global_limiter=g)
    assert "ok" in o1 and "ok" in o2
    assert "עמוס" in o3                     # 3rd chat blocked by the GLOBAL cap


def test_on_text_sheds_load_when_saturated(monkeypatch):
    """Beyond the in-flight ceiling, on_text replies 'busy' without an LLM call."""
    import asyncio, threading

    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", frozenset())
    monkeypatch.setattr(handlers, "_INFLIGHT", threading.BoundedSemaphore(2))
    calls = {"n": 0}
    def slow(t, l, **k):
        import time as _t; _t.sleep(0.3); calls["n"] += 1
        return Answer(text="ok", lang=l, citations=[], disclaimer="")
    monkeypatch.setattr(handlers.answer_mod, "answer_default", slow)

    class _Msg:
        text = "מה מגיע לי אחרי לידה"
        async def reply_text(self, text, **kw): self.sent = text
    class _Chat:
        def __init__(self, c): self.id = c
    class _Up:
        def __init__(self, c): self.effective_message = _Msg(); self.effective_chat = _Chat(c)
    class _Bot:
        async def send_chat_action(self, **kw): pass
    class _Ctx: bot = _Bot()

    async def main():
        ups = [_Up(700 + i) for i in range(6)]
        await asyncio.gather(*(handlers.on_text(u, _Ctx()) for u in ups))
        return ups
    ups = asyncio.run(main())
    sents = [u.effective_message.sent for u in ups]
    busy = sum("busy" in s or "עסוק" in s for s in sents)
    ok = sum("ok" in s for s in sents)
    assert ok == 2 and busy == 4           # 2 admitted, 4 shed
    assert calls["n"] == 2                  # shed requests made NO answer call
