"""Spot-check the agent path on a handful of LINEAR failures.

Cheap targeted comparison: load the linear baseline, pick the most informative
failures (retrieval misses first — where R4's terminology-broaden + filter-relax
re-retrieve should actually help — then a few correctness-only misses), run the
agent path on JUST those, and print a per-question linear-vs-agent table.

Run (from repo root):
    PYTHONPATH=.:src python -m eval.spot_check
    PYTHONPATH=.:src python -m eval.spot_check --n 10
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from eval import metrics
from rag import answer as answer_mod
from rag import retriever

LINEAR_RESULTS = Path("eval") / "results_he_linear.jsonl"
GOLDEN = Path("eval") / "golden_he.jsonl"
OUT = Path("eval") / "spot_check_agent.jsonl"
HIT_K = 5


def _load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _pick(linear: list[dict], n: int) -> list[dict]:
    """Pick the most informative failures, in order of expected agent impact:
    1. hit@5=False AND in-scope (R4 should recover via terminology/filter-relax)
    2. hit@5=True but correct=False (grading may keep better context for generate)
    """
    in_scope = [r for r in linear if r.get("category") == "in_scope" and "error" not in r]
    retrieval_miss = [r for r in in_scope if r.get(f"hit@{HIT_K}") is False]
    correct_miss = [r for r in in_scope if r.get(f"hit@{HIT_K}") is True and not r.get("correct")]

    picked: list[dict] = []
    for r in retrieval_miss:
        if len(picked) >= n:
            break
        picked.append(r)
    for r in correct_miss:
        if len(picked) >= n:
            break
        picked.append(r)
    return picked[:n]


def _retrieved_ids(question: str, lang: str) -> list[str]:
    return [str(c.meta.pageid) for c in retriever.retrieve(question, lang, top_k=HIT_K)]


def _evaluate_one(item: dict, gold_lookup: dict[str, dict]) -> dict:
    gold = gold_lookup[item["id"]]
    q, lang = gold["question"], gold["lang"]
    t0 = time.monotonic()
    a = answer_mod.answer_agent(q, lang)
    latency_s = time.monotonic() - t0

    retrieved = _retrieved_ids(q, lang)
    hit = metrics.hit_at_k(retrieved, gold["gold_doc_id"], HIT_K)

    if a.refused:
        correct = False
    else:
        judged = metrics.judge_in_scope(q, a.text, gold["gold_paragraph"])
        correct = judged.correct
    return {
        "id": item["id"],
        "question": q,
        "linear_hit": item.get(f"hit@{HIT_K}"),
        "linear_correct": item.get("correct"),
        "linear_latency_s": item.get("latency_s"),
        "agent_hit": hit,
        "agent_correct": correct,
        "agent_refused": a.refused,
        "agent_n_citations": len(a.citations),
        "agent_latency_s": round(latency_s, 2),
    }


def main(n: int = 10) -> None:
    linear = _load_jsonl(LINEAR_RESULTS)
    gold_lookup = {g["id"]: g for g in _load_jsonl(GOLDEN)}
    picked = _pick(linear, n)
    if not picked:
        raise SystemExit("No linear failures to spot-check.")

    print(f"Spot-checking {len(picked)} linear failures on the AGENT path:\n")
    rows: list[dict] = []
    with OUT.open("w", encoding="utf-8") as f:
        for i, item in enumerate(picked, 1):
            try:
                rec = _evaluate_one(item, gold_lookup)
            except Exception as exc:  # noqa: BLE001
                rec = {"id": item["id"], "error": f"{type(exc).__name__}: {exc}"}
            rows.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if "error" in rec:
                print(f"  [{i:>2}/{len(picked)}] {rec['id']:10s} ERROR: {rec['error']}",
                      flush=True)
            else:
                hit_arrow = "→".join([str(rec['linear_hit']), str(rec['agent_hit'])])
                corr_arrow = "→".join([str(rec['linear_correct']), str(rec['agent_correct'])])
                print(f"  [{i:>2}/{len(picked)}] {rec['id']:10s} hit:{hit_arrow:18s} "
                      f"correct:{corr_arrow:18s} ({rec['agent_latency_s']}s)",
                      flush=True)

    valid = [r for r in rows if "error" not in r]
    hit_recovered = sum(1 for r in valid if (not r["linear_hit"]) and r["agent_hit"])
    correct_recovered = sum(1 for r in valid if (not r["linear_correct"]) and r["agent_correct"])
    regressed = sum(1 for r in valid if r["linear_correct"] and not r["agent_correct"])
    mean_latency = sum(r["agent_latency_s"] for r in valid) / max(1, len(valid))

    print("\n" + "=" * 60)
    print(f"Summary over {len(valid)} cases:")
    print(f"  hit@{HIT_K} recovered: {hit_recovered}/{sum(1 for r in valid if not r['linear_hit'])} "
          f"(linear-miss → agent-hit)")
    print(f"  correctness recovered: {correct_recovered}/{sum(1 for r in valid if not r['linear_correct'])} "
          f"(linear-wrong → agent-correct)")
    print(f"  regressions: {regressed} (linear-correct → agent-wrong)")
    print(f"  mean agent latency: {mean_latency:.1f}s")
    print(f"\nResults JSONL: {OUT}")


def cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()
    main(args.n)


if __name__ == "__main__":
    cli()
