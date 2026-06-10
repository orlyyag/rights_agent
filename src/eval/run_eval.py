"""Per-question eval runner. Scores the linear OR agent RAG path against the
golden set; writes JSONL results. ``report.py`` consumes the output.

For each in-scope item: retrieve (top-K) → answer → judge → log metrics.
For each adversarial item: answer → judge refusal → log.
Latency is recorded so A2 (latency improvement) has a baseline.

Run (from repo root):
    PYTHONPATH=.:src python -m eval.run_eval                  # default: linear (Tier-0 baseline)
    PYTHONPATH=.:src python -m eval.run_eval --path agent     # Tier-1 agent loop (R4 + R5)

Output filenames carry the path so both runs coexist:
    eval/results_he_linear.jsonl + eval/report_he_linear.md
    eval/results_he_agent.jsonl  + eval/report_he_agent.md
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import config
from eval import metrics
from rag import answer as answer_mod
from rag import retriever

GOLDEN_PATH = Path("eval") / "golden_he.jsonl"
HIT_K = 5
INTER_QUESTION_SLEEP_S = 1.5  # pacing — each Q makes ~3 LLM calls (linear) or ~5 (agent)


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


def _answer_fn(path: str):
    """Return a callable ``(question, lang, *, thread_id=...)`` that hits the
    requested answer path. Both entrypoints accept thread_id kwarg uniformly."""
    if path == "agent":
        return answer_mod.answer_agent
    return answer_mod.answer


def _eval_one(item: dict, answer_fn) -> dict:
    lang = item["lang"]
    q = item["question"]
    t0 = time.monotonic()
    # thread_id = the golden item id — lets us filter LangSmith by item ("show
    # me every call for in-001") and group the agent's multi-node trace.
    a = answer_fn(q, lang, thread_id=f"eval:{item['id']}")
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


def main(path: str = "linear") -> None:
    items = list(_iter_golden(GOLDEN_PATH))
    results_path = Path("eval") / f"results_he_{path}.jsonl"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    answer_fn = _answer_fn(path)
    print(f"Eval ({path}): {len(items)} questions → {results_path}")
    with results_path.open("w", encoding="utf-8") as out:
        for i, item in enumerate(items, 1):
            try:
                rec = _eval_one(item, answer_fn)
                rec["answer_path"] = path
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
    print(f"Done. Run `python -m eval.report --path {path}` for the summary.")


def cli() -> None:
    ap = argparse.ArgumentParser(description="Score the linear or agent path against golden_he.jsonl")
    ap.add_argument("--path", choices=["linear", "agent"], default="linear",
                    help="answer path to evaluate (default: linear)")
    args = ap.parse_args()
    main(args.path)


if __name__ == "__main__":
    sys.exit(cli())
