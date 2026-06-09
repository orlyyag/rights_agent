"""Per-chat in-memory session (Q7). Minimal for Tier-0; Tier-1 feeds the last
turns into the history-aware rewrite step (R5). Resets on restart — avoid mid-demo
restarts (Q7).
"""
from __future__ import annotations

from collections import defaultdict, deque

import config

_SESSIONS: dict[int, deque] = defaultdict(lambda: deque(maxlen=2 * config.MEMORY_TURNS))


def add_turn(chat_id: int, role: str, text: str) -> None:
    """Record a turn. ``role`` is "user" or "assistant"."""
    _SESSIONS[chat_id].append((role, text))


def history(chat_id: int) -> list[tuple[str, str]]:
    """Last ≤ 2*MEMORY_TURNS (role, text) pairs, oldest first."""
    return list(_SESSIONS[chat_id])


def reset(chat_id: int) -> None:
    _SESSIONS.pop(chat_id, None)
