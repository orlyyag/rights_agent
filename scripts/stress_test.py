"""Concurrency stress harness (§0 #5 capacity: the open-to-all demo).

Simulates N users hitting the bot at the same instant, through the REAL async
path PTB uses after the concurrency fix: concurrent handler dispatch →
``handlers.on_text`` → executor offload → ``build_reply`` (retrieve + generate).
Only the Telegram transport is faked.

    PYTHONPATH=.:src python scripts/stress_test.py            # live, 20 users
    PYTHONPATH=.:src python scripts/stress_test.py --fake     # no LLM, plumbing only
    PYTHONPATH=.:src python scripts/stress_test.py -n 30      # more users

Pass/fail: wall clock must be far below the serial estimate (N × mean latency)
and every user must get a rendered reply.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time

import config
from bot import handlers
from schema import Answer

QUESTIONS_PATH = "eval/golden_he.jsonl"


class _Msg:
    def __init__(self, text: str):
        self.text = text
        self.sent: str | None = None

    async def reply_text(self, text, **kw):
        self.sent = text


class _Chat:
    def __init__(self, cid: int):
        self.id = cid


class _Update:
    def __init__(self, cid: int, text: str):
        self.effective_message = _Msg(text)
        self.effective_chat = _Chat(cid)


class _Bot:
    async def send_chat_action(self, **kw):
        pass


class _Ctx:
    bot = _Bot()


def _load_questions(n: int) -> list[str]:
    qs = []
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item.get("category") == "in_scope":
                qs.append(item["question"])
    return [qs[i % len(qs)] for i in range(n)]


async def _run(n: int, fake: bool) -> int:
    config.ALLOWED_CHAT_IDS = frozenset()  # open-to-all, like the demo
    if fake:
        def _fa(q, lang, **kw):
            time.sleep(1.5)  # stands in for the ~7s LLM round-trip
            return Answer(text="ok", lang=lang, citations=[], disclaimer="")
        from rag import answer as answer_mod
        answer_mod.answer_default = _fa

    updates = [_Update(900_000 + i, q) for i, q in enumerate(_load_questions(n))]
    lat: dict[int, float] = {}

    async def one(i: int, up: _Update) -> None:
        t0 = time.monotonic()
        await handlers.on_text(up, _Ctx())
        lat[i] = time.monotonic() - t0

    t0 = time.monotonic()
    await asyncio.gather(*(one(i, u) for i, u in enumerate(updates)))
    wall = time.monotonic() - t0

    ok = [u for u in updates if u.effective_message.sent]
    errs = [u for u in updates if u.effective_message.sent
            and ("תקלה זמנית" in u.effective_message.sent
                 or "something went wrong" in u.effective_message.sent)]
    vals = sorted(lat.values())
    mean = statistics.mean(vals)
    p95 = vals[max(0, int(len(vals) * 0.95) - 1)]
    serial_est = mean * n

    print(f"mode={'fake' if fake else 'LIVE'}  users={n}")
    print(f"replies: {len(ok)}/{n} delivered, {len(errs)} error replies")
    print(f"per-user latency: mean={mean:.2f}s  median={vals[len(vals)//2]:.2f}s  "
          f"p95={p95:.2f}s  max={vals[-1]:.2f}s")
    print(f"wall clock: {wall:.2f}s   (serial estimate: {serial_est:.1f}s, "
          f"speedup ×{serial_est / wall:.1f})")
    passed = len(ok) == n and not errs and wall < serial_est / 3
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20, help="parallel users (default 20)")
    ap.add_argument("--fake", action="store_true", help="stub the LLM (free, plumbing only)")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_run(args.n, args.fake)))


if __name__ == "__main__":
    main()
