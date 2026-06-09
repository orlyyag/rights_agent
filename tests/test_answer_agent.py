"""answer_agent + answer_default routing — LLM-free."""
from __future__ import annotations

import config
from rag import answer as answer_mod
from schema import Answer


def test_answer_default_routes_to_linear_by_default(monkeypatch):
    monkeypatch.setattr(config, "ANSWER_PATH", "linear")
    seen = {}
    monkeypatch.setattr(answer_mod, "answer",
                        lambda q, l: (seen.setdefault("via", "linear"),
                                      Answer(text="x", lang=l, citations=[], disclaimer=""))[1])
    monkeypatch.setattr(answer_mod, "answer_agent",
                        lambda *a, **kw: (seen.setdefault("via", "agent"),
                                          Answer(text="y", lang="he", citations=[], disclaimer=""))[1])
    out = answer_mod.answer_default("q", "he")
    assert out.text == "x"
    assert seen["via"] == "linear"


def test_answer_default_routes_to_agent_when_configured(monkeypatch):
    monkeypatch.setattr(config, "ANSWER_PATH", "agent")
    seen = {}
    monkeypatch.setattr(answer_mod, "answer",
                        lambda q, l: (seen.setdefault("via", "linear"),
                                      Answer(text="x", lang=l, citations=[], disclaimer=""))[1])
    monkeypatch.setattr(answer_mod, "answer_agent",
                        lambda *a, **kw: (seen.setdefault("via", "agent"),
                                          Answer(text="y", lang="he", citations=[], disclaimer=""))[1])
    out = answer_mod.answer_default("q", "he")
    assert out.text == "y"
    assert seen["via"] == "agent"


def test_answer_agent_delegates_to_graph(monkeypatch):
    captured = {}

    def fake_run_agent(question, lang, history=None):
        captured["question"] = question
        captured["lang"] = lang
        captured["history"] = history
        return Answer(text="from agent", lang=lang, citations=[], disclaimer="")

    import rag.graph as graph_mod
    monkeypatch.setattr(graph_mod, "run_agent", fake_run_agent)

    out = answer_mod.answer_agent("מה זכאות?", "he", history=[("user", "prev")])
    assert out.text == "from agent"
    assert captured == {"question": "מה זכאות?", "lang": "he", "history": [("user", "prev")]}
