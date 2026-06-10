"""Re-run the linear eval for a SINGLE golden id and patch its line in
``eval/results_he_linear.jsonl`` in place. Used after swapping one golden item
(in-007) so we don't re-run all 48.

    PYTHONPATH=.:src python eval/rerun_one.py in-007
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from eval.run_eval import _eval_one, _answer_fn, GOLDEN_PATH

RESULTS = Path("eval") / "results_he_linear.jsonl"


def main(target_id: str) -> None:
    items = {json.loads(l)["id"]: json.loads(l)
             for l in GOLDEN_PATH.open(encoding="utf-8") if l.strip()}
    item = items[target_id]
    rec = _eval_one(item, _answer_fn("linear"))
    rec["answer_path"] = "linear"

    rows = [json.loads(l) for l in RESULTS.open(encoding="utf-8") if l.strip()]
    replaced = False
    for i, r in enumerate(rows):
        if r.get("id") == target_id:
            rows[i] = rec
            replaced = True
    if not replaced:
        rows.append(rec)
    with RESULTS.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    marker = (f"hit@5={rec.get('hit@5')} correct={rec.get('correct')} "
              f"refused={rec.get('answer_refused')}")
    print(f"Patched {target_id}: {marker}  ({rec['latency_s']}s)")
    print("Q:", item["question"])
    print("A:", (rec["answer_text"] or "")[:400])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "in-007")
