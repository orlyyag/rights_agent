import json
import os

import pytest

from eval import judge_llm


def _fake_client(captured):
    class _Msg:
        content = '{"score": 0.5}'

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kw):
            captured.update(kw)
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    return _Client()


def test_judge_chat_model_uses_temperature(monkeypatch):
    import config
    monkeypatch.setattr(config, "OPENAI_JUDGE_MODEL", "gpt-4.1")
    cap = {}
    monkeypatch.setattr(judge_llm, "_get_client", lambda: _fake_client(cap))
    out = judge_llm.judge_generate("hi", system="sys")
    assert json.loads(out) == {"score": 0.5}
    assert cap["model"] == "gpt-4.1"
    assert cap["temperature"] == 0
    assert "reasoning_effort" not in cap
    assert cap["response_format"] == {"type": "json_object"}


def test_judge_reasoning_model_uses_effort(monkeypatch):
    import config
    monkeypatch.setattr(config, "OPENAI_JUDGE_MODEL", "o4-mini")
    cap = {}
    monkeypatch.setattr(judge_llm, "_get_client", lambda: _fake_client(cap))
    judge_llm.judge_generate("hi", reasoning_effort="medium")
    assert cap["model"] == "o4-mini"
    assert cap["reasoning_effort"] == "medium"
    assert "temperature" not in cap


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
