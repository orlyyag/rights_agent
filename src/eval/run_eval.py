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
import inspect
import json
import sys
import time
from pathlib import Path

import config
from eval.metrics import heuristics as H
from eval.metrics import judges as J
from rag import answer as answer_mod
from rag import retriever, rewrite

GOLDEN_PATH = Path("eval") / "golden_he.jsonl"
HIT_K = 5
INTER_QUESTION_SLEEP_S = 1.5  # pacing — each Q makes ~3 LLM calls (linear) or ~5 (agent)


def _iter_golden(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _retrieve_context(question: str, lang: str,
                      history: list[tuple[str, str]] | None = None):
    """Top-K chunks with text — for hit@k AND faithfulness/context-precision.

    Two-turn items (T13/R5) condense the follow-up into a standalone query first,
    mirroring the agent's rewrite step — hit@k on the raw \"ולעצמאים?\" would
    measure nothing. Returns (doc_ids, context, resolved_query).
    """
    resolved = question
    if history:
        resolved = rewrite.rewrite_query(question, history).query
    chunks = retriever.retrieve(resolved, lang, top_k=HIT_K)
    ids = [str(c.meta.pageid) for c in chunks]
    context = [{"doc_id": str(c.meta.pageid), "title": c.meta.title, "text": c.text}
               for c in chunks]
    return ids, context, resolved


def _answer_fn(path: str):
    """Return a callable ``(question, lang, *, thread_id=...)`` that hits the
    requested answer path. Both entrypoints accept thread_id kwarg uniformly."""
    if path == "agent":
        return answer_mod.answer_agent
    return answer_mod.answer


def _eval_one(item: dict, answer_fn) -> dict:
    lang = item["lang"]
    q = item["question"]
    # T13/R5 two-turn cases carry prior turns; only the agent path consumes them
    # (the linear path has no memory — it sees the raw follow-up and is EXPECTED
    # to do worse, which is the point of the case).
    history = [tuple(t) for t in (item.get("history") or [])]
    t0 = time.monotonic()
    # thread_id = the golden item id — lets us filter LangSmith by item ("show
    # me every call for in-001") and group the agent's multi-node trace.
    # Signature check, not try/except: probing with an unsupported kwarg makes
    # the @traceable wrapper log a binding failure for every two-turn item.
    if history and "history" in inspect.signature(answer_fn).parameters:
        a = answer_fn(q, lang, history=history, thread_id=f"eval:{item['id']}")
    else:
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
    if item.get("case"):
        base["case"] = item["case"]   # e.g. follow_up / colloquial_recovery (T13)

    if item["category"] == "in_scope":
        # Independent top-K retrieval (the answer path may keep fewer after the
        # floor cut; hit@k wants the standard k). Capture the chunk TEXT too so
        # faithfulness can be judged against what the generator actually saw.
        retrieved_ids, context, resolved_q = _retrieve_context(q, lang, history or None)
        if resolved_q != q:
            base["resolved_query"] = resolved_q
        gold = item.get("gold_doc_ids") or item["gold_doc_id"]   # set or scalar
        hit = H.hit_at_k(retrieved_ids, gold, HIT_K)
        cited_urls = [c.url for c in a.citations]
        base.update(
            retrieved_doc_ids=retrieved_ids,
            retrieved_context=context,
            cited_doc_ids=cited_urls,
            recall_at_k=H.recall_at_k(retrieved_ids, gold, HIT_K),
            mrr=H.mrr(retrieved_ids, gold),
            citation_present=H.citation_present(cited_urls),
            has_citation=H.citation_present(cited_urls),   # back-compat alias
            citation_valid=H.citation_valid(cited_urls),
            language_match=H.language_match(a.text, lang),
            refusal_kind=H.refusal_kind(refused=a.refused, hit=hit),
        )
        base[f"hit@{HIT_K}"] = hit
        if a.refused:
            # Refused on an in-scope question — no answer to judge.
            base.update(correct=None, faithful=None, answer_relevancy=None,
                        answer_correctness=None)
        else:
            ctx_text = "\n\n".join(c["text"] for c in context)
            faith = J.faithfulness(a.text, ctx_text)
            relev = J.answer_relevancy(q, a.text)
            corr = J.answer_correctness(q, a.text, item["gold_paragraph"])
            base.update(
                faithful=(faith.score if faith else None),
                faithful_supported=(faith.n_supported if faith else None),
                faithful_claims=(faith.n_claims if faith else None),
                answer_relevancy=relev,
                answer_correctness=corr,
                correct=(None if corr is None else corr >= 0.5),
            )
    else:  # adversarial
        base["refused_correctly"] = J.refusal_correctness(q, a.text)

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
