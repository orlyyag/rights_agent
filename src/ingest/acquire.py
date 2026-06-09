"""Manifest-diff fetch into a per-page raw layer (PLAN §5.2, §0 #7).

Decouples *fetch* (this module) from *index* (clean→chunk→embed), so re-indexing
never re-crawls Kol Zchut. Resumable + idempotent — safe to Ctrl-C and rerun;
the next invocation diffs against the on-disk manifest and only fetches pages
that are missing or whose ``lastrevid`` changed.

Layout:
- ``data/manifest/{lang}.json`` — last-seen ``{pageid → lastrevid}``
- ``data/raw/{lang}/{pageid}.json`` — per-page snapshot ``RawDoc``
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import config
from ingest.mediawiki import MediaWikiClient, PageInfo


# ── Paths ────────────────────────────────────────────────────────────────────
def raw_dir(lang: str) -> Path:
    return config.RAW_DIR / lang


def manifest_path(lang: str) -> Path:
    return config.MANIFEST_DIR / f"{lang}.json"


def raw_path(lang: str, pageid: int) -> Path:
    return raw_dir(lang) / f"{pageid}.json"


# ── Manifest IO ──────────────────────────────────────────────────────────────
def load_manifest(lang: str) -> dict[str, int]:
    """``{pageid (str) → lastrevid (int)}``. Empty on first run."""
    p = manifest_path(lang)
    if not p.exists():
        return {}
    try:
        return {str(k): int(v) for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
    except (json.JSONDecodeError, ValueError):
        return {}


def save_manifest(lang: str, manifest: dict[str, int]) -> None:
    """Atomic write so a Ctrl-C mid-save never corrupts the manifest."""
    p = manifest_path(lang)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


# ── Diff ─────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Diff:
    """Plan for one sync cycle (PLAN §5.2)."""

    added: list[PageInfo]      # in current manifest, not in stored
    changed: list[PageInfo]    # lastrevid differs
    deleted: list[int]         # in stored, not in current

    @property
    def to_fetch(self) -> list[PageInfo]:
        return self.added + self.changed


def diff_manifest(stored: dict[str, int], current: Iterable[PageInfo]) -> Diff:
    added: list[PageInfo] = []
    changed: list[PageInfo] = []
    current_ids: set[str] = set()
    for p in current:
        pid = str(p.pageid)
        current_ids.add(pid)
        if pid not in stored:
            added.append(p)
        elif stored[pid] != p.lastrevid:
            changed.append(p)
    deleted = sorted(int(k) for k in stored.keys() - current_ids)
    return Diff(added=added, changed=changed, deleted=deleted)


# ── Raw layer ────────────────────────────────────────────────────────────────
def _now_iso(now_fn: Callable[[], float] = time.time) -> str:
    t = now_fn()
    g = time.gmtime(t)
    return f"{g.tm_year:04d}-{g.tm_mon:02d}-{g.tm_mday:02d}T{g.tm_hour:02d}:{g.tm_min:02d}:{g.tm_sec:02d}Z"


def write_raw(lang: str, info: PageInfo, html: str,
              *, now_fn: Callable[[], float] = time.time) -> Path:
    """Atomic per-page JSON write."""
    p = raw_path(lang, info.pageid)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pageid": info.pageid,
        "title": info.title,
        "url": info.url,
        "lang": lang,
        "lastrevid": info.lastrevid,
        "html": html,
        "fetched_at": _now_iso(now_fn),
    }
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
    return p


def delete_raw(lang: str, pageid: int) -> bool:
    """Remove a raw file (used when a page disappears from the wiki)."""
    p = raw_path(lang, pageid)
    if p.exists():
        p.unlink()
        return True
    return False


def iter_raw(lang: str):
    """Iterate the on-disk raw layer (used by clean/chunk/index)."""
    d = raw_dir(lang)
    if not d.exists():
        return
    for p in sorted(d.glob("*.json")):
        try:
            yield json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue


# ── Orchestrator ─────────────────────────────────────────────────────────────
def acquire(lang: str, *, client: MediaWikiClient | None = None,
            manifest_limit: int | None = None,
            on_fetch: Callable[[int, int, PageInfo], None] | None = None) -> Diff:
    """Pull the manifest, diff against stored, fetch what changed, persist atomically.

    Resumable by construction: if a fetch crashed last time, the raw file wasn't
    written → next manifest_diff still flags it as added/changed and we retry.
    The stored manifest is updated only after the successful fetch of each page,
    so partial progress sticks.

    ``manifest_limit`` caps how many pages we enumerate from the API (handy for the
    overnight small-validation run; ``None`` = full sweep).
    """
    client = client or MediaWikiClient(lang)
    stored = load_manifest(lang)

    current: list[PageInfo] = []
    for i, info in enumerate(client.manifest()):
        if manifest_limit is not None and i >= manifest_limit:
            break
        current.append(info)

    diff = diff_manifest(stored, current)
    to_fetch = diff.to_fetch
    total = len(to_fetch)
    if on_fetch is None:
        def on_fetch(i: int, n: int, p: PageInfo) -> None:
            if i == 0 or (i + 1) % 25 == 0 or i + 1 == n:
                print(f"  fetched {i+1}/{n}  pageid={p.pageid}  {p.title[:60]}",
                      flush=True)

    for i, info in enumerate(to_fetch):
        parsed = client.parse(info.pageid)
        write_raw(lang, info, parsed.get("html", ""))
        stored[str(info.pageid)] = info.lastrevid
        save_manifest(lang, stored)
        on_fetch(i, total, info)

    for pageid in diff.deleted:
        delete_raw(lang, pageid)
        stored.pop(str(pageid), None)
    if diff.deleted:
        save_manifest(lang, stored)
    return diff
