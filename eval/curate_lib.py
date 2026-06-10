"""Curation research CLI for fixing the golden set.

Backed by ``data/curate_text_he.jsonl`` (one cleaned page per line:
``{pageid, title, url, text}``), which mirrors the exact pages the bot indexes
(``data/raw/he/*.json`` → ``ingest.clean``). Use this to (a) read the full text
of a candidate KolZchut page and (b) find the canonical page for a question.

Usage (from repo root):
    python eval/curate_lib.py page 9247
    python eval/curate_lib.py search "תאונת עבודה עובדת משק בית מעסיק"
    python eval/curate_lib.py contains 9247 "תאונת עבודה היא תאונה שאירעה"   # verify a quote is on the page
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

CACHE = Path("data/curate_text_he.jsonl")
_WORD = re.compile(r"[֐-׿\w]+", re.UNICODE)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    return [json.loads(l) for l in CACHE.open(encoding="utf-8") if l.strip()]


def _by_id() -> dict[str, dict]:
    return {r["pageid"]: r for r in _load()}


def page(pageid: str) -> None:
    r = _by_id().get(str(pageid))
    if not r:
        print(f"[not in indexed corpus] pageid={pageid}")
        return
    print(f"PAGEID: {r['pageid']}\nTITLE: {r['title']}\nURL: {r['url']}\n{'-'*80}")
    print(r["text"])


def contains(pageid: str, quote: str) -> None:
    r = _by_id().get(str(pageid))
    if not r:
        print(f"[not in corpus] pageid={pageid}")
        return
    ok = _norm(quote) in _norm(r["text"])
    print(f"{'FOUND' if ok else 'NOT FOUND'} on page {pageid} ({r['title']})")


def search(query: str, k: int = 12) -> None:
    q_tokens = [t for t in _WORD.findall(query) if len(t) > 1]
    if not q_tokens:
        print("empty query")
        return
    q_set = set(q_tokens)
    scored = []
    for r in _load():
        title_tokens = set(_WORD.findall(r["title"]))
        text_tokens = _WORD.findall(r["text"])
        text_set = set(text_tokens)
        # score: title matches weighted heavily; body coverage of distinct query terms
        title_hit = len(q_set & title_tokens) * 5
        body_hit = len(q_set & text_set)
        # term frequency bonus (capped) so on-topic pages float up
        tf = sum(min(text_tokens.count(t), 4) for t in q_set)
        score = title_hit + body_hit + 0.25 * tf
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    for score, r in scored[:k]:
        snippet = _norm(r["text"])[:160]
        print(f"[{score:6.1f}] {r['pageid']:>6}  {r['title']}")
        print(f"          {snippet}")


def _main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "page":
        page(sys.argv[2])
    elif cmd == "search":
        search(" ".join(sys.argv[2:]))
    elif cmd == "contains":
        contains(sys.argv[2], " ".join(sys.argv[3:]))
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    _main()
