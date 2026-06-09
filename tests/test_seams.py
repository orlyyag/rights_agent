"""Contract tests for the three frozen Day-1 seams (PLAN §21, R9).

Pure-logic, LLM-free (§0 #9): no network, no API key, no SDK required.
Run: ``pytest -m "not integration"``.
"""
from __future__ import annotations

import pytest

import config
import schema
from rag import llm


def test_active_pointer_roundtrip_and_atomic(tmp_path, monkeypatch):
    ptr = tmp_path / "active_collection"
    monkeypatch.setattr(config, "ACTIVE_POINTER", ptr)

    # Missing pointer → default (R7 fallback; no restart needed).
    assert config.get_active_collection() == config.DEFAULT_COLLECTION

    config.set_active_collection("kz_v7")
    assert config.get_active_collection() == "kz_v7"
    # Atomic flip leaves no half-written temp behind.
    assert not ptr.with_suffix(".tmp").exists()


def test_chunk_meta_is_chroma_scalar_and_roundtrips():
    meta = schema.ChunkMeta(
        pageid=123, title="דמי לידה", url="https://kolzchut/x",
        lang="he", section="כמה מקבלים", lastrevid=999, source="pipeline",
    )
    d = meta.to_metadata()
    assert set(d) == set(schema.CHUNK_META_FIELDS)
    assert all(isinstance(v, (str, int, float, bool)) for v in d.values())  # Chroma-safe
    assert schema.ChunkMeta.from_metadata(d) == meta


def test_chunk_id_is_stable():
    assert schema.chunk_id("corpus", "ru", 42, 3) == "corpus:ru:42:3"


def test_llm_is_single_mock_point(monkeypatch):
    monkeypatch.setattr(llm, "generate", lambda p, **k: "MOCK")
    assert llm.generate("hi", system="s") == "MOCK"
    assert callable(llm.embed) and callable(llm.generate)


def test_llm_retry_then_raises_llmerror(monkeypatch):
    monkeypatch.setattr(config, "LLM_RETRIES", 1)
    monkeypatch.setattr(config, "LLM_BACKOFF_S", 0.0)
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RuntimeError("simulated 429")

    with pytest.raises(llm.LLMError):
        llm._with_retry(boom, what="x")
    assert calls["n"] == 2  # initial attempt + 1 retry (§0 #6)
