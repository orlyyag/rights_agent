"""grade_docs — pure-logic tests (LLM mocked)."""
from __future__ import annotations

from rag import grade
from schema import ChunkMeta, RetrievedChunk


def _chunks(n=3):
    return [
        RetrievedChunk(
            text=f"body {i}",
            meta=ChunkMeta(pageid=i, title=f"T{i}", url=f"u{i}",
                           lang="he", section="", lastrevid=0, source="corpus"),
            score=0.9,
        )
        for i in range(n)
    ]


def test_empty_chunks_skip_llm_call():
    called = {"n": 0}
    def fake(*a, **kw):
        called["n"] += 1
        return ""
    r = grade.grade_chunks("q", [], generate_fn=fake)
    assert called["n"] == 0
    assert not r.any_kept and r.overall_failure == grade.FAILURE_OK


def test_keeps_relevant_indices_in_order():
    fake_json = (
        '{"verdicts": ['
        '  {"id": 0, "relevant": false, "reason": "off-topic"},'
        '  {"id": 1, "relevant": true, "reason": "covers eligibility"},'
        '  {"id": 2, "relevant": true, "reason": "covers amounts"}'
        '], "overall": "ok"}'
    )
    r = grade.grade_chunks("q", _chunks(3), generate_fn=lambda p, system=None: fake_json)
    assert r.kept_indices == [1, 2]
    assert r.reasons[0] == "off-topic"
    assert r.overall_failure == grade.FAILURE_OK
    assert r.any_kept


def test_caps_at_max_keep():
    verdicts = ",".join(f'{{"id": {i}, "relevant": true, "reason": "x"}}' for i in range(8))
    r = grade.grade_chunks("q", _chunks(8), max_keep=3,
                            generate_fn=lambda p, system=None: '{"verdicts": [' + verdicts + '], "overall": "ok"}')
    assert r.kept_indices == [0, 1, 2]


def test_overall_failure_narrow_terminology_routes_retry():
    fake_json = ('{"verdicts": [{"id": 0, "relevant": false, "reason": "uses official term not in query"}],'
                 '"overall": "narrow_terminology"}')
    r = grade.grade_chunks("q", _chunks(1), generate_fn=lambda p, system=None: fake_json)
    assert not r.any_kept
    assert r.overall_failure == grade.FAILURE_NARROW_TERMINOLOGY


def test_overall_failure_wrong_topic():
    r = grade.grade_chunks(
        "?",
        _chunks(2),
        generate_fn=lambda p, system=None:
            '{"verdicts": [{"id":0,"relevant":false,"reason":"weather"},'
            '{"id":1,"relevant":false,"reason":"weather"}],"overall":"wrong_topic"}',
    )
    assert r.overall_failure == grade.FAILURE_WRONG_TOPIC and not r.any_kept


def test_invalid_overall_falls_back_to_ok():
    r = grade.grade_chunks(
        "q", _chunks(1),
        generate_fn=lambda p, system=None: '{"verdicts":[{"id":0,"relevant":true,"reason":""}],"overall":"glorp"}',
    )
    assert r.overall_failure == grade.FAILURE_OK


def test_broken_json_treats_as_no_kept():
    r = grade.grade_chunks("q", _chunks(2), generate_fn=lambda p, system=None: "not json at all")
    assert not r.any_kept
    assert r.overall_failure == grade.FAILURE_OK


def test_out_of_range_id_is_ignored():
    r = grade.grade_chunks(
        "q", _chunks(2),
        generate_fn=lambda p, system=None:
            '{"verdicts": [{"id": 0, "relevant": true, "reason": ""},'
            '{"id": 5, "relevant": true, "reason": ""}], "overall": "ok"}',
    )
    assert r.kept_indices == [0]


def test_prompt_contains_lang_and_snippet():
    seen = {}
    def fake(prompt, system=None):
        seen["prompt"] = prompt
        seen["system"] = system
        return '{"verdicts": [], "overall": "ok"}'
    grade.grade_chunks("מה זכאות?", _chunks(1), generate_fn=fake)
    assert "lang=he" in seen["prompt"]
    assert "[0]" in seen["prompt"]
    assert "STRICT JSON" in seen["system"]
