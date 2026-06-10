"""Pure-logic eval-metric tests (LLM-free via inject-fn)."""
from __future__ import annotations

from eval import metrics
from eval.metrics import _legacy


def test_hit_at_k():
    assert metrics.hit_at_k(["a", "b", "c"], "b", k=3) is True
    assert metrics.hit_at_k(["a", "b", "c"], "b", k=1) is False
    assert metrics.hit_at_k(["a", "b", "c"], "z", k=3) is False
    assert metrics.hit_at_k(["a"], None, k=3) is False         # no gold → False
    # Coerce ids to strings (CSV ids are strings; Chroma metadata may store ints)
    assert metrics.hit_at_k([1, 2, 3], "2", k=3) is True


def test_parse_json_extracts_object_from_noisy_output():
    # _parse_json is a private helper of the legacy Gemini judge module.
    assert _legacy._parse_json('here is the json: {"a": 1, "b": true}') == {"a": 1, "b": True}
    assert _legacy._parse_json("no json at all") == {}
    assert _legacy._parse_json('```json\n{"x": false}\n```') == {"x": False}


def test_judge_in_scope_with_fake_llm():
    fake = lambda p, system=None: '{"correct": true, "language_match": true, "faithful": true, "has_citation": false}'
    r = metrics.judge_in_scope("q", "a", "ref", generate_fn=fake)
    assert r.correct is True and r.faithful is True and r.has_citation is False


def test_judge_refusal_with_fake_llm():
    assert metrics.judge_refusal("?", "I refuse",
                                 generate_fn=lambda p, system=None: '{"refused_correctly": true}') is True
    assert metrics.judge_refusal("?", "fake answer",
                                 generate_fn=lambda p, system=None: '{"refused_correctly": false}') is False
