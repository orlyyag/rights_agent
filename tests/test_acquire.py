"""acquire.py — manifest diff, raw-layer IO, resumable orchestrator (LLM-free)."""
from __future__ import annotations

import json
from pathlib import Path

import config
from ingest import acquire
from ingest.mediawiki import PageInfo


def _redirect_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "MANIFEST_DIR", tmp_path / "manifest")


def test_diff_manifest_classifies_added_changed_deleted():
    stored = {"1": 100, "2": 100, "3": 100}
    current = [
        PageInfo(pageid=2, title="b", lastrevid=100, url="u"),
        PageInfo(pageid=3, title="c", lastrevid=101, url="u"),   # changed
        PageInfo(pageid=4, title="d", lastrevid=100, url="u"),   # added
    ]
    d = acquire.diff_manifest(stored, current)
    assert [p.pageid for p in d.added] == [4]
    assert [p.pageid for p in d.changed] == [3]
    assert d.deleted == [1]
    assert {p.pageid for p in d.to_fetch} == {3, 4}


def test_manifest_persists_atomically(monkeypatch, tmp_path):
    _redirect_paths(monkeypatch, tmp_path)
    acquire.save_manifest("he", {"1": 10, "2": 20})
    assert acquire.load_manifest("he") == {"1": 10, "2": 20}


def test_load_manifest_recovers_from_corrupt_file(monkeypatch, tmp_path):
    _redirect_paths(monkeypatch, tmp_path)
    p = acquire.manifest_path("he")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not json", encoding="utf-8")
    assert acquire.load_manifest("he") == {}


def test_write_raw_round_trip(monkeypatch, tmp_path):
    _redirect_paths(monkeypatch, tmp_path)
    info = PageInfo(pageid=99, title="X", lastrevid=42, url="https://kz/he/X")
    p = acquire.write_raw("he", info, "<p>hi</p>", now_fn=lambda: 1_700_000_000.0)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["pageid"] == 99 and data["lang"] == "he"
    assert data["html"] == "<p>hi</p>" and data["lastrevid"] == 42
    assert data["fetched_at"].endswith("Z")
    rows = list(acquire.iter_raw("he"))
    assert len(rows) == 1 and rows[0]["pageid"] == 99


class _FakeClient:
    """Minimal stand-in for MediaWikiClient: enumerates a fixed manifest, returns
    canned HTML on parse()."""

    def __init__(self, pages, htmls=None):
        self.pages = pages
        self.htmls = htmls or {p.pageid: f"<p>{p.title}</p>" for p in pages}
        self.parsed = []

    def manifest(self, **kw):
        yield from self.pages

    def parse(self, pageid: int):
        self.parsed.append(pageid)
        return {"pageid": pageid, "html": self.htmls[pageid], "title": "", "displaytitle": ""}


def test_acquire_full_first_run_fetches_everything(monkeypatch, tmp_path):
    _redirect_paths(monkeypatch, tmp_path)
    pages = [
        PageInfo(pageid=1, title="A", lastrevid=10, url="u1"),
        PageInfo(pageid=2, title="B", lastrevid=20, url="u2"),
    ]
    client = _FakeClient(pages)
    d = acquire.acquire("he", client=client, on_fetch=lambda *a: None)
    assert client.parsed == [1, 2]
    assert acquire.load_manifest("he") == {"1": 10, "2": 20}
    assert acquire.raw_path("he", 1).exists() and acquire.raw_path("he", 2).exists()
    assert d.deleted == []


def test_acquire_is_resumable_after_partial_crash(monkeypatch, tmp_path):
    """Simulate a crash mid-fetch: page 1 wrote, page 2 didn't. Re-run should fetch
    only page 2 (NOT page 1) on the next pass."""
    _redirect_paths(monkeypatch, tmp_path)
    pages = [
        PageInfo(pageid=1, title="A", lastrevid=10, url="u1"),
        PageInfo(pageid=2, title="B", lastrevid=20, url="u2"),
    ]

    # Pretend page 1 was successfully fetched + manifest-recorded before the crash:
    acquire.write_raw("he", pages[0], "<p>A</p>")
    acquire.save_manifest("he", {"1": 10})

    # On the next pass, only page 2 should be parsed.
    client = _FakeClient(pages)
    acquire.acquire("he", client=client, on_fetch=lambda *a: None)
    assert client.parsed == [2]
    assert acquire.load_manifest("he") == {"1": 10, "2": 20}


def test_acquire_deletes_removed_pages(monkeypatch, tmp_path):
    _redirect_paths(monkeypatch, tmp_path)
    # Page 1 used to exist; the live wiki no longer lists it.
    acquire.write_raw("he", PageInfo(pageid=1, title="A", lastrevid=10, url="u"), "<p>old</p>")
    acquire.save_manifest("he", {"1": 10})

    client = _FakeClient([PageInfo(pageid=2, title="B", lastrevid=20, url="u2")])
    d = acquire.acquire("he", client=client, on_fetch=lambda *a: None)
    assert d.deleted == [1]
    assert not acquire.raw_path("he", 1).exists()
    assert acquire.load_manifest("he") == {"2": 20}


def test_acquire_manifest_limit_caps_enumeration(monkeypatch, tmp_path):
    _redirect_paths(monkeypatch, tmp_path)
    pages = [PageInfo(pageid=i, title=f"P{i}", lastrevid=i, url="u") for i in range(1, 8)]
    client = _FakeClient(pages)
    acquire.acquire("he", client=client, manifest_limit=3, on_fetch=lambda *a: None)
    assert client.parsed == [1, 2, 3]
