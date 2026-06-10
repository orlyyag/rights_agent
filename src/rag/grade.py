"""Batched ``grade_docs`` — the relevance gate per PLAN §0 #4 / R3 / R4.

ONE LLM call scores every candidate chunk for relevance to the question and
returns a per-chunk verdict plus an overall failure-mode label that the
re-retrieve transform reads to pick its move (terminology-broaden vs filter-relax).

R3: grade_docs is the *authoritative* refuse/scope gate; the cosine floor in
``retriever`` is only a lenient pre-filter. R4: one batched call (not N per-
chunk calls) keeps live latency in check.

Returns a :class:`GradeResult` that ``graph.py`` consumes to route the next step.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from rag import llm
from rag.llm import traceable
from schema import RetrievedChunk

# Failure modes the grader can label — drives the re-retrieve transform (R4).
FAILURE_NARROW_TERMINOLOGY = "narrow_terminology"   # query uses colloquial / wrong-language official terms
FAILURE_WRONG_TOPIC = "wrong_topic"                  # question genuinely off-topic for KZ
FAILURE_CROSS_LINGUAL_THIN = "cross_lingual_thin"    # ru-only topic, he-only sources (or vice versa)
FAILURE_OK = "ok"                                    # at least one strong hit kept

_VALID_FAILURES = {FAILURE_NARROW_TERMINOLOGY, FAILURE_WRONG_TOPIC,
                   FAILURE_CROSS_LINGUAL_THIN, FAILURE_OK}

_SYSTEM = (
    "You grade retrieved Kol Zchut paragraphs for relevance to a rights question. "
    "Respond with STRICT JSON ONLY (no prose, no markdown fences):\n"
    '{\n'
    '  "verdicts": [\n'
    '    {"id": <int>, "relevant": <bool>, "reason": "<one short phrase>"}, ...\n'
    '  ],\n'
    '  "overall": "ok" | "narrow_terminology" | "wrong_topic" | "cross_lingual_thin"\n'
    '}\n'
    "Use 'narrow_terminology' if candidates cover the topic but the question uses "
    "colloquial / wrong-language terms and a broader rewrite would help. "
    "Use 'cross_lingual_thin' if the question's language differs from the candidates' "
    "and the topic seems to exist mainly in the OTHER language. "
    "Use 'wrong_topic' only if the question is genuinely outside Israeli rights/benefits. "
    "Use 'ok' if at least one candidate is a strong hit."
)


@dataclass
class GradeResult:
    """One grade_docs call's verdict."""

    kept_indices: list[int]      # indices into the original chunks list, in order
    reasons: list[str]           # per-chunk one-phrase reasons (same length as input)
    overall_failure: str         # one of FAILURE_* above
    raw: dict                    # the parsed LLM JSON, for tracing / debugging

    @property
    def any_kept(self) -> bool:
        return bool(self.kept_indices)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(text: str) -> dict:
    """Robust JSON-from-LLM extraction. Returns {} on failure (caller handles)."""
    m = _JSON_RE.search(text or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    lines = [f"Question:\n{question}\n", "Candidates:"]
    for i, c in enumerate(chunks):
        snippet = (c.text or "").strip()
        if len(snippet) > 600:
            snippet = snippet[:600] + "…"
        lines.append(f"[{i}] (lang={c.meta.lang}) Title: {c.meta.title}\n     {snippet}")
    lines.append(
        "\nGrade each candidate and return the JSON described in the system prompt."
    )
    return "\n".join(lines)


@traceable(name="grade_chunks", run_type="chain")
def grade_chunks(question: str, chunks: list[RetrievedChunk],
                 *, max_keep: int = 5, generate_fn=None) -> GradeResult:
    """Run one batched grade call. Empty input → trivial result (no chunks kept,
    overall='ok' so the router treats it as a normal refuse path, NOT a retry)."""
    if not chunks:
        return GradeResult(kept_indices=[], reasons=[], overall_failure=FAILURE_OK, raw={})

    generate_fn = generate_fn or llm.generate
    out = generate_fn(_build_prompt(question, chunks), system=_SYSTEM)
    data = _parse_json(out)

    verdicts = data.get("verdicts") or []
    overall = data.get("overall") or FAILURE_OK
    if overall not in _VALID_FAILURES:
        overall = FAILURE_OK

    reasons = [""] * len(chunks)
    kept: list[int] = []
    for v in verdicts:
        try:
            i = int(v.get("id"))
        except (TypeError, ValueError):
            continue
        if not (0 <= i < len(chunks)):
            continue
        reasons[i] = str(v.get("reason") or "")
        if bool(v.get("relevant")):
            kept.append(i)

    # Stable ordering: original retrieval order; respect max_keep.
    kept = kept[:max_keep]
    return GradeResult(kept_indices=kept, reasons=reasons, overall_failure=overall, raw=data)
