"""rewrite — history-aware condense + terminology broaden (LLM mocked)."""
from __future__ import annotations

from rag import rewrite


def test_no_history_passes_through_without_llm_call():
    called = {"n": 0}
    def fake(*a, **kw):
        called["n"] += 1
        return ""
    r = rewrite.rewrite_query("מה זכאות?", history=None, generate_fn=fake)
    assert called["n"] == 0
    assert r.query == "מה זכאות?" and r.is_follow_up is False


def test_follow_up_is_condensed():
    history = [("user", "מה מגיע לי אחרי לידה?"),
               ("assistant", "מענק לידה, קצבת ילדים…")]
    fake = '{"query": "מענק לידה לעצמאים", "is_follow_up": true, "reason": "elliptical follow-up about freelancers"}'
    r = rewrite.rewrite_query("ולעצמאים?", history=history,
                              generate_fn=lambda p, system=None: fake)
    assert r.is_follow_up is True
    assert r.query == "מענק לידה לעצמאים"


def test_new_topic_returns_current_message_verbatim():
    history = [("user", "מה מגיע לי אחרי לידה?"),
               ("assistant", "מענק לידה…")]
    fake = '{"query": "דוח חניה", "is_follow_up": false, "reason": "topic switched"}'
    r = rewrite.rewrite_query("דוח חניה", history=history,
                              generate_fn=lambda p, system=None: fake)
    assert r.is_follow_up is False
    assert r.query == "דוח חניה"


def test_broken_json_falls_back_to_original_question():
    r = rewrite.rewrite_query("ולעצמאים?", history=[("user", "x")],
                              generate_fn=lambda p, system=None: "not json")
    assert r.query == "ולעצמאים?"
    assert r.is_follow_up is False


def test_empty_query_in_json_falls_back_to_original():
    r = rewrite.rewrite_query("חופשת לידה",
                              history=[("user", "x")],
                              generate_fn=lambda p, system=None: '{"query": "", "is_follow_up": false}')
    assert r.query == "חופשת לידה"


def test_history_formatting_includes_role_labels_and_truncates():
    seen = {}
    def fake(prompt, system=None):
        seen["prompt"] = prompt
        return '{"query": "x", "is_follow_up": false}'
    history = [("user", "Q1"), ("assistant", "A1"), ("user", "x" * 500)]
    rewrite.rewrite_query("Q2", history=history, generate_fn=fake)
    assert "User: Q1" in seen["prompt"]
    assert "Assistant: A1" in seen["prompt"]
    # last user line should be truncated with ellipsis
    assert "…" in seen["prompt"]


def test_broaden_terminology_calls_llm_with_official_term_prompt():
    seen = {}
    def fake(prompt, system=None):
        seen["system"] = system
        return '{"query": "מענק לידה", "reason": "official term"}'
    r = rewrite.broaden_terminology("כסף לאמהות חדשות", generate_fn=fake)
    assert r.query == "מענק לידה"
    assert "official" in (seen["system"] or "").lower() or "broader" in (seen["system"] or "").lower()
