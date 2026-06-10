import json
import os

import pytest

from eval import judge_llm


def test_judge_generate_parses_json(monkeypatch):
    class _Msg:  # mimic openai response shape
        content = '{"score": 0.5}'

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kw):
            assert kw["model"] == "o4-mini"
            assert kw["reasoning_effort"] == "low"
            assert kw["response_format"] == {"type": "json_object"}
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    monkeypatch.setattr(judge_llm, "_get_client", lambda: _Client())
    out = judge_llm.judge_generate("hi", system="sys")
    assert json.loads(out) == {"score": 0.5}


def test_judge_generate_missing_key_raises(monkeypatch):
    monkeypatch.setattr(judge_llm, "_client", None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(judge_llm, "OpenAI", None)  # simulate no SDK/key path
    with pytest.raises(judge_llm.JudgeUnavailable):
        judge_llm.judge_generate("hi")


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"),
                    reason="needs OPENAI_API_KEY")
def test_judge_generate_live_smoke():
    out = judge_llm.judge_generate(
        'Return JSON {"ok": true} and nothing else.', system="You output strict JSON.")
    assert json.loads(out).get("ok") is True
