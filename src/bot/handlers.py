"""Telegram handlers — thin I/O over the agent core.

Holds ``render_answer`` (HTML parse mode, R6) and the sync, testable ``build_reply``
core. The async PTB callbacks reference ``telegram`` types only via string
annotations (``from __future__ import annotations``), so this module imports without
python-telegram-bot installed — PTB is imported only in ``telegram_app``.
"""
from __future__ import annotations

import html

import config
from rag import answer as answer_mod
from rag import guardrails
from schema import Answer

WELCOME = (
    "שלום! אני עוזר/ת זכויות מבוסס 'כל זכות'. שאלו על זכויות והטבות בישראל.\n"
    "Здравствуйте! Я ассистент по правам на базе «Коль Зхут». "
    "Спросите о правах и льготах в Израиле."
)
PRIVATE = "🔒 זהו דמו פרטי. · Это частный демо-доступ."
RATE_MSG = {
    "he": "קיבלתי יותר מדי הודעות. נסו שוב בעוד דקה.",
    "ru": "Слишком много сообщений. Попробуйте через минуту.",
}
NONTEXT = {
    "he": "אפשר לכתוב את השאלה בטקסט?",
    "ru": "Пожалуйста, напишите вопрос текстом.",
}
ERROR = {
    "he": "מצטער/ת, יש תקלה זמנית. נסו שוב.",
    "ru": "Извините, временная ошибка. Попробуйте ещё раз.",
}
RESET_OK = "🔄 השיחה אופסה. · Диалог сброшен."

_LIMITER = guardrails.RateLimiter()


def _esc(s: str) -> str:
    return html.escape(s or "")


def render_answer(ans: Answer) -> str:
    """Render an :class:`Answer` to a Telegram HTML message (R6): body, then a
    citation footer, then the italic disclaimer. A refusal renders as body only."""
    parts = [_esc(ans.text)]
    if ans.citations:
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
    answer_fn = answer_fn or answer_mod.answer
    limiter = rate if rate is not None else _LIMITER

    if not guardrails.is_allowed(chat_id):
        return _esc(PRIVATE)
    lang = guardrails.detect_lang(text)
    if not limiter.allow(chat_id):
        return _esc(RATE_MSG[lang])
    return render_answer(answer_fn(text, lang))


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
        reply = build_reply(update.effective_chat.id, update.effective_message.text)
        await _send(update, reply)
    except Exception:  # noqa: BLE001 — never crash the process (§0 #6)
        lang = guardrails.detect_lang(getattr(update.effective_message, "text", "") or "")
        await _send(update, _esc(ERROR[lang]))


async def on_nontext(update, context) -> None:
    await _send(update, _esc(NONTEXT["he"]))  # can't detect language without text (§0 #8)


async def on_start(update, context) -> None:
    await _send(update, _esc(WELCOME))


async def on_help(update, context) -> None:
    await _send(update, _esc(WELCOME))


async def on_reset(update, context) -> None:
    from bot import session
    session.reset(update.effective_chat.id)
    await _send(update, _esc(RESET_OK))
