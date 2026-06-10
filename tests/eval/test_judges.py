import json

from eval.metrics import judges


def _fake(payload):
    return lambda prompt, system=None: json.dumps(payload)


def test_faithfulness_per_claim():
    fn = _fake({"claims": [
        {"claim": "x", "supported": True},
        {"claim": "y", "supported": False},
    ]})
    r = judges.faithfulness("ans", "ctx", generate_fn=fn)
    assert r.n_claims == 2 and r.n_supported == 1
    assert r.score == 0.5


def test_faithfulness_empty_claims_is_one():
    fn = _fake({"claims": []})  # no checkable claims → vacuously faithful
    assert judges.faithfulness("ans", "ctx", generate_fn=fn).score == 1.0


def test_answer_relevancy_and_correctness_clamp():
    assert judges.answer_relevancy("q", "a", generate_fn=_fake({"score": 1.4})) == 1.0
    assert judges.answer_correctness("q", "a", "gold", generate_fn=_fake({"score": -2})) == 0.0
    assert judges.answer_correctness("q", "a", "gold", generate_fn=_fake({"score": 0.75})) == 0.75


def test_refusal_correctness():
    assert judges.refusal_correctness("q", "a", generate_fn=_fake({"refused_correctly": True})) is True
    assert judges.refusal_correctness("q", "a", generate_fn=_fake({})) is False


def test_judge_null_on_unavailable():
    def boom(*a, **k):
        from eval.judge_llm import JudgeUnavailable
        raise JudgeUnavailable("no key")
    assert judges.answer_correctness("q", "a", "g", generate_fn=boom) is None
