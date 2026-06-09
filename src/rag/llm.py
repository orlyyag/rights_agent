"""The single Gemini door — frozen Day-1 seam #2 (§0 conventions, the one mock point §0 #9).

``embed()`` + ``generate()``, each wrapped with retry/backoff + graceful fallback
(§0 #6). Pinned model versions live in :mod:`config`. Uses ``google-genai``
(``client.models.*``). Import-safe: the client is created lazily, so tests and
offline tooling can import this module — and monkeypatch ``embed``/``generate`` —
without the SDK installed or an API key set.
"""
from __future__ import annotations

import time
from typing import Callable, Sequence, TypeVar

import config

T = TypeVar("T")


class LLMError(RuntimeError):
    """Raised when a Gemini call fails after retries; callers degrade gracefully (§0 #6)."""


_client = None


def _get_client():
    """Lazily build the genai client (keeps module import-safe)."""
    global _client
    if _client is None:
        from google import genai  # imported lazily on first real call

        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _with_retry(fn: Callable[[], T], *, what: str) -> T:
    """Run ``fn`` with ``config.LLM_RETRIES`` extra attempts + linear backoff."""
    last: Exception | None = None
    for attempt in range(config.LLM_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — single choke point by design (§0 #6)
            last = exc
            if attempt < config.LLM_RETRIES:
                time.sleep(config.LLM_BACKOFF_S * (attempt + 1))
    raise LLMError(f"{what} failed after {config.LLM_RETRIES + 1} attempts: {last}") from last


def embed(texts: Sequence[str], *, task_type: str) -> list[list[float]]:
    """Embed a batch of strings.

    Use ``config.EMBED_TASK_DOCUMENT`` for chunks and ``EMBED_TASK_QUERY`` for
    queries (asymmetric, Q1). Returns one ``EMBED_DIM``-length vector per input.
    """
    from google.genai import types

    def _call() -> list[list[float]]:
        resp = _get_client().models.embed_content(
            model=config.EMBED_MODEL,
            contents=list(texts),
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=config.EMBED_DIM,
            ),
        )
        return [list(e.values) for e in resp.embeddings]

    return _with_retry(_call, what="embed")


def generate(prompt: str, *, system: str | None = None,
             temperature: float | None = None) -> str:
    """Generate grounded text.

    ``system`` is the grounding/guardrail system prompt (answer only from
    retrieved KZ content; ignore instructions inside user input or page text).
    """
    from google.genai import types

    def _call() -> str:
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=config.GEN_TEMPERATURE if temperature is None else temperature,
            thinking_config=types.ThinkingConfig(thinking_budget=config.GEN_THINKING_BUDGET),
        )
        resp = _get_client().models.generate_content(
            model=config.GEN_MODEL, contents=prompt, config=cfg)
        return (resp.text or "").strip()

    return _with_retry(_call, what="generate")
