"""HTML → structured clean text + tables→Markdown (PLAN §5.2, R1).

R1 is the silent-failure risk: the official corpus *flattened* tables (so benefit
amounts came out as prose). Our pipeline must preserve numeric tables — converting
``<table>`` to a Markdown table keeps the numbers, headers, and alignment that the
LLM can quote verbatim with no hallucination room.

Output: :class:`CleanedDoc` — a list of :class:`Section` objects (h1/h2/h3
boundaries), each with a heading + the markdown-rendered body. ``chunk.py``
consumes this directly; section-based chunking is Q3 in PLAN.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from bs4 import BeautifulSoup, NavigableString, Tag

# Wikitable chrome / nav junk we never want in our chunks.
_DROP_SELECTORS = (
    "script",
    "style",
    ".mw-editsection",          # edit links
    ".mw-jump-link",             # skip-to-content
    ".toc",                      # table of contents (we keep headings ourselves)
    ".navbox",                   # navigation boxes
    ".infobox",                  # right-side infoboxes (KZ uses for status badges)
    ".printfooter",
    ".mw-empty-elt",
    ".article-source",           # KZ "source" sidebar
    ".article-meta",             # KZ metadata block
    ".reference",                # footnote markers
    ".error",
    ".mw-references-wrap",       # bottom references
    ".collapsible-content",      # collapsed bits hidden by default in KZ skin
    "table.metadata",
    "div.metadata",
)

# Tags whose text should NOT cross paragraph boundaries (kept as inline runs).
_INLINE_TAGS = {"a", "span", "b", "i", "em", "strong", "u", "small", "sub", "sup", "code", "br"}

_HEADING_TAGS = {"h1", "h2", "h3", "h4"}


@dataclass(frozen=True)
class Section:
    heading: str         # "" for the pre-heading lead
    level: int           # 0 (lead), 1, 2, 3, 4
    text: str            # markdown-mixed body — paragraphs + tables


@dataclass
class CleanedDoc:
    pageid: int
    title: str
    url: str
    lang: str
    lastrevid: int
    sections: list[Section] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return sum(len(s.text) for s in self.sections)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _strip(text: str) -> str:
    """Collapse whitespace runs and trim. Preserves newlines."""
    lines = []
    for line in (text or "").split("\n"):
        compressed = " ".join(line.split())
        lines.append(compressed)
    out = "\n".join(lines)
    # Collapse 3+ blank lines into 2 (paragraph break).
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out.strip()


def _table_to_markdown(table: Tag) -> str:
    """Convert ``<table>`` to a GitHub-flavored markdown table.

    Numbers preserved exactly. If the table has no rows or only one column we
    fall back to bullets (renders better than a broken markdown table)."""
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        rows.append([" ".join(c.get_text(" ", strip=True).split()) for c in cells])
    if not rows:
        return ""
    n_cols = max(len(r) for r in rows)
    if n_cols <= 1:
        return "\n".join(f"• {r[0]}" for r in rows if r)
    # Pad short rows so the markdown table is well-formed.
    rows = [r + [""] * (n_cols - len(r)) for r in rows]
    # Escape pipes inside cells so they don't break the row split.
    rows = [[c.replace("|", "\\|") for c in r] for r in rows]
    header, *body = rows
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * n_cols) + "|"]
    for r in body:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _block_text(node: Tag) -> str:
    """Render a block-level element's text, preserving paragraph breaks."""
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name.lower() if child.name else ""
        if name in _INLINE_TAGS:
            parts.append(child.get_text(" ", strip=False))
        elif name == "li":
            parts.append("\n• " + child.get_text(" ", strip=True))
        elif name == "br":
            parts.append("\n")
        else:
            parts.append("\n" + child.get_text(" ", strip=True) + "\n")
    return _strip("".join(parts))


def _heading_level(tag: Tag) -> int:
    return int(tag.name[1])  # h1 → 1, h2 → 2, …


def _section_break_text(buf: list[str]) -> str:
    return _strip("\n\n".join(s for s in buf if s.strip()))


# ── Main entrypoint ──────────────────────────────────────────────────────────
def clean(raw: dict[str, Any]) -> CleanedDoc:
    """Take a :data:`acquire.RawDoc` (from ``data/raw/{lang}/{pageid}.json``) and
    return a :class:`CleanedDoc` with text + markdown tables, sectioned by heading."""
    soup = BeautifulSoup(raw.get("html") or "", "html.parser")

    # Strip the chrome before any walk so it can't bleed into a section's text.
    for sel in _DROP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    # The KZ template wraps content in <div class="mw-parser-output"> — descend.
    container = soup.select_one(".mw-parser-output") or soup.body or soup

    sections: list[Section] = []
    current_heading = ""
    current_level = 0
    buffer: list[str] = []

    def flush() -> None:
        text = _section_break_text(buffer)
        if text or current_heading:
            sections.append(Section(heading=current_heading, level=current_level, text=text))
        buffer.clear()

    for el in container.children:
        if isinstance(el, NavigableString):
            txt = str(el).strip()
            if txt:
                buffer.append(txt)
            continue
        if not isinstance(el, Tag) or not el.name:
            continue
        name = el.name.lower()
        if name in _HEADING_TAGS:
            flush()
            current_heading = el.get_text(" ", strip=True)
            current_level = _heading_level(el)
        elif name == "table":
            md = _table_to_markdown(el)
            if md:
                buffer.append(md)
        elif name in ("p", "div", "ul", "ol", "dl", "blockquote", "pre"):
            txt = _block_text(el) if name == "div" else el.get_text(" ", strip=True)
            if name in ("ul", "ol"):
                items = [li.get_text(" ", strip=True) for li in el.find_all("li", recursive=False)]
                txt = "\n".join(f"• {it}" for it in items if it)
            if txt:
                buffer.append(_strip(txt))
        # Silently skip everything else (figure, hr, etc.).
    flush()

    return CleanedDoc(
        pageid=int(raw.get("pageid", 0)),
        title=str(raw.get("title", "")),
        url=str(raw.get("url", "")),
        lang=str(raw.get("lang", "")),
        lastrevid=int(raw.get("lastrevid", 0)),
        sections=[s for s in sections if s.text or s.heading],
    )


def cleaned_to_iter(docs: Iterable[CleanedDoc]) -> Iterable[CleanedDoc]:
    """Pass-through helper so chunk.py can pipeline clean → chunk lazily."""
    yield from docs
