"""OpenAI judge wrapper — EVAL ONLY. The production bot never imports this.

Cross-provider on purpose: the generator is Gemini, the judge is OpenAI, so the
judge has no self-preference for the generator's outputs. Lazy client (import-safe
for offline tests), retry/backoff, LangSmith-traceable, JSON-object output.
"""
from __future__ import annotations

import os
import time

import config

try:  # import-safe: tests/offline tooling can import without the SDK installed
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None  # type: ignore

try:
    from rag.llm import traceable
except Exception:  # noqa: BLE001
    def traceable(*_a, **_k):  # fallback no-op decorator
        def deco(fn):
            return fn
        return deco

_client = None


class JudgeUnavailable(RuntimeError):
    """Raised when no OpenAI key/SDK is available — callers degrade gracefully."""


def _get_client():
    global _client
    if _client is not None:
        return _client
    if OpenAI is None or not os.environ.get("OPENAI_API_KEY"):
        raise JudgeUnavailable("OPENAI_API_KEY / openai SDK not available")
    _client = OpenAI()
    return _client


@traceable(name="judge_generate", run_type="llm",
           metadata={"ls_provider": "openai", "ls_model_name": config.OPENAI_JUDGE_MODEL})
def judge_generate(prompt: str, *, system: str | None = None, retries: int = 3) -> str:
    """Return the judge model's JSON text. Retries transient errors with backoff."""
    client = _get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    last = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=config.OPENAI_JUDGE_MODEL,
                messages=messages,
                reasoning_effort=config.OPENAI_JUDGE_REASONING_EFFORT,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 ** attempt)
    raise JudgeUnavailable(f"judge failed after {retries} attempts: {last}")
