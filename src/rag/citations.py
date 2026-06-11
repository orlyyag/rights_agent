"""Citation language policy (R2 + decision 2026-06-11).

Hebrew and auto-language questions present **Hebrew** source links; Russian
questions present **Russian** links. When an answer used a chunk from the other
language (cross-lingual fallback, relax_filter, auto retrieval), the cited page
is mapped to its counterpart via MediaWiki ``langlinks``.

No counterpart / API failure → the ORIGINAL link is kept: every substantive
answer must attribute its real source (license + output guardrail), so a
wrong-language link beats a dropped one.

Lookups are cached for the process lifetime — repeat citations are free; a
cache entry of ``None`` means "no translation exists", so misses are cached too.
"""
from __future__ import annotations

from urllib.parse import quote

from schema import ChunkMeta

PAGE_URL = {
    "he": "https://www.kolzchut.org.il/he/{title}",
    "ru": "https://www.kolzchut.org.il/ru/{title}",
}

# (source_lang, pageid, target_lang) → (title, url) | None (= no translation)
_cache: dict[tuple[str, int, str], tuple[str, str] | None] = {}
_clients: dict[str, object] = {}


def desired_citation_lang(lang: str) -> str:
    """ru questions → ru links; he/auto/anything else → he links."""
    return "ru" if lang == "ru" else "he"


def _live_langlinks(meta: ChunkMeta) -> dict[str, str]:
    """Query the SOURCE page's wiki for its interlanguage links. Lazy import +
    per-lang client cache; tests monkeypatch this function."""
    from ingest.mediawiki import MediaWikiClient  # noqa: PLC0415 — keep serving path import-light

    client = _clients.get(meta.lang)
    if client is None:
        client = _clients[meta.lang] = MediaWikiClient(meta.lang)
    return client.langlinks(meta.pageid)


def _title_to_url(title: str, target: str) -> str:
    return PAGE_URL[target].format(title=quote(title.replace(" ", "_")))


def localize(meta: ChunkMeta, target: str) -> tuple[str, str]:
    """Return ``(title, url)`` for the cited page in ``target`` language.

    Same language → original. Different language → langlinks lookup (cached);
    missing translation or API failure → original.
    """
    if meta.lang == target or target not in PAGE_URL:
        return meta.title, meta.url
    key = (meta.lang, meta.pageid, target)
    if key not in _cache:
        try:
            title = (_live_langlinks(meta) or {}).get(target, "").strip()
        except Exception:  # noqa: BLE001 — a citation lookup must never break an answer
            return meta.title, meta.url   # transient failure: do NOT cache as "missing"
        _cache[key] = (title, _title_to_url(title, target)) if title else None
    found = _cache[key]
    return found if found else (meta.title, meta.url)
