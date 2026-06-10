# Eval metrics redesign + T12 floor calibration — design

**Date:** 2026-06-10 · **Status:** approved (design), pending spec review
**Author:** Claude (Opus 4.8) with the user

## Problem

The eval (`src/eval/metrics.py`) is a single-call Gemini judge returning
`{correct, language_match, faithful, has_citation}` against one `gold_paragraph`,
plus a `hit@k` heuristic. After the golden-set curation
([eval/CURATION.md](../../../eval/CURATION.md)) two structural problems surfaced:

1. **`faithful` is broken.** It checks every answer claim against the *one short
   gold paragraph*, but the bot answers from the *whole retrieved context*. With
   focused golds it collapsed to 3.7% — a measurement artifact, not a regression.
2. **Metrics are mis-assigned to mechanism.** `has_citation` and `language_match`
   are LLM-judged even though they're deterministically knowable (we already store
   `answer_n_citations`, `answer_citation_urls`, and the answer text). Meanwhile the
   thing that *needs* semantic judgment (faithfulness) uses the wrong reference.
3. **Refusal accounting is coarse.** All in-scope refusals are counted as misses,
   conflating *justified* refusals (no supporting page exists) with *false*
   refusals (gold was retrieved, bot refused anyway). Only the latter is the bug.
4. **Judge self-bias + no error bars.** The same Gemini Flash both generates and
   judges; the judge numbers have unknown agreement with humans.

Separately, **T12**: on the linear path the cosine **similarity floor (0.35)** is
the refuse gate (`retriever` drops chunks `< floor` → `answer.py` refuses on empty).
It was calibrated for the old corpus and is too strict for the pipeline embeddings,
driving ~32% in-scope pre-refusal.

## Goals

- Fix `faithful`; re-assign every metric to the right mechanism (heuristic vs judge).
- Add a rigorous, **calibrated** judge suite (RAGAS-shaped) using a **cross-provider
  judge (OpenAI `o4-mini`)**, independent of the Gemini generator.
- Add the **false-vs-justified refusal split** so refusal quality is legible.
- Calibrate the per-language similarity floor (**T12**) to recover false refusals
  *without* losing the 100% adversarial-refusal property — measured by the new split.

## Non-goals

- Changing the production answer path's model (bot stays 100% Gemini; OpenAI is
  **eval-only**).
- Russian metrics (he-only for this pass; modules stay lang-parametric).
- Replacing `hit@k` — we extend it (gold-doc *set*, recall@k, MRR), not remove it.

## Decisions (locked)

| Fork | Decision |
|---|---|
| Judge implementation | **Custom Hebrew-aware judges** on a new eval judge wrapper, shaped like RAGAS, **+ a real-RAGAS sanity sample** (~10 items) as a cross-check |
| Judge model | **OpenAI `o4-mini`** (reasoning model; cross-provider → no self-bias). Low reasoning effort for cost. `OPENAI_API_KEY` from `.env`, model via `OPENAI_JUDGE_MODEL` |
| Calibration anchor | ~25 human-labeled `(answer, correct?)` pairs; report Cohen's κ + accuracy of the judge vs human |

## Architecture

Two phases. Phase 1 builds the measurement; Phase 2 uses it to tune the floor.

### Phase 1 — metric harness

New, small, single-purpose units:

- **`src/eval/judge_llm.py`** — OpenAI client wrapper (lazy client, retry/backoff,
  LangSmith `@traceable`, structured-output/JSON). Mirrors `rag.llm` shape so it's
  monkeypatchable in tests. Reads `OPENAI_API_KEY`; model from `config.OPENAI_JUDGE_MODEL`
  (default `o4-mini`). **Eval-only — never imported by the bot path.**
- **`src/eval/metrics/heuristics.py`** — pure functions, no LLM:
  `hit_at_k`, `recall_at_k`, `mrr` (over a gold-doc *set*), `context_precision_at_k`
  (from per-chunk relevance labels), `citation_present`, `citation_valid`
  (URL resolves / is among retrieved sources), `language_match` (Hebrew-script ratio),
  `refusal_kind` → `{false_refusal | justified_refusal | answered}`
  (`refused ∧ hit@k` = false).
- **`src/eval/metrics/judges.py`** — OpenAI-judged, RAGAS-shaped, Hebrew prompts,
  forced structured output:
  - `faithfulness(answer, retrieved_context)` — **per-claim entailment**: extract
    atomic claims → verify each against the context → `supported / total`.
  - `answer_relevancy(question, answer)` — addresses the question? (no gold).
  - `answer_correctness(question, answer, gold_paragraph)` — agrees with gold, graded 0–1.
  - `refusal_correctness(question, answer)` — refused without fabricating (adversarial).
- **`src/eval/metrics/calibration.py`** — load `eval/calibration_he.jsonl`
  (human labels), compute κ / accuracy / confusion vs the judge; optional 2nd judge
  (Gemini Pro) for inter-judge agreement on the same set.
- **`src/eval/ragas_sample.py`** — run real `ragas` (on OpenAI) over ~10 items for
  faithfulness + answer_relevancy; emit a small comparison table vs our custom judges.

**Context capture (the one architectural change).** `run_eval._eval_one` currently
stores `retrieved_doc_ids` only. Faithfulness and context_precision need the actual
**chunk texts the generator saw** and the **cited pages**. The answer path already
builds these; we surface them on the returned answer object (or recompute via the same
retrieve call) and persist `retrieved_context` (list of `{doc_id, title, text}`) +
`cited_doc_ids` into the results JSONL. No bot behavior change.

**`report.py`** aggregates the new metrics and adds a **calibration block** (κ +
accuracy per judged metric) and the refusal split. `metrics.py` becomes a thin
shim re-exporting from `eval/metrics/*` (back-comat) or is replaced; tests updated.

### Phase 2 — T12 floor calibration

1. **Instrument:** a script dumps, per golden question, the retrieved cosine scores
   (in-scope: the score of the gold chunk if present + top-1; adversarial: top-1).
2. **Choose:** pick `SIMILARITY_FLOOR_BY_LANG["he"]` that maximizes in-scope
   *answered-and-correct* while keeping adversarial top-1 below the floor
   (preserve 100% correct refusal). Likely a sweep over candidate floors with the
   Phase-1 metrics as the objective.
3. **Set & verify:** update `config.SIMILARITY_FLOOR_BY_LANG`, re-run the eval, and
   confirm: false_refusal ↓, justified_refusal ~unchanged, adversarial refusal = 100%.

Success is defined by Phase-1 metrics, so Phase 1 lands first.

## Data flow (Phase 1, per question)

```
question ─▶ retrieve(top-k) ─▶ [chunks: doc_id,title,text,score] ─▶ answer(text,citations,refused)
                 │                          │                               │
            heuristics:                 persisted as                   heuristics:
            hit/recall/mrr           retrieved_context              citation_*, language, refusal_kind
                                            │
                                   OpenAI judges (o4-mini):
                            faithfulness(answer, context),
                            answer_relevancy(question, answer),
                            answer_correctness(question, answer, gold)
                                            │
                                   calibration: judge vs human κ
```

## Error handling

- Judge call fails after retries → metric recorded as `null` (not `false`), excluded
  from aggregates, surfaced in the report's "errors" row. (Current code coerces to
  `false`, which silently depresses scores.)
- Missing `OPENAI_API_KEY` → judges skip with a clear message; heuristics still run,
  so the eval degrades gracefully to retrieval + format metrics.
- Structured-output parse failure → one reformat retry, then `null`.

## Testing

- `heuristics.py`: pure unit tests (hit/recall/mrr/citation/language/refusal_kind) —
  deterministic, no network.
- `judges.py`: monkeypatch the judge client; assert prompt assembly + parsing +
  null-on-failure. One opt-in live smoke test gated on `OPENAI_API_KEY`.
- `calibration.py`: κ/accuracy math on a tiny fixture.
- T12: a test that the floor sweep picks the expected floor on a synthetic score set.

## File map

```
src/eval/judge_llm.py            (new)  OpenAI judge wrapper, eval-only
src/eval/metrics/__init__.py     (new)
src/eval/metrics/heuristics.py   (new)  pure metrics
src/eval/metrics/judges.py       (new)  o4-mini RAGAS-shaped judges
src/eval/metrics/calibration.py  (new)  κ / accuracy vs human
src/eval/ragas_sample.py         (new)  real-RAGAS cross-check (~10 items)
src/eval/run_eval.py             (edit) capture retrieved_context + cited_doc_ids
src/eval/report.py               (edit) new metrics + calibration block
src/eval/metrics.py              (edit) shim → eval/metrics/* (back-compat)
config.py                        (edit) OPENAI_JUDGE_MODEL; T12 floor values
.env.example                     (edit) OPENAI_API_KEY
eval/calibration_he.jsonl        (new)  ~25 human-labeled answers
scripts/calibrate_floor.py       (new)  T12 score dump + sweep
tests/eval/...                   (new)  unit tests per module
```

## Risks

- **o4-mini latency/cost:** reasoning tokens make each judge call slower/pricier than
  Flash. Mitigate: low reasoning effort, batch where possible, judge only answered
  items, cache by `(answer, context)` hash within a run.
- **Hebrew judging quality:** o4-mini is multilingual but Hebrew legal nuance is hard.
  The human-calibration κ is exactly the guard — if κ is low we revise prompts.
- **Context capture coupling:** must surface the generator's context without changing
  bot behavior; keep it additive on the answer object.
```
