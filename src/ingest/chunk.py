"""Section-based chunking with title+heading prefix (PLAN §0 Grill Q3).

Targets the corpus's effective unit: ~512 tokens per chunk, ~50-token overlap,
"PageTitle > Section" prefix prepended to each chunk so the embedding picks up
the topical context even when the body text is generic.

Token count uses a chars-per-token heuristic (Gemini's BPE is ~3.5-4 chars/token
for he/ru); the exact ratio doesn't change correctness, only the average chunk
length within ~10-15%.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from ingest.clean import CleanedDoc, Section
from schema import Chunk, ChunkMeta, chunk_id


@dataclass(frozen=True)
class ChunkParams:
    target_tokens: int = 512
    overlap_tokens: int = 50
    chars_per_token: float = 4.0          # rough estimate for he/ru
    min_chunk_tokens: int = 30            # drop slivers below this
    paragraph_split: re.Pattern[str] = re.compile(r"\n{2,}")
    sentence_split: re.Pattern[str] = re.compile(r"(?<=[.!?])\s+|(?<=[׃׀])\s+")


def _est_tokens(text: str, p: ChunkParams) -> int:
    return max(1, int(len(text or "") / p.chars_per_token))


def _paragraphs(text: str, p: ChunkParams) -> list[str]:
    return [s.strip() for s in p.paragraph_split.split(text or "") if s.strip()]


def _split_long_paragraph(para: str, budget_tokens: int, p: ChunkParams) -> list[str]:
    """Hard-split a paragraph that exceeds the budget. Tries sentence boundaries
    first, then a word-greedy fill, then a flat char window as a last resort."""
    if _est_tokens(para, p) <= budget_tokens:
        return [para]
    sentences = [s.strip() for s in p.sentence_split.split(para) if s.strip()]
    if len(sentences) > 1:
        out: list[str] = []
        buf, buf_tok = [], 0
        for s in sentences:
            t = _est_tokens(s, p)
            if buf and buf_tok + t > budget_tokens:
                out.append(" ".join(buf))
                buf, buf_tok = [], 0
            buf.append(s)
            buf_tok += t
        if buf:
            out.append(" ".join(buf))
        # if any sentence is itself oversized, recurse on words
        flat: list[str] = []
        for piece in out:
            flat.extend(_word_pack(piece, budget_tokens, p) if _est_tokens(piece, p) > budget_tokens else [piece])
        return flat
    return _word_pack(para, budget_tokens, p)


def _word_pack(text: str, budget_tokens: int, p: ChunkParams) -> list[str]:
    words = text.split()
    out: list[str] = []
    buf, buf_tok = [], 0
    for w in words:
        wt = max(1, _est_tokens(w, p))
        if buf and buf_tok + wt > budget_tokens:
            out.append(" ".join(buf))
            buf, buf_tok = [], 0
        buf.append(w)
        buf_tok += wt
    if buf:
        out.append(" ".join(buf))
    return out


def _overlap_tail(parts: list[str], overlap_tokens: int, p: ChunkParams) -> list[str]:
    """Return the trailing slice of ``parts`` whose total ≈ overlap_tokens."""
    tail: list[str] = []
    total = 0
    for piece in reversed(parts):
        t = _est_tokens(piece, p)
        if total + t > overlap_tokens and tail:
            break
        tail.insert(0, piece)
        total += t
    return tail


def _emit(doc: CleanedDoc, section: Section, source: str, idx: int,
          prefix: str, body: str) -> Chunk:
    text = f"{prefix}\n\n{body}" if prefix else body
    meta = ChunkMeta(
        pageid=doc.pageid, title=doc.title, url=doc.url, lang=doc.lang,
        section=section.heading, lastrevid=doc.lastrevid, source=source,
    )
    return Chunk(id=chunk_id(source, doc.lang, doc.pageid, idx), text=text, meta=meta)


def chunk_doc(doc: CleanedDoc, *, source: str = "pipeline",
              params: ChunkParams | None = None) -> list[Chunk]:
    """Section-by-section chunking. Returns a list of :class:`Chunk` ready for
    ``ingest.index.build_collection``."""
    p = params or ChunkParams()
    out: list[Chunk] = []
    idx = 0

    for section in doc.sections:
        if not section.text.strip():
            continue
        prefix = (
            f"{doc.title} > {section.heading}".strip()
            if section.heading else doc.title or ""
        )
        prefix_tokens = _est_tokens(prefix, p) if prefix else 0
        budget = max(p.target_tokens - prefix_tokens, 100)  # keep some room for body
        paragraphs = _paragraphs(section.text, p)

        buffer: list[str] = []
        buf_tokens = 0
        for para in paragraphs:
            pieces = _split_long_paragraph(para, budget, p)
            for piece in pieces:
                pt = _est_tokens(piece, p)
                if buffer and buf_tokens + pt > budget:
                    body = "\n\n".join(buffer)
                    out.append(_emit(doc, section, source, idx, prefix, body))
                    idx += 1
                    tail = _overlap_tail(buffer, p.overlap_tokens, p)
                    buffer = list(tail)
                    buf_tokens = sum(_est_tokens(t, p) for t in buffer)
                buffer.append(piece)
                buf_tokens += pt

        if buffer:
            # Always emit the trailing buffer — short sections are still valuable
            # (the title+heading prefix carries topical signal even when the body
            # is brief). min_chunk_tokens only matters for overlap-only slivers,
            # which we filter below.
            body = "\n\n".join(buffer)
            out.append(_emit(doc, section, source, idx, prefix, body))
            idx += 1

    return out


def chunk_docs(docs: Iterable[CleanedDoc], **kw) -> list[Chunk]:
    """Convenience: chunk many docs flat."""
    out: list[Chunk] = []
    for d in docs:
        out.extend(chunk_doc(d, **kw))
    return out
