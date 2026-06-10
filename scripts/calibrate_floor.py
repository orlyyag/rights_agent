"""T12 — calibrate the per-language cosine floor.

Dumps the gold-chunk similarity for in-scope questions and the top-1 similarity
for adversarial questions, then sweeps candidate floors and picks the one that
keeps the most in-scope while cutting ALL adversarial (preserve 100% refusal).

    PYTHONPATH=.:src python scripts/calibrate_floor.py he
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import config
from rag import retriever

GOLDEN = Path("eval") / "golden_he.jsonl"
CANDIDATES = [round(x / 100, 2) for x in range(15, 56, 1)]  # 0.15 … 0.55


def best_floor(inscope_scores, adversarial_scores, candidates=CANDIDATES) -> float:
    """Highest-recall floor that still cuts every adversarial.

    Prefer the LOWEST floor that cuts all adversarial (keeps the most in-scope).
    If no floor cleanly separates them, fall back to the floor that maximizes
    (in-scope kept − adversarial kept).
    """
    viable = [c for c in candidates if all(a < c for a in adversarial_scores)]
    if viable:
        return min(viable)
    def margin(c):
        return sum(s >= c for s in inscope_scores) - sum(s >= c for s in adversarial_scores)
    return max(candidates, key=margin)


def _gold_score(question, lang, gold_ids):
    chunks = retriever.retrieve(question, lang, top_k=10)
    gold = {str(g) for g in (gold_ids if isinstance(gold_ids, (list, set)) else [gold_ids])}
    for c in chunks:
        if str(c.meta.pageid) in gold:
            return c.score
    return chunks[0].score if chunks else 0.0   # gold not retrieved → top-1 as proxy


def main(lang: str = "he") -> None:
    rows = [json.loads(l) for l in GOLDEN.open(encoding="utf-8") if l.strip()]
    inscope, adversarial = [], []
    for r in rows:
        if r["category"] == "in_scope":
            inscope.append(_gold_score(r["question"], lang,
                                       r.get("gold_doc_ids") or r["gold_doc_id"]))
        else:
            chunks = retriever.retrieve(r["question"], lang, top_k=1)
            adversarial.append(chunks[0].score if chunks else 0.0)
    floor = best_floor(inscope, adversarial)
    ins = sorted(inscope)
    print(f"in-scope gold scores: min={ins[0]:.3f} "
          f"median={ins[len(ins)//2]:.3f} max={ins[-1]:.3f}")
    print(f"adversarial top-1:    max={max(adversarial):.3f} "
          f"(all: {', '.join(f'{a:.3f}' for a in sorted(adversarial))})")
    print(f"current floor[{lang}]: {config.SIMILARITY_FLOOR_BY_LANG.get(lang)}")
    kept_now = sum(s >= config.SIMILARITY_FLOOR_BY_LANG.get(lang, 0.35) for s in inscope)
    kept_new = sum(s >= floor for s in inscope)
    print(f"in-scope above current floor: {kept_now}/{len(inscope)}  →  "
          f"above recommended: {kept_new}/{len(inscope)}")
    print(f"RECOMMENDED floor[{lang}] = {floor}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "he")
