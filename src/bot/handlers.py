"""Telegram handlers — thin I/O over the agent core.

Holds ``render_answer`` (HTML parse mode, R6) and the sync, testable ``build_reply``
core. The async PTB callbacks reference ``telegram`` types only via string
annotations (``from __future__ import annotations``), so this module imports without
python-telegram-bot installed — PTB is imported only in ``telegram_app``.
"""
from __future__ import annotations

import asyncio
import html
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import config
from bot import session
from rag import answer as answer_mod
from rag import guardrails
from schema import Answer

WELCOME = (
    "שלום! אני עוזר/ת זכויות מבוסס 'כל זכות'. שאלו על זכויות והטבות בישראל. "
    "כדאי לציין פרטים רלוונטיים כמו גיל, מצב משפחתי או מצב תעסוקתי לקבלת תשובה מדויקת יותר.\n"
    "\n"
    "Здравствуйте! Я ассистент по правам на базе «Коль Зхут». Спросите о правах и льготах в Израиле. "
    "Можно указать релевантные детали (возраст, семейное положение, трудоустройство) для более точного ответа."
)
PRIVATE = "🔒 זהו דמו פרטי. · Это частный демо-доступ."
RATE_MSG = {
    "he": "קיבלתי יותר מדי הודעות. נסו שוב בעוד דקה.",
    "ru": "Слишком много сообщений. Попробуйте через минуту.",
    "auto": "Too many messages. Try again in a minute.",
}
NONTEXT = {
    "he": "אפשר לכתוב את השאלה בטקסט?",
    "ru": "Пожалуйста, напишите вопрос текстом.",
}
ERROR = {
    "he": "מצטער/ת, יש תקלה זמנית. נסו שוב.",
    "ru": "Извините, временная ошибка. Попробуйте ещё раз.",
    "auto": "Sorry, something went wrong. Please try again.",
}
RESET_OK = "🔄 השיחה אופסה. · Диалог сброшен."
TOO_SHORT = {
    "he": "על השאלה לכלול שלוש מילים לכל הפחות.",
    "ru": "Вопрос должен содержать не менее трёх слов.",
    "auto": "Please write the question in at least three words.",
}
TOO_LONG = {
    "he": "השאלה ארוכה מדי. נסחו אותה בקצרה (עד 500 תווים).",
    "ru": "Вопрос слишком длинный. Сформулируйте короче (до 500 символов).",
    "auto": "The question is too long. Please keep it under 500 characters.",
}

# Caveat shown between body and citations, mirroring the official KZ on-site chat:
# tells the user the answer is AI-generated and to verify via the source links.
AI_CAVEAT = {
    "he": "תשובה מבוססת AI. כדאי לוודא את הפרטים בקישורים שלמטה:",
    "ru": "Ответ сгенерирован ИИ. Рекомендуем проверить детали по ссылкам ниже:",
    "auto": "AI-generated answer. Please verify the details in the links below:",
}

_LIMITER = guardrails.RateLimiter()
_BOLD_RE = re.compile(r"\*\*([^*\n]+?)\*\*")

# ── Concurrency (§0 #5 capacity) ─────────────────────────────────────────────
# The answer core blocks for seconds (LLM calls). PTB dispatches updates
# concurrently (concurrent_updates in telegram_app), and on_text offloads
# build_reply to this pool so the event loop stays free. A per-chat lock keeps
# one conversation's turns ordered (history coherence) while different chats
# run in parallel.
_EXECUTOR = ThreadPoolExecutor(max_workers=config.BOT_WORKERS, thread_name_prefix="answer")
_chat_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _chat_lock(chat_id: int) -> threading.Lock:
    with _locks_guard:
        lock = _chat_locks.get(chat_id)
        if lock is None:
            lock = _chat_locks[chat_id] = threading.Lock()
        return lock


def _esc(s: str) -> str:
    return html.escape(s or "")


def _localized(table: dict[str, str], lang: str) -> str:
    return table.get(lang) or table.get(config.AUTO_LANG) or table["he"]


def _md_to_telegram_html(escaped_text: str) -> str:
    """Convert Gemini's markdown (already HTML-escaped) to Telegram HTML.

    Only the patterns our system prompt asks the model to emit:
    line-start ``"* "`` → ``"• "`` (bullet character; no HTML semantics);
    inline ``**text**`` → ``<b>text</b>``. Asterisks aren't HTML-special, so this
    can safely run *after* :func:`html.escape`.
    """
    lines = []
    for line in escaped_text.split("\n"):
        if line.startswith("* "):
            line = "• " + line[2:]
        lines.append(line)
    return _BOLD_RE.sub(r"<b>\1</b>", "\n".join(lines))


def render_answer(ans: Answer) -> str:
    """Render an :class:`Answer` to a Telegram HTML message (R6):

    body → italic AI caveat → citation list → italic legal disclaimer.
    A refusal (no citations) renders as the body alone; we don't show the
    "verify via links" caveat when there are no links to verify with.
    """
    parts: list[str] = [_md_to_telegram_html(_esc(ans.text))]
    if ans.citations:
        caveat = _localized(AI_CAVEAT, ans.lang)
        parts.append(f"<i>{_esc(caveat)}</i>")
        parts.append("\n".join(
            f'📄 <a href="{html.escape(c.url, quote=True)}">{_esc(c.title)}</a>'
            for c in ans.citations
        ))
    if ans.disclaimer:
        parts.append(f"<i>{_esc(ans.disclaimer)}</i>")
    return "\n\n".join(p for p in parts if p)


def build_reply(chat_id: int, text: str, *, answer_fn=None, rate=None) -> str:
    """Sync core: allowlist → rate cap → detect language → answer → render.
    Pure and injectable; the async callbacks below are a thin shell over this."""
    answer_fn = answer_fn or answer_mod.answer_default
    limiter = rate if rate is not None else _LIMITER

    if not guardrails.is_allowed(chat_id):
        return _esc(PRIVATE)
    # Per-chat critical section: rate-window, history read, answer, history
    # write happen atomically per conversation. Different chats interleave
    # freely on the worker pool.
    with _chat_lock(chat_id):
        lang = guardrails.detect_lang(text)
        if not limiter.allow(chat_id):
            return _esc(_localized(RATE_MSG, lang))
        if guardrails.too_short(text):
            return _esc(_localized(TOO_SHORT, lang))
        if guardrails.too_long(text):
            return _esc(_localized(TOO_LONG, lang))
        # thread_id = the Telegram chat_id, so a single conversation's traces group
        # in LangSmith — across linear or agent path, across many messages.
        # History (R5) is read BEFORE recording the current turn — the rewrite step
        # receives prior turns + the current message separately.
        try:
            ans = answer_fn(text, lang, history=session.history(chat_id),
                            thread_id=f"chat:{chat_id}")
        except TypeError:
            # injected test fakes may not accept kwargs — fall back to positional
            ans = answer_fn(text, lang)
        session.add_turn(chat_id, "user", text)
        session.add_turn(chat_id, "assistant", ans.text)
        return render_answer(ans)


# ── async PTB callbacks (telegram imported lazily in telegram_app) ───────────
async def _send(update, text: str) -> None:
    await update.effective_message.reply_text(
        text,
        parse_mode=config.TELEGRAM_PARSE_MODE,
        disable_web_page_preview=config.DISABLE_WEB_PAGE_PREVIEW,
    )


async def on_text(update, context) -> None:
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        # Off the event loop: build_reply blocks for seconds on LLM calls.
        # 20 users → 20 pool threads in flight, the loop keeps dispatching.
        reply = await asyncio.get_running_loop().run_in_executor(
            _EXECUTOR, build_reply, update.effective_chat.id, update.effective_message.text)
        await _send(update, reply)
    except Exception:  # noqa: BLE001 — never crash the process (§0 #6)
        lang = guardrails.detect_lang(getattr(update.effective_message, "text", "") or "")
        await _send(update, _esc(_localized(ERROR, lang)))


async def on_nontext(update, context) -> None:
    await _send(update, _esc(NONTEXT["he"]))  # can't detect language without text (§0 #8)


async def on_start(update, context) -> None:
    await _send(update, _esc(WELCOME))


async def on_help(update, context) -> None:
    await _send(update, _esc(WELCOME))


async def on_reset(update, context) -> None:
    session.reset(update.effective_chat.id)
    await _send(update, _esc(RESET_OK))
