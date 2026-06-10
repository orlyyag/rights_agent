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

# LangSmith @traceable (A8) — optional. When the SDK is installed and
# LANGSMITH_API_KEY is set in .env, every embed/generate call shows up as a
# traced run. When not installed, this degrades to a transparent no-op so the
# wrapper, the tests, and production all keep the exact same shape.
try:
    from langsmith import get_current_run_tree, traceable  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    def traceable(*args, **kwargs):  # type: ignore[no-redef]
        if args and callable(args[0]):
            return args[0]
        def _deco(fn):
            return fn
        return _deco
    def get_current_run_tree():  # type: ignore[no-redef]
        return None


def _record_usage(usage_metadata) -> None:
    """Attach Gemini token counts to the current LangSmith run so the dashboard
    can compute cost (LangSmith reads ``usage_metadata`` + ``ls_model_name`` to
    map tokens → dollars). No-op when no tracing context is active."""
    rt = get_current_run_tree()
    if rt is None or usage_metadata is None:
        return
    try:
        rt.add_metadata({
            "usage_metadata": {
                "input_tokens": int(getattr(usage_metadata, "prompt_token_count", 0) or 0),
                "output_tokens": int(getattr(usage_metadata, "candidates_token_count", 0) or 0),
                "total_tokens": int(getattr(usage_metadata, "total_token_count", 0) or 0),
            },
        })
    except Exception:  # noqa: BLE001 — observability must never break a request
        pass


def _set_thread_id(thread_id: str | None) -> None:
    """Tag the current LangSmith run with a thread_id so all child runs (embed,
    generate, grade, rewrite, ...) appear under the same conversation/question.
    Used by the bot (chat_id) and the eval (question id)."""
    if not thread_id:
        return
    rt = get_current_run_tree()
    if rt is None:
        return
    try:
        rt.add_metadata({"thread_id": str(thread_id)})
    except Exception:  # noqa: BLE001
        pass


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
    """Exponential backoff (``LLM_BACKOFF_S * 2**attempt``) — defaults to 5/10/20/40/80s,
    enough to ride out a per-minute quota refresh (RESOURCE_EXHAUSTED / 429)."""
    last: Exception | None = None
    for attempt in range(config.LLM_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — single choke point by design (§0 #6)
            last = exc
            if attempt < config.LLM_RETRIES:
                wait = config.LLM_BACKOFF_S * (2 ** attempt)
                print(f"  ⚠ {what} attempt {attempt+1} failed ({type(exc).__name__}); "
                      f"retrying in {wait:g}s", flush=True)
                time.sleep(wait)
    raise LLMError(f"{what} failed after {config.LLM_RETRIES + 1} attempts: {last}") from last


@traceable(
    name="embed",
    run_type="embedding",
    metadata={"ls_provider": "google", "ls_model_name": "gemini-embedding-001"},
)
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


@traceable(
    name="generate",
    run_type="llm",
    metadata={"ls_provider": "google", "ls_model_name": config.GEN_MODEL,
              "ls_model_type": "chat"},
)
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
        _record_usage(getattr(resp, "usage_metadata", None))
        return (resp.text or "").strip()

    return _with_retry(_call, what="generate")
