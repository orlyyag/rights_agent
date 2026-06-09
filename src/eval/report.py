"""Aggregate ``eval/results_he.jsonl`` into a markdown baseline report.

Run (from repo root):
    PYTHONPATH=.:src python -m eval.report
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

RESULTS_PATH = Path("eval") / "results_he.jsonl"
REPORT_PATH = Path("eval") / "report_he.md"
HIT_K = 5


def _load(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _pct(num: int, denom: int) -> str:
    if not denom:
        return "n/a"
    return f"{100 * num / denom:.1f}% ({num}/{denom})"


def _stats(values: list[float]) -> str:
    if not values:
        return "n/a"
    values = sorted(values)
    n = len(values)
    median = values[n // 2]
    mean = statistics.mean(values)
    p95 = values[min(n - 1, int(0.95 * n))]
    return f"mean={mean:.2f}s · median={median:.2f}s · p95={p95:.2f}s · max={values[-1]:.2f}s"


def _table(rows: list[tuple[str, str]]) -> str:
    return "| Metric | Value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows)


def main() -> None:
    records = _load(RESULTS_PATH)
    errors = [r for r in records if "error" in r]
    in_scope = [r for r in records if r.get("category") == "in_scope" and "error" not in r]
    adv = [r for r in records if r.get("category") == "adversarial" and "error" not in r]

    n_inscope, n_adv = len(in_scope), len(adv)

    # Retrieval
    hits = sum(1 for r in in_scope if r.get(f"hit@{HIT_K}"))

    # Answer quality (only on in-scope items where the bot didn't pre-refuse)
    answered = [r for r in in_scope if not r.get("answer_refused")]
    correct = sum(1 for r in answered if r.get("correct"))
    faithful = sum(1 for r in answered if r.get("faithful"))
    lang_ok = sum(1 for r in answered if r.get("language_match"))
    # Structural fact (citations attach to the Answer object, rendered by render_answer);
    # the LLM-judge sees only body text and was reporting 0% — false negative. The structural
    # count is the ground truth.
    cited = sum(1 for r in answered if (r.get("answer_n_citations") or 0) > 0)
    refused_in_scope = sum(1 for r in in_scope if r.get("answer_refused"))

    # Refusals
    refused_correctly = sum(1 for r in adv if r.get("refused_correctly"))

    # Latency
    latencies = [r["latency_s"] for r in records if "latency_s" in r]

    md = [
        "# Hebrew evaluation — Tier-0 baseline",
        "",
        f"Linear retrieve → generate → cite path (`rag/answer.py`), corpus index "
        f"`kz_corpus_he` (Webiks May-2024 corpus, 24,487 chunks). Golden set: "
        f"{n_inscope} in-scope (random sample, seed=42, from "
        f"`Webiks_KolZchut_QA_Training_DataSet_v0.1.csv` after cleaning) + "
        f"{n_adv} hand-written adversarial.",
        "",
        "## Retrieval",
        _table([
            (f"hit@{HIT_K} (gold `doc_id` in top-{HIT_K})", _pct(hits, n_inscope)),
        ]),
        "",
        "## Answer quality (in-scope, judged via Gemini)",
        _table([
            ("correct (matches reference paragraph)", _pct(correct, len(answered))),
            ("faithful (every claim supported by gold paragraph — strict)", _pct(faithful, len(answered))),
            ("language match (answer in Hebrew)", _pct(lang_ok, len(answered))),
            ("citation present", _pct(cited, len(answered))),
            ("in-scope items the bot pre-refused (likely false negative)", _pct(refused_in_scope, n_inscope)),
        ]),
        "",
        "## Refusals (adversarial / off-topic)",
        _table([("correct refusal", _pct(refused_correctly, n_adv))]),
        "",
        "## Latency (end-to-end per question, baseline for A2)",
        _table([("p50/p95/max", _stats(latencies))]),
        "",
        "## Errors",
        _table([("eval errors", str(len(errors)))]),
        "",
    ]

    # Worst-N for triage
    misses = [r for r in in_scope if not r.get(f"hit@{HIT_K}")]
    if misses:
        md.append(f"## Retrieval misses ({len(misses)} items)\n")
        md.append("Gold `doc_id` not in top-K — these point at chunking/embedding issues.")
        md.append("")
        md.append("| id | gold_doc_id | question |")
        md.append("|---|---|---|")
        for r in misses[:15]:
            q = r["question"][:90] + ("…" if len(r["question"]) > 90 else "")
            md.append(f"| {r['id']} | (gold not retrieved) | {q} |")
        if len(misses) > 15:
            md.append(f"| … | … | (+{len(misses) - 15} more) |")
        md.append("")

    adv_failures = [r for r in adv if not r.get("refused_correctly")]
    if adv_failures:
        md.append(f"## Adversarial failures ({len(adv_failures)} items)\n")
        md.append("| id | subkind | question |")
        md.append("|---|---|---|")
        for r in adv_failures:
            q = r["question"][:90] + ("…" if len(r["question"]) > 90 else "")
            md.append(f"| {r['id']} | {r.get('subkind', '')} | {q} |")
        md.append("")

    if errors:
        md.append("## Pipeline errors\n")
        for r in errors:
            md.append(f"- `{r['id']}`: {r['error']}")

    REPORT_PATH.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print("\n" + "\n".join(md[:20]))


if __name__ == "__main__":
    main()
