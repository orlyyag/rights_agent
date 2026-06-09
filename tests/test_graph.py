"""Agent graph — routing + end-to-end with mocked primitives (LLM-free)."""
from __future__ import annotations

import config
from rag import answer as answer_mod
from rag import grade
from rag import graph
from rag import prompts
from rag import retriever
from schema import ChunkMeta, RetrievedChunk


def _rc(i=0, lang="he", title=None, url=None):
    return RetrievedChunk(
        text=f"body-{i}",
        meta=ChunkMeta(pageid=i, title=title or f"T{i}",
                       url=url or f"https://kz/he/T{i}",
                       lang=lang, section="", lastrevid=0, source="corpus"),
        score=0.9,
    )


# ── route_after_grade (pure) ─────────────────────────────────────────────────
def test_route_generate_when_any_kept():
    assert graph.route_after_grade({"kept": [_rc(0)]}) == "generate"


def test_route_refuse_when_wrong_topic_no_retry_used():
    assert graph.route_after_grade(
        {"kept": [], "grade_failure": grade.FAILURE_WRONG_TOPIC, "retry_count": 0}
    ) == "refuse"


def test_route_re_retrieve_when_narrow_terminology_within_budget():
    assert graph.route_after_grade(
        {"kept": [], "grade_failure": grade.FAILURE_NARROW_TERMINOLOGY, "retry_count": 0}
    ) == "re_retrieve"


def test_route_re_retrieve_when_cross_lingual_thin_within_budget():
    assert graph.route_after_grade(
        {"kept": [], "grade_failure": grade.FAILURE_CROSS_LINGUAL_THIN, "retry_count": 0}
    ) == "re_retrieve"


def test_route_refuse_when_retry_cap_hit(monkeypatch):
    monkeypatch.setattr(config, "GRADE_LOOP_CAP", 1)
    assert graph.route_after_grade(
        {"kept": [], "grade_failure": grade.FAILURE_NARROW_TERMINOLOGY, "retry_count": 1}
    ) == "refuse"


def test_route_refuse_when_ok_with_no_kept_unusual():
    # 'ok' but nothing kept is degenerate; refuse rather than retry endlessly.
    assert graph.route_after_grade(
        {"kept": [], "grade_failure": grade.FAILURE_OK, "retry_count": 0}
    ) == "refuse"


# ── End-to-end via run_agent (with monkeypatched primitives) ─────────────────
def _wire(monkeypatch, *, retrieved_seq, grade_seq, gen_text="answer body",
          broaden_to=None, rewrite_to=None):
    """Helper: each call to retrieve()/grade()/generate() returns the next item
    from its sequence. Lets us simulate multi-step flows."""
    retrieved_iter = iter(retrieved_seq)
    grade_iter = iter(grade_seq)

    def fake_retrieve(query, lang, *, top_k=None, collection=None, relax_filter=False):
        return next(retrieved_iter)

    def fake_grade(question, chunks, *, max_keep=5, generate_fn=None):
        return next(grade_iter)

    def fake_generate(prompt, system=None, temperature=None):
        return gen_text

    def fake_rewrite(question, history=None, generate_fn=None):
        from rag.rewrite import RewriteResult
        return RewriteResult(query=rewrite_to or question, is_follow_up=False)

    def fake_broaden(question, generate_fn=None):
        from rag.rewrite import RewriteResult
        return RewriteResult(query=broaden_to or question, is_follow_up=False)

    monkeypatch.setattr(retriever, "retrieve", fake_retrieve)
    monkeypatch.setattr("rag.graph.retriever.retrieve", fake_retrieve)
    monkeypatch.setattr("rag.graph.grade_mod.grade_chunks", fake_grade)
    monkeypatch.setattr("rag.graph.rewrite_mod.rewrite_query", fake_rewrite)
    monkeypatch.setattr("rag.graph.rewrite_mod.broaden_terminology", fake_broaden)
    monkeypatch.setattr("rag.graph.llm.generate", fake_generate)
    # Reset the lazy module-level graph so route logic uses our patches.
    monkeypatch.setattr("rag.graph._GRAPH", None)


def _g_keep(chunks):
    return grade.GradeResult(kept_indices=list(range(len(chunks))),
                             reasons=["ok"] * len(chunks),
                             overall_failure=grade.FAILURE_OK, raw={})


def _g_drop(failure):
    return grade.GradeResult(kept_indices=[], reasons=[], overall_failure=failure, raw={})


def test_happy_path_one_retrieve_then_generate(monkeypatch):
    chunks = [_rc(1), _rc(2)]
    _wire(monkeypatch, retrieved_seq=[chunks], grade_seq=[_g_keep(chunks)],
          gen_text="תשובה")
    a = graph.run_agent("מה זכאות?", "he")
    assert a.refused is False
    assert a.text == "תשובה"
    assert {c.url for c in a.citations} == {"https://kz/he/T1", "https://kz/he/T2"}
    assert a.disclaimer == prompts.disclaimer("he")


def test_narrow_terminology_triggers_one_re_retrieve_then_succeeds(monkeypatch):
    """First grade rejects everything with narrow_terminology; re-retrieve
    broadens the query; second retrieve+grade keeps a chunk; generate runs."""
    first, second = [_rc(1)], [_rc(2)]
    _wire(
        monkeypatch,
        retrieved_seq=[first, second],
        grade_seq=[_g_drop(grade.FAILURE_NARROW_TERMINOLOGY), _g_keep(second)],
        gen_text="תשובה אחרי הרחבה",
        broaden_to="מענק לידה",
    )
    a = graph.run_agent("כסף לאמהות חדשות", "he")
    assert a.refused is False
    assert a.text == "תשובה אחרי הרחבה"
    assert any("T2" in c.title for c in a.citations)


def test_cross_lingual_thin_triggers_filter_relax(monkeypatch):
    """Empty same-lang result → cross_lingual_thin → re-retrieve with relax_filter
    sees the other-language chunk → kept → generate."""
    flag = {"relax": False}

    def fake_retrieve(query, lang, *, top_k=None, collection=None, relax_filter=False):
        flag["relax"] = flag["relax"] or relax_filter
        if relax_filter:
            return [_rc(9, lang="he")]    # found in he when ru was thin
        return []                          # first attempt: ru returns nothing useful

    monkeypatch.setattr(retriever, "retrieve", fake_retrieve)
    monkeypatch.setattr("rag.graph.retriever.retrieve", fake_retrieve)

    grade_iter = iter([_g_drop(grade.FAILURE_CROSS_LINGUAL_THIN),
                       _g_keep([_rc(9, lang="he")])])

    def fake_grade(question, chunks, **kw):
        return next(grade_iter)

    monkeypatch.setattr("rag.graph.grade_mod.grade_chunks", fake_grade)

    from rag.rewrite import RewriteResult
    monkeypatch.setattr("rag.graph.rewrite_mod.rewrite_query",
                        lambda q, history=None, generate_fn=None: RewriteResult(q, False))
    monkeypatch.setattr("rag.graph.rewrite_mod.broaden_terminology",
                        lambda q, generate_fn=None: RewriteResult(q, False))
    monkeypatch.setattr("rag.graph.llm.generate",
                        lambda p, system=None, temperature=None: "ru answer with he source")
    monkeypatch.setattr("rag.graph._GRAPH", None)

    a = graph.run_agent("какая-то редкая тема", "ru")
    assert a.refused is False
    assert flag["relax"] is True
    assert a.text == "ru answer with he source"


def test_wrong_topic_refuses_without_burning_retry(monkeypatch):
    _wire(monkeypatch, retrieved_seq=[[_rc(1)]],
          grade_seq=[_g_drop(grade.FAILURE_WRONG_TOPIC)])
    a = graph.run_agent("מה מזג האוויר?", "he")
    assert a.refused is True
    assert a.text == prompts.refusal("he")
    assert a.citations == []


def test_retry_cap_refuses_after_one_failed_re_retrieve(monkeypatch):
    """Two consecutive narrow_terminology failures hit the cap → refuse."""
    _wire(monkeypatch,
          retrieved_seq=[[_rc(1)], [_rc(2)]],
          grade_seq=[_g_drop(grade.FAILURE_NARROW_TERMINOLOGY),
                     _g_drop(grade.FAILURE_NARROW_TERMINOLOGY)])
    a = graph.run_agent("colloquial term", "he")
    assert a.refused is True
    assert a.text == prompts.refusal("he")
    assert a.citations == []


def test_template_refusal_from_generate_drops_citations(monkeypatch):
    """If generate returns the template refusal string, the bot should not
    attach citations even though grade kept chunks."""
    chunks = [_rc(1)]
    refusal_he = "בהסתמך על המקורות שסופקו, אין בטקסטים מידע שעונה על השאלה."
    _wire(monkeypatch, retrieved_seq=[chunks], grade_seq=[_g_keep(chunks)],
          gen_text=refusal_he)
    a = graph.run_agent("borderline question", "he")
    assert a.refused is True
    assert a.text == refusal_he
    assert a.citations == [] and a.disclaimer == ""


def test_empty_generation_falls_back_to_refusal(monkeypatch):
    chunks = [_rc(1)]
    _wire(monkeypatch, retrieved_seq=[chunks], grade_seq=[_g_keep(chunks)],
          gen_text="   ")
    a = graph.run_agent("q", "he")
    assert a.refused is True
    assert a.text == prompts.refusal("he")
