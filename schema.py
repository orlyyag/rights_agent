"""Shared data contracts — frozen Day-1 seam #3 (PLAN.md §21, R9).

``ChunkMeta`` is the Chroma metadata schema that BOTH lanes depend on: ingest
(``index.py``) writes it, the retriever reads it back. All fields are scalar so
the dict is valid Chroma metadata. Freeze this before either lane builds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, TypedDict

#: The frozen metadata key set stored on every chunk (§5.2, §0 #1/#2).
CHUNK_META_FIELDS = ("pageid", "title", "url", "lang", "section", "lastrevid", "source")


@dataclass(frozen=True)
class ChunkMeta:
    """Per-chunk metadata. Scalar-only → valid Chroma metadata."""

    pageid: int
    title: str
    url: str
    lang: str          # "he" | "ru"
    section: str       # heading path; also prepended to the chunk text (Q3)
    lastrevid: int
    source: str        # "corpus" | "pipeline" (§0 #2)

    def to_metadata(self) -> dict[str, Any]:
        """Chroma-ready dict (all scalars)."""
        return asdict(self)

    @classmethod
    def from_metadata(cls, d: dict[str, Any]) -> "ChunkMeta":
        return cls(**{k: d[k] for k in CHUNK_META_FIELDS})


@dataclass
class Chunk:
    """A chunk ready to embed + upsert."""

    id: str            # stable id, see chunk_id()
    text: str          # "Title > Section\n\n<body>" — title+heading prefix (Q3)
    meta: ChunkMeta


class RawDoc(TypedDict):
    """``data/raw/{lang}/{pageid}.json`` — decouples fetch from index (§5.3)."""

    pageid: int
    title: str
    url: str
    lang: str
    lastrevid: int
    html: str
    fetched_at: str


def chunk_id(source: str, lang: str, pageid: int, idx: int) -> str:
    """Stable, collision-free chunk id so re-index upserts (not duplicates)."""
    return f"{source}:{lang}:{pageid}:{idx}"


# ── Live-path contracts (shared by rag + bot) ───────────────────────────────
@dataclass(frozen=True)
class Citation:
    """A source link shown in the answer footer (R6)."""

    title: str
    url: str


@dataclass
class RetrievedChunk:
    """A chunk returned by the retriever, with its similarity score."""

    text: str
    meta: ChunkMeta
    score: float       # cosine similarity, ~[0, 1] (higher = closer)


@dataclass
class Answer:
    """The agent's result. The bot renders this to HTML (R6); it never builds answer text itself."""

    text: str
    lang: str          # "he" | "ru"
    citations: list[Citation]
    disclaimer: str
    refused: bool = False
