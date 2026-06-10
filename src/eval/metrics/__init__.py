"""Eval metrics package.

- ``heuristics`` — deterministic, no LLM (hit/recall/mrr/citation/language/refusal).
- ``judges``     — LLM-as-judge via the cross-provider OpenAI judge (added in Task 3).
- ``_legacy``    — the original Gemini single-call judge, kept for back-compat
                   (``spot_check.py`` and ``tests/test_metrics.py`` still use it).

The names below are re-exported so existing ``from eval import metrics`` callers
keep working.
"""
from eval.metrics import heuristics  # noqa: F401
from eval.metrics.heuristics import (  # noqa: F401
    hit_at_k,
    recall_at_k,
    mrr,
    context_precision_at_k,
    citation_present,
    citation_valid,
    language_match,
    refusal_kind,
)
from eval.metrics.judges import (  # noqa: F401
    faithfulness,
    answer_relevancy,
    answer_correctness,
    refusal_correctness,
)
from eval.metrics._legacy import (  # noqa: F401  back-compat (Gemini judge)
    judge_in_scope,
    judge_refusal,
    JudgeResult,
)
