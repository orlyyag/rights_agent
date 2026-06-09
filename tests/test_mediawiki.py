"""MediaWiki client — throttle, retry, manifest pagination — LLM-free + network-free."""
from __future__ import annotations

import json

import pytest

from ingest import mediawiki


class _FakeResp:
    def __init__(self, body=None, status=200, headers=None):
        self._body = body if body is not None else {}
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self._body if not isinstance(self._body, str) else json.loads(self._body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise mediawiki.MediaWikiError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        return self.responses.pop(0)


def _client(session, **kw):
    sleep_calls = kw.pop("sleep_calls", None)
    if sleep_calls is not None:
        kw["sleep_fn"] = sleep_calls.append
    kw.setdefault("now_fn", lambda: 0.0)
    kw.setdefault("request_interval_s", 0)
    return mediawiki.MediaWikiClient("he", session=session, **kw)


def test_throttle_blocks_when_under_interval():
    waited = []
    clock = [0.0]
    s = _FakeSession([_FakeResp({"query": {"pages": {}}})])
    c = mediawiki.MediaWikiClient(
        "he", session=s, sleep_fn=waited.append, now_fn=lambda: clock[0],
        request_interval_s=1.0,
    )
    c._last_call_t = 0.0  # pretend we just called
    clock[0] = 0.3
    c._get({"action": "x"})
    assert waited and waited[0] == pytest.approx(0.7, abs=1e-6)


def test_retry_on_429_then_succeeds():
    sleeps = []
    s = _FakeSession([
        _FakeResp(status=429, headers={"Retry-After": "2"}),
        _FakeResp({"query": {"pages": {}}}),
    ])
    c = _client(s, sleep_calls=sleeps)
    out = c._get({"action": "x"})
    assert out == {"query": {"pages": {}}}
    assert 2 in sleeps  # honored Retry-After


def test_retry_on_maxlag_then_succeeds():
    s = _FakeSession([
        _FakeResp({"error": {"code": "maxlag", "info": "lag 3s"}}),
        _FakeResp({"query": {"pages": {}}}),
    ])
    c = _client(s)
    assert c._get({"action": "x"}) == {"query": {"pages": {}}}


def test_non_maxlag_error_raises_immediately():
    s = _FakeSession([_FakeResp({"error": {"code": "badparam", "info": "no"}})])
    c = _client(s)
    with pytest.raises(mediawiki.MediaWikiError):
        c._get({"action": "x"})


def test_manifest_iterates_pages_and_paginates():
    page1 = {"query": {"pages": {
                "1": {"pageid": 1, "title": "A", "lastrevid": 100, "fullurl": "u1"},
                "2": {"pageid": 2, "title": "B", "lastrevid": 101, "fullurl": "u2"}}},
             "continue": {"gapcontinue": "X"}}
    page2 = {"query": {"pages": {
                "3": {"pageid": 3, "title": "C", "lastrevid": 102, "fullurl": "u3"}}}}
    s = _FakeSession([_FakeResp(page1), _FakeResp(page2)])
    c = _client(s)
    items = list(c.manifest())
    assert [it.pageid for it in items] == [1, 2, 3]
    assert items[0].url == "u1"
    # Second call carries the continuation token.
    assert s.calls[1]["params"]["gapcontinue"] == "X"


def test_manifest_skips_missing_entries():
    body = {"query": {"pages": {"-1": {"missing": ""},
                                "5": {"pageid": 5, "title": "T", "lastrevid": 1, "fullurl": "u"}}}}
    s = _FakeSession([_FakeResp(body)])
    c = _client(s)
    assert [it.pageid for it in c.manifest()] == [5]


def test_parse_returns_html_and_title():
    body = {"parse": {"pageid": 9, "title": "X", "displaytitle": "X*",
                      "text": {"*": "<p>hi</p>"}}}
    s = _FakeSession([_FakeResp(body)])
    c = _client(s)
    out = c.parse(9)
    assert out == {"pageid": 9, "title": "X", "displaytitle": "X*", "html": "<p>hi</p>"}


def test_langlinks_returns_lang_to_title_map():
    body = {"query": {"pages": {"9": {"langlinks": [
        {"lang": "ru", "*": "Title-ru"},
        {"lang": "ar", "*": "Title-ar"}]}}}}
    s = _FakeSession([_FakeResp(body)])
    c = _client(s)
    assert c.langlinks(9) == {"ru": "Title-ru", "ar": "Title-ar"}
