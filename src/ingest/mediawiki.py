"""Thin MediaWiki client for the Kol Zchut wikis (he + ru).

WAF-safe by design (PLAN §5.3 "etiquette"):
- descriptive User-Agent (their CDN blocks default bot UAs — observed)
- ~1 req/s throttle, configurable
- ``maxlag`` parameter so we back off when the API is under load
- exponential-backoff retry on 429 / 503 / network errors

Three operations:
- :meth:`manifest`   — cheap full-page list with ``pageid, title, lastrevid, url``
  (used by ``acquire.py`` for the diff that powers first crawl + incremental sync)
- :meth:`parse`      — rendered HTML for one page (``action=parse&prop=text``)
- :meth:`langlinks`  — interlanguage links for one page (R2 cross-lingual)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterator

import requests

# Per-language endpoints (verified live in PLAN §5.1).
ENDPOINTS = {
    "he": "https://www.kolzchut.org.il/w/api.php",
    "ru": "https://www.kolzchut.org.il/w/ru/api.php",
}

DEFAULT_UA = (
    "KolZchutRightsAgent/0.1 (final project; rights-info bot grounded in Kol Zchut; "
    "contact: yanyag@gmail.com)"
)


class MediaWikiError(RuntimeError):
    """Raised when the API returns an error after retries."""


@dataclass(frozen=True)
class PageInfo:
    """One entry in the manifest — enough to diff and request the page later."""

    pageid: int
    title: str
    lastrevid: int
    url: str
    ns: int = 0


class MediaWikiClient:
    """Polite MediaWiki client. Use one instance per language."""

    def __init__(self, lang: str, *, endpoint: str | None = None,
                 user_agent: str = DEFAULT_UA, request_interval_s: float = 1.0,
                 maxlag: int = 5, max_retries: int = 4, timeout_s: float = 30.0,
                 session: requests.Session | None = None,
                 sleep_fn=time.sleep, now_fn=time.monotonic) -> None:
        if lang not in ENDPOINTS and endpoint is None:
            raise ValueError(f"unknown lang {lang!r}; pass endpoint= to override")
        self.lang = lang
        self.endpoint = endpoint or ENDPOINTS[lang]
        self.request_interval_s = request_interval_s
        self.maxlag = maxlag
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        self._sleep = sleep_fn
        self._now = now_fn
        self._last_call_t = 0.0
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    # ── HTTP plumbing ────────────────────────────────────────────────────────
    def _throttle(self) -> None:
        wait = self.request_interval_s - (self._now() - self._last_call_t)
        if wait > 0:
            self._sleep(wait)

    def _get(self, params: dict[str, Any]) -> dict:
        """One GET with throttle + retry on transient errors / API ``maxlag``."""
        params = {"format": "json", "maxlag": self.maxlag, **params}
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            self._last_call_t = self._now()
            try:
                resp = self.session.get(self.endpoint, params=params, timeout=self.timeout_s)
            except requests.RequestException as exc:
                last_exc = exc
                self._sleep(2 ** attempt)
                continue
            if resp.status_code in (429, 503):
                last_exc = MediaWikiError(f"HTTP {resp.status_code}")
                # honor Retry-After if the server sets it, else exponential
                retry_after = resp.headers.get("Retry-After")
                self._sleep(int(retry_after) if (retry_after or "").isdigit() else 2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "error" in data:
                code = data["error"].get("code", "")
                if code == "maxlag":
                    last_exc = MediaWikiError(data["error"].get("info", "maxlag"))
                    self._sleep(2 ** attempt)
                    continue
                raise MediaWikiError(f"{code}: {data['error'].get('info', '')}")
            return data
        raise MediaWikiError(f"{params!r} failed after {self.max_retries + 1} attempts: {last_exc}")

    # ── Public operations ────────────────────────────────────────────────────
    def manifest(self, *, batch_size: int = 500,
                 namespace: int = 0) -> Iterator[PageInfo]:
        """Yield every non-redirect content page (PLAN §5.2):
        ``generator=allpages | prop=info | inprop=url | gapfilterredir=nonredirects``.

        Pagination is handled via ``gapcontinue``. The generator finishes when the
        API stops returning a continuation token.
        """
        cont: dict[str, str] = {}
        while True:
            params = {
                "action": "query",
                "generator": "allpages",
                "gaplimit": batch_size,
                "gapnamespace": namespace,
                "gapfilterredir": "nonredirects",
                "prop": "info",
                "inprop": "url",
                **cont,
            }
            data = self._get(params)
            pages = (data.get("query") or {}).get("pages") or {}
            for raw in pages.values():
                if "pageid" not in raw:  # skip "missing" pages defensively
                    continue
                yield PageInfo(
                    pageid=int(raw["pageid"]),
                    title=str(raw.get("title", "")),
                    lastrevid=int(raw.get("lastrevid") or 0),
                    url=str(raw.get("fullurl") or raw.get("canonicalurl") or ""),
                    ns=int(raw.get("ns") or 0),
                )
            cont = (data.get("continue") or {})
            if not cont:
                return

    def parse(self, pageid: int) -> dict[str, Any]:
        """Return ``{pageid, title, html, displaytitle}`` from ``action=parse``."""
        data = self._get({
            "action": "parse",
            "pageid": pageid,
            "prop": "text|displaytitle",
            "redirects": 1,
        })
        p = data.get("parse") or {}
        return {
            "pageid": int(p.get("pageid", pageid)),
            "title": p.get("title", ""),
            "displaytitle": p.get("displaytitle", ""),
            "html": (p.get("text") or {}).get("*", ""),
        }

    def langlinks(self, pageid: int) -> dict[str, str]:
        """Return ``{lang_code: title_in_that_lang}`` for cross-lingual mapping (R2)."""
        data = self._get({
            "action": "query",
            "pageids": pageid,
            "prop": "langlinks",
            "lllimit": "max",
        })
        pages = (data.get("query") or {}).get("pages") or {}
        page = pages.get(str(pageid)) or next(iter(pages.values()), {})
        return {ll["lang"]: ll.get("*", "") for ll in (page.get("langlinks") or [])}
