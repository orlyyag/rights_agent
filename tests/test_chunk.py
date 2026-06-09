"""chunk.py — section chunking, title+heading prefix, overlap, oversized splits."""
from __future__ import annotations

from ingest import chunk
from ingest.clean import CleanedDoc, Section


def _doc(sections, title="זכאות לדמי לידה", pageid=42, lang="he"):
    return CleanedDoc(
        pageid=pageid, title=title, url=f"https://kz/he/{title}",
        lang=lang, lastrevid=1, sections=sections,
    )


def test_emits_one_chunk_per_short_section_with_prefix():
    sections = [
        Section(heading="זכאות", level=2, text="פסקה ראשונה."),
        Section(heading="גובה התשלום", level=2, text="פסקה שנייה."),
    ]
    chunks = chunk.chunk_doc(_doc(sections))
    assert len(chunks) == 2
    assert chunks[0].text.startswith("זכאות לדמי לידה > זכאות\n\n")
    assert chunks[1].text.startswith("זכאות לדמי לידה > גובה התשלום\n\n")
    assert chunks[0].meta.section == "זכאות"
    assert chunks[0].id == "pipeline:he:42:0" and chunks[1].id == "pipeline:he:42:1"
    assert chunks[0].meta.source == "pipeline"


def test_lead_section_with_no_heading_uses_title_only_prefix():
    sections = [Section(heading="", level=0, text="פסקת לידה.")]
    chunks = chunk.chunk_doc(_doc(sections))
    assert chunks[0].text.startswith("זכאות לדמי לידה\n\n")
    assert chunks[0].meta.section == ""


def test_long_section_splits_into_multiple_chunks_with_overlap():
    paragraphs = [f"פסקה מספר {i}. " * 30 for i in range(10)]
    body = "\n\n".join(paragraphs)
    sections = [Section(heading="ז", level=2, text=body)]
    params = chunk.ChunkParams(target_tokens=120, overlap_tokens=20)
    chunks = chunk.chunk_doc(_doc(sections), params=params)
    assert len(chunks) >= 2
    # Adjacent chunks share at least one paragraph (overlap).
    shared_found = False
    for a, b in zip(chunks, chunks[1:]):
        a_paras = set(a.text.split("\n\n"))
        b_paras = set(b.text.split("\n\n"))
        shared = a_paras & b_paras - {""}
        if shared - {chunks[0].text.split("\n\n")[0]}:  # ignore the title prefix
            shared_found = True
            break
    assert shared_found, "expected overlap between adjacent chunks"


def test_oversized_paragraph_is_hard_split_not_dropped():
    """One giant paragraph that exceeds the budget should be split on sentence
    boundaries, then word-greedy as fallback. No content silently lost."""
    big = ("משפט ראשון מאוד ארוך. " * 50).strip()
    sections = [Section(heading="ז", level=2, text=big)]
    params = chunk.ChunkParams(target_tokens=80, overlap_tokens=10)
    chunks = chunk.chunk_doc(_doc(sections), params=params)
    assert len(chunks) >= 2
    # Reassembled content should contain every original sentence (approximate).
    reassembled = " ".join(c.text for c in chunks)
    assert reassembled.count("משפט ראשון מאוד ארוך") >= 50 - 2


def test_empty_section_is_skipped():
    sections = [
        Section(heading="ז", level=2, text="ממש תוכן"),
        Section(heading="ריק", level=2, text=""),
        Section(heading="גם זה", level=2, text="עוד תוכן"),
    ]
    chunks = chunk.chunk_doc(_doc(sections))
    assert {c.meta.section for c in chunks} == {"ז", "גם זה"}


def test_metadata_round_trip():
    sections = [Section(heading="ז", level=2, text="גוף הפסקה.")]
    chunks = chunk.chunk_doc(_doc(sections, title="כותרת", pageid=7, lang="ru"),
                              source="pipeline")
    c = chunks[0]
    assert c.meta.pageid == 7 and c.meta.lang == "ru"
    assert c.meta.title == "כותרת" and c.meta.lastrevid == 1
    assert c.meta.source == "pipeline"


def test_chunk_id_is_stable_across_runs():
    sections = [Section(heading="ז", level=2, text="גוף.")]
    a = chunk.chunk_doc(_doc(sections))[0]
    b = chunk.chunk_doc(_doc(sections))[0]
    assert a.id == b.id


def test_chunk_docs_flattens():
    docs = [_doc([Section(heading="א", level=2, text="ת")]),
            _doc([Section(heading="ב", level=2, text="ת")], pageid=99)]
    out = chunk.chunk_docs(docs)
    assert len(out) == 2
    assert {c.meta.pageid for c in out} == {42, 99}
