"""Per-question eval runner. Scores the linear Tier-0 RAG path against the
golden set; writes JSONL results. ``report.py`` consumes the output.

For each in-scope item: retrieve (top-K) → answer → judge → log metrics.
For each adversarial item: answer → judge refusal → log.
Latency is recorded so A2 (latency improvement) has a baseline.

Run (from repo root):
    PYTHONPATH=.:src python -m eval.run_eval
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import config
from eval import metrics
from rag import answer as answer_mod
from rag import retriever

GOLDEN_PATH = Path("eval") / "golden_he.jsonl"
RESULTS_PATH = Path("eval") / "results_he.jsonl"
HIT_K = 5
INTER_QUESTION_SLEEP_S = 1.5  # extra pacing — each Q makes ~3 LLM calls (gen + 2 judge)


def _iter_golden(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _retrieved_doc_ids(question: str, lang: str) -> list[str]:
    """Same retrieval the answer path uses, but expose the chunks' doc_ids for hit@k."""
    chunks = retriever.retrieve(question, lang, top_k=HIT_K)
    return [str(c.meta.pageid) for c in chunks]


def _eval_one(item: dict) -> dict:
    lang = item["lang"]
    q = item["question"]
    t0 = time.monotonic()
    a = answer_mod.answer(q, lang)
    latency_s = time.monotonic() - t0

    base = {
        "id": item["id"],
        "category": item["category"],
        "question": q,
        "lang": lang,
        "latency_s": round(latency_s, 3),
        "answer_text": a.text,
        "answer_refused": a.refused,
        "answer_n_citations": len(a.citations),
        "answer_citation_urls": [c.url for c in a.citations],
    }

    if item["category"] == "in_scope":
        # hit@k uses an independent retrieval call (the answer path may have used
        # fewer than HIT_K chunks after the floor cut; we want the standard k=5).
        retrieved_ids = _retrieved_doc_ids(q, lang)
        base["retrieved_doc_ids"] = retrieved_ids
        base[f"hit@{HIT_K}"] = metrics.hit_at_k(retrieved_ids, item["gold_doc_id"], HIT_K)
        if a.refused:
            # Refused on an in-scope question — judge can't score correctness; mark as miss.
            base.update(correct=False, language_match=False, faithful=False, has_citation=False)
        else:
            judged = metrics.judge_in_scope(q, a.text, item["gold_paragraph"])
            base.update(
                correct=judged.correct,
                language_match=judged.language_match,
                faithful=judged.faithful,
                has_citation=judged.has_citation,
            )
    else:  # adversarial
        base["refused_correctly"] = metrics.judge_refusal(q, a.text)

    return base


def main() -> None:
    items = list(_iter_golden(GOLDEN_PATH))
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Eval: {len(items)} questions → {RESULTS_PATH}")
    with RESULTS_PATH.open("w", encoding="utf-8") as out:
        for i, item in enumerate(items, 1):
            try:
                rec = _eval_one(item)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                marker = (
                    f"hit@{HIT_K}={rec.get(f'hit@{HIT_K}')!s:5s} correct={rec.get('correct')!s:5s}"
                    if item["category"] == "in_scope"
                    else f"refused_correctly={rec.get('refused_correctly')}"
                )
                print(f"  [{i:>2}/{len(items)}] {item['id']:10s} {marker}  ({rec['latency_s']}s)", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{i:>2}/{len(items)}] {item['id']:10s} ERROR: {type(exc).__name__}: {exc}",
                      flush=True)
                out.write(json.dumps({"id": item["id"], "error": str(exc)}, ensure_ascii=False) + "\n")
                out.flush()
            time.sleep(INTER_QUESTION_SLEEP_S)
    print(f"Done. Run `python -m eval.report` for the summary.")


if __name__ == "__main__":
    main()
