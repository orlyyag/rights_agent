# Progress

Status tracker for the Kol Zchut Rights Assistant. Updated as bricks land.
PLAN.md is the authoritative spec; this is the executive summary.

**Deadline:** Saturday 2026-06-13. **Today:** 2026-06-10 (Wed).
**Demo anchor:** `git checkout v0.1-tier0-demo` always returns to a working bot.

---

## Tier-0 POC ✅ Done · `v0.1-tier0-demo`

Live Hebrew Telegram bot, grounded + cited, against the official Webiks corpus
(24,487 chunks, May 2024 snapshot).

| Component | Status |
|---|---|
| Config + central LLM wrapper (`rag/llm.py`) — Gemini 3.5 Flash + `gemini-embedding-001` @3072, asymmetric task types, exponential-backoff retry, LangSmith `@traceable` | ✅ |
| Hebrew corpus → Chroma (`kz_corpus_he`), per-request active pointer (R7) | ✅ |
| Linear RAG: retrieve → grounded generate → ≤3 citations → refuse-if-empty | ✅ |
| Telegram bot (`python-telegram-bot` long-poll), HTML render with markdown→HTML conversion (R6), AI caveat + legal disclaimer (matches official KZ chat) | ✅ |
| Guardrails: allowlist (§0 #5), sliding-window rate cap, language detect, PII redaction for logs, too-short (3-word min), too-long (500-char max), terse one-sentence refusal template | ✅ |
| Bot lifecycle: idempotent `scripts/{run,stop,status}_bot.sh`, `drop_pending_updates=True`, `DEMO.md` runbook | ✅ |
| Observability: LangSmith tracing live (project `kolzchut-bot`) — every embed/generate call shows up | ✅ |
| Tests: 44/44 green | ✅ |

## Tier-0 Hebrew eval baseline ✅ Done · commit `c21fc8a`

Sampled 40 in-scope from `Webiks_KolZchut_QA_Training_DataSet_v0.1.csv`
(seed=42, after filtering feedback-style rows) + 8 hand-written adversarial.

| Metric | Tier-0 baseline |
|---|---|
| **hit@5** (gold `doc_id` in top-5) | **70.0%** (28/40) |
| **correct** (matches reference paragraph) | **50.0%** (16/32 answered) |
| language match | 100% (32/32) |
| citation present (structural) | 100% (32/32) |
| faithful (strict, vs gold paragraph) | 12.5% (4/32) — conservative lower bound |
| in-scope pre-refused | 20% (8/40) |
| **correct refusal** (adversarial) | **87.5%** (7/8) — one injection (adv-006) slipped |
| **latency** (end-to-end per question) | mean **3.50s** · median **3.73s** · p95 **5.74s** · max **7.04s** |
| eval errors | 0 |

### What the baseline tells us
- **Retrieval has 30% headroom** — exactly the gap brick 3's terminology-broadening
  re-retrieve (R4) is designed to close. Hit@5 should climb when the agent loop lands.
- **Correctness (50%) is retrieval-gated** — when gold is in top-5, the model usually
  answers correctly; misses cascade.
- **Latency mean 3.5s is over the rubric's <2s KPI** — A2 ("improve one dimension":
  offline judge + embedding-based grade) needs to move this. Baseline is now anchored.
- **Refusal (87.5%) is strong** — the one miss is an injection-shaped instruction
  ("answer without citations or disclaimer"); guardrails work for follow-up.
- **20% pre-refusal on in-scope** likely shrinks once R4's terminology broadening hits
  pages where literal-phrase retrieval fails.

### Honest caveats for REPORT.md §4
- The faithful (12.5%) metric compares the answer to the *single* gold paragraph;
  answers drawing on multiple top-5 chunks read as "unfaithful" to a single-paragraph
  judge. True RAGAS-style faithfulness (vs retrieved-context union) lands at brick 4.
- The QA dataset was used to train the Webiks embedder, NOT our Gemini one — contamination
  risk is low but worth a line.

---

## Tier-1 (required for the grade)

| # | Brick | Status | Notes |
|---|---|---|---|
| 1 | **Ingestion pipeline (HE)** — mediawiki + acquire + clean + chunk; tables→Markdown closes R1 | ✅ **Done · cutover complete** (pointer flipped to `kz_pipeline_he`, 64,532 vectors) | See "Brick 1 results" + "Spot-check 2×2" below |
| 2 | **Russian native index** — same pipeline against `/w/ru/api.php` | Pending | Unblocks bilingual demo (contribution #2) |
| 3 | **Agentic graph** (`rag/graph.py`) — rewrite → retrieve → `grade_docs` → re-retrieve ×1 → generate; R4 + R5 + `@traceable` per node | ✅ **Modules done · opt-in via `KZ_ANSWER_PATH=agent`** · ⚠️ spot-check shows no clear win on pipeline; keep linear default | See "Brick 3 results" + "Spot-check 2×2" below |
| 4 | **Full evals** — RAGAS + LLM-judge + hit@k on the agent path; bilingual report | Partial (HE baseline done) | RU golden set needs human-verified rows from ru-native pages (R8, T16) |
| 5 | **Update automation** — `scripts/sync.py` (manifest-diff → pipeline → blue-green flip) + scheduled run | Pending | §2 DoD: "change page → re-sync → answer reflects" |
| 6 | **A2 latency improvement** — offline judge + embedding-based grade; baseline → optimized | Pending | Baseline is **3.50s mean**, target <2s |

---

## Brick 1 results (this overnight session)

**All four ingestion modules implemented + tested** (`531f5be` → `b94a272`):

| Module | LOC | Tests | What it does |
|---|---|---|---|
| `ingest/mediawiki.py` | ~150 | 8 | WAF-safe KZ client: descriptive UA, ~1 req/s throttle, `maxlag=5`, exp-backoff retry on 429/503/network. Three ops: `manifest()` (paginated), `parse(pageid)` (HTML), `langlinks(pageid)` (cross-lingual R2). |
| `ingest/acquire.py` | ~150 | 8 | Manifest-diff (added/changed/deleted) + atomic per-page raw-layer write. Resumable + idempotent — Ctrl-C-safe, partial progress sticks. `acquire(lang, manifest_limit=None)` is the entrypoint; `scripts/acquire.py he` is the CLI. |
| `ingest/clean.py` | ~170 | 8 | HTML → `CleanedDoc(sections=[Section(heading, level, text)])`. Strips chrome (script/style/.mw-editsection/.navbox/.infobox/.toc/etc.) before any walk. **Tables → markdown** (numbers verbatim) — single-column tables fall back to bullets; pipes inside cells escaped. |
| `ingest/chunk.py` | ~140 | 8 | Section-based chunking ~512 tok with ~50-tok overlap (Q3). Each chunk prefixed `"PageTitle > Heading"` so the embedding catches topical context. Oversized paragraphs hard-split on sentence boundaries → words; no content silently lost. |

**Total: ~610 LOC + 32 ingestion tests.** Full test suite: **72/72 green**.

### R1 verified on real benefit pages

Tested three known benefit pages (`466 מענק לידה`, `6499 קצבת ילדים`, `1521 דמי אבטלה`). All three had tables and **all tables came through as markdown with every number preserved**:

```
| עבור לידת הילד הראשון במשפחה | 2,103 ₪ |
| עבור הילד השני במשפחה         |   946 ₪ |
| עבור הילד השלישי              |   631 ₪ |
| עבור לידת תאומים              | 10,514 ₪ |
| עבור לידת שלישייה             | 15,771 ₪ |
```

The Webiks corpus said 1,986 ₪ for the first-child grant (May 2024 snapshot — stale).
The pipeline pulls **2,103 ₪** (current).
**This is exactly the corpus→pipeline cutover motivation.** Every table-bearing demo question gets sharper numbers after the pipeline replaces the corpus.

### Cross-page sanity check

10 alphabetically-first HE pages walked through the full pipeline cleanly. 7/10 had ≥1-chunk overlap with the corpus for the same `pageid` (the 3 misses are pages created after May 2024 or differ substantially).

| pageid | title | sections | chunks | overlap w/ corpus |
|---|---|---|---|---|
| 11330 | "אפיקים בנגב" — שירות לאומי-אזרחי לצעירות מהחברה הבדואית | 8 | 7 | yes |
| 11351 | "אשר רוח בו" — מכינה קדם צבאית | 4 | 4 | yes |
| 21929 | "גניבת" לקוחות מהמעסיק | 6 | 5 | (post-May-2024) |
| 8225  | "גשר לעצמאות" | 12 | 10 | yes |
| 2119  | "הסכם הקשישים" של בנק לאומי | 4 | 6 | yes |
| 10311 | "חבר טלפוני" | 1 | 1 | (post-May-2024) |
| 8531  | "חוזרים לבית הספר" | 1 | 1 | (post-May-2024) |
| 11791 | "חיבורים" | 7 | 7 | yes |
| 10737 | "ידידים" | 3 | 3 | yes |
| 9870  | "יסודות לצמיחה" | 2 | 2 | yes |

### 🌙 Overnight HE crawl

Started a full HE crawl via `scripts/acquire.py he` in the background (pid **87650**, log: `data/acquire.log`). Expected **~2 hours** at 1 req/s for ~7,300 non-redirect content pages. Resumable — even if it crashes mid-way, the next run continues from the manifest.

```bash
# When you wake — check status:
pgrep -fl scripts/acquire           # still alive?
tail -20 data/acquire.log           # progress
ls data/raw/he | wc -l              # pages on disk
cat data/manifest/he.json | python3 -c "import sys, json; print(len(json.load(sys.stdin)), 'pages')"
```

**No embedding cost incurred overnight.** Embed is a separate explicit step once you wake — `python scripts/load_pipeline.py` (or equivalent — I haven't built the embed-driver yet; one-liner using `index.build_collection(chunks)` is enough).

If the crawl is still running when you wake: `tail -f data/acquire.log` to watch. If you want to stop it: `pkill -f 'scripts/acquire.py'`. To resume: re-run the same `python scripts/acquire.py he` command. State is in `data/manifest/he.json` and `data/raw/he/*.json`.

### What's NOT done in brick 1 (intentional handoff)

- **No embedding.** Cost ~$1-3 + decision is yours.
- **No `kz_pipeline_he` Chroma collection.** Once the crawl finishes, build with: `chunk.chunk_docs(acquire.iter_raw('he'))` → `index.build_collection(chunks, 'kz_pipeline_he')` → `config.set_active_collection('kz_pipeline_he')`.
- **No active-pointer flip.** Bot still serves from `kz_corpus_he`. Flipping is a one-liner once `kz_pipeline_he` is built and smoke-tested.
- **No automated `scripts/sync.py`.** That's brick 5 (update automation).

---

## Brick 3 results — LangGraph agentic loop (overnight, 4 commits)

**Topology B** wired per PLAN §6 / R4:

```
START → rewrite → retrieve → grade ─┬── generate → END
                                     ├── re_retrieve → retrieve → grade  (×1)
                                     └── refuse → END
```

| Module | LOC | Tests | What it does |
|---|---|---|---|
| `rag/grade.py` | ~140 | 9 | **ONE** batched LLM call grades every candidate for relevance + per-chunk reason + an overall failure mode that drives the re-retrieve transform. R3 (grade is the authoritative gate) + R4 (one batched call, not N). |
| `rag/rewrite.py` | ~130 | 7 | History-aware rewriter (R5). `rewrite_query()` condenses follow-ups + detects new-topic to prevent Frankenqueries; **no LLM call when history is empty** (Tier-0 cost preserved). `broaden_terminology()` is the second entrypoint used by re-retrieve. |
| `rag/graph.py` | ~190 | 13 | LangGraph compiled state machine; every node is `@traceable` so a Telegram turn produces a full trace tree in LangSmith. The re-retrieve picks `broaden_terminology` for `narrow_terminology` failures and **filter-relax** (R2/R4 unified) for `cross_lingual_thin`. Loop cap = `GRADE_LOOP_CAP` (default 1). |
| `rag/answer.py` | (extended) | 3 | `answer_agent(question, lang, history)` is a drop-in for the linear `answer()`. `answer_default(...)` routes by `config.ANSWER_PATH`. |
| `bot/handlers.py` | (1-line) | — | `build_reply` now calls `answer_default` → env-var flip switches every Telegram message over with no code change. |
| `rag/retriever.py` | (1-arg) | — | Added `relax_filter=False` kwarg (drops the lang `where` filter); used by the agent's cross-lingual fallback. |

**Total: ~460 new LOC + 32 mocked-LLM tests.** Full suite: **104/104 green**.

### How to flip the bot to the agent path

```bash
# 1. Add to .env (default is "linear")
echo "KZ_ANSWER_PATH=agent" >> .env

# 2. Restart the bot
scripts/run_bot.sh

# 3. Test on Telegram — and watch the trace tree in LangSmith
#    https://smith.langchain.com → kolzchut-bot project
```

To revert: change `agent` back to `linear` in `.env` and restart.

### Cost note before flipping

Each Telegram turn on the agent path does:
- 1 LLM call for rewrite (only if history is non-empty — Tier-0 saves this)
- 1 LLM call for grade_docs (batched over all candidates)
- 1 LLM call for generate
- **+1 LLM call** if re-retrieve fires (broaden_terminology) plus another grade

So worst case is **~4 calls per turn** vs Tier-0's **1 call**. With Gemini 3.5 Flash that's still a few cents per message — fine for a demo, worth confirming on volume.

### What's NOT done in brick 3 (intentional handoff)

- **No live spot-check yet.** Module + integration tests are all mocked. The agent's first real run against Gemini + Chroma is your decision — flip the env var and send a few Telegram messages.
- **No follow-up cases in the eval set yet.** The `eval/golden_he.jsonl` is single-turn. Once you spot-check the agent works, rerun `eval/run_eval.py` against the agent path (set `KZ_ANSWER_PATH=agent` in the env when running) to get the new hit@5 / correctness numbers — that's the brick-3 vs brick-0 delta that the rubric A2 wants.
- **No memory wiring from `bot/handlers.py` yet.** `bot/session.py` records turns but `handlers.build_reply` doesn't pass history into the answer call. Trivial change once you opt in: pass `session.history(chat_id)` to `answer_default`.
- **`bot/handlers.py` is the right place to thread memory.** One line: `answer_fn(text, lang, history=session.history(chat_id))` after extending `answer_default` to accept history. Skipped to keep the linear path API stable.

---

- **No embedding.** Cost ~$1-3 + decision is yours.
- **No `kz_pipeline_he` Chroma collection.** Once the crawl finishes, build with: `chunk.chunk_docs(acquire.iter_raw('he'))` → `index.build_collection(chunks, 'kz_pipeline_he')` → `config.set_active_collection('kz_pipeline_he')`.
- **No active-pointer flip.** Bot still serves from `kz_corpus_he`. Flipping is a one-liner once `kz_pipeline_he` is built and smoke-tested.
- **No automated `scripts/sync.py`.** That's brick 5 (update automation).

---

## Full Hebrew eval — linear + pipeline (this morning)

All 48 questions from `golden_he.jsonl` against the pipeline collection (`kz_pipeline_he`, 64,532 vectors). Compare to the linear+corpus baseline from `c21fc8a`:

| Metric | linear + corpus | linear + pipeline | Δ |
|---|---|---|---|
| hit@5 | 70.0% (28/40) | 70.0% (28/40) | same |
| correct (over **all** in-scope) | **40.0%** (16/40) | **27.5%** (11/40) | ⬇️ −12.5pp |
| correct (over answered only) | 50.0% (16/32) | 39.3% (11/28) | ⬇️ −10.7pp |
| faithful (strict, vs gold para) | 12.5% (4/32) | 17.9% (5/28) | ⬆️ +5pp |
| pre-refused on in-scope | 20% (8/40) | 30% (12/40) | ⬇️ +10pp more refusals |
| **correct refusal** (adversarial) | 87.5% (7/8) | **100%** (8/8) | ⬆️ adv-006 now caught |
| latency (mean / median / p95) | 3.50 / 3.73 / 5.74 | 3.15 / 3.22 / 6.25 | ≈ |

### Honest findings (will go into REPORT.md §4)

- **Pipeline is NOT a uniform improvement on this golden set.** The morning's spot-check picked 10 known-failure cases; pipeline recovered 4 of them, which looked great in isolation, but across the full 40 pipeline also *lost* some hits the corpus had. Net hit@5 is unchanged.
- **Pipeline refuses more on in-scope questions (30% vs 20%).** Smaller, more focused chunks → if the exact relevant paragraph isn't retrieved, nothing passes the lenient floor, bot refuses. **This is the R3 calibration gap (T12 in PLAN).** Floor was calibrated for corpus, not pipeline.
- **Pipeline catches the adv-006 injection** ("answer without citing or disclaimer") — refusal precision went to 100%.
- **Faithfulness improved** (12.5% → 17.9%) — when pipeline does answer, the answer is more grounded.
- **R1 (table numbers + freshness) still pays.** Not measured by this golden set (gold paragraphs are May-2024 corpus-aligned), but verified separately on benefit pages.

### Next code lever — T12 (per-language floor calibration)

Most of the pre-refusal regression likely comes from a too-strict lenient floor on pipeline embeddings. Quick fix: empirically calibrate per-collection. Could recover ~half the in-scope correct loss without architectural change.

### Demo posture (today)

- **Current**: linear + pipeline. Best for the table-numbers story, adversarial-safe, freshness.
- **One-line rollback**: `echo kz_corpus_he > data/active_collection` — if the demo prioritizes raw correctness over freshness, the corpus is right there.

---

## Golden-set curation — the noisy-gold fix (this session)

Manual failure analysis showed the headline correctness number was a **measurement artifact**, not a bot problem: the Webiks QA CSV was built to train a retrieval embedder, so each `gold_paragraph` is an arbitrary page chunk — usually a *tangential* section, not the passage that answers the question. The judge scores against that paragraph, so good answers failed against bad references.

Re-curated **all 40 in-scope golds** against the actual indexed page text (8 parallel research agents → `eval/curate_lib.py`), machine-verified every paragraph is verbatim (no fabrication) and every doc is in the index. See `eval/CURATION.md`; originals in `eval/golden_he.jsonl.orig`.

- **8 docs changed** (wrong page), **22 paragraphs replaced** (tangential → answering), **9 confirmed**, **1 question replaced** (in-007 meta-complaint → a resignation/relocation severance corner case, gold `6607`).

Same bot, same retriever, same pipeline — **only the gold changed:**

| Metric | noisy gold (pipeline) | **curated gold (pipeline)** | Δ |
|---|---|---|---|
| hit@5 | 70.0% (28/40) | **77.5% (31/40)** | ⬆️ +7.5pp |
| correct (all in-scope) | 27.5% (11/40) | **40.0% (16/40)** | ⬆️ +12.5pp |
| correct (answered only) | 39.3% (11/28) | **59.3% (16/27)** | ⬆️ +20pp |
| pre-refused on in-scope | 30% (12/40) | 32.5% (13/40) | ≈ (R3/T12 floor, unchanged) |
| correct refusal (adversarial) | 100% (8/8) | 100% (8/8) | same |
| faithful (strict, vs gold para) | 17.9% (5/28) | 3.7% (1/27) | ⬇️ **metric artifact** — see below |

- **+5 `correct` flips** (in-004/012/015/021/027/029) were all bot answers the noisy gold wrongly failed — confirms the bot was being under-credited.
- **hit@5 +3 net** = 4 gains from fixing wrong/missing gold docs − **1 honest loss** (in-008: gold moved to the page that actually defines the term, which the retriever doesn't surface — kept the correct gold, not a retrieval-friendly one).
- **faithful (strict) collapse is a metric bug, not a regression:** focused golds are short, but the bot answers from the whole page, so "every claim supported by *this one paragraph*" now fails for correct answers. Metric should be redefined as grounded-in-the-cited-sources, not grounded-in-one-paragraph.
- **Pre-refusal still ~32%** — flagged T12 (floor calibration) as the next lever. *(The metrics-redesign session below disproved that — see "T12 disproved".)*

---

## Eval metrics redesign + over-refusal fix (this session)

Rebuilt the eval metrics from scratch (spec + plan in `docs/superpowers/specs|plans/2026-06-10-eval-metrics-*`), then used the new measurement to find and fix the real refusal bug. ~20 commits on branch `eval/metrics-and-floor-calibration`, full suite green (125 tests).

### 1. Metric harness — heuristics vs cross-provider judge

The old eval was one Gemini call grading against a single `gold_paragraph`; it mis-assigned every metric. Reassigned by mechanism:

- **Heuristics** (`src/eval/metrics/heuristics.py`, pure, no LLM): hit@5, recall@5, MRR (over a gold-doc *set*), citation present/valid, language (Hebrew-script ratio), and the **false-vs-justified refusal split**. Citation + language used to be *LLM-judged* — now free and deterministic.
- **Judges** (`src/eval/metrics/judges.py`, RAGAS-shaped, Hebrew prompts) on a **cross-provider OpenAI `o4-mini`** judge (`src/eval/judge_llm.py`, eval-only — the bot stays 100% Gemini, so the judge has no self-preference): per-claim **faithfulness vs the retrieved context**, `answer_relevancy`, `answer_correctness`.
- **`run_eval` now captures the retrieved context** (chunk text), not just doc_ids — required to judge faithfulness against what the generator actually saw.

Two judge bugs were caught by **live testing, not the plan** (the bot never regressed — the judges were wrong): `answer_correctness` was unstable and re-created the old artifact (docking points for correct detail beyond the narrow gold) → reformulated as a boolean *contradiction* check; the refusal judge misread textbook refusals → clarified that an off-topic-but-answerable refusal is correct. This is exactly why calibration (next) matters.

**The headline fix:** `faithfulness` went from a meaningless **3.7% → ~100%** once judged per-claim against the retrieved context instead of the narrow gold paragraph.

### 2. T12 disproved — the floor was a red herring

`scripts/calibrate_floor.py` swept the cosine floor and **disproved the long-standing hypothesis**:

- All 40 in-scope gold chunks score **0.67–0.84** — far above the 0.35 floor (it cuts *nothing*).
- Adversarial top-1 scores **0.60–0.70** — they *overlap* in-scope, so cosine **cannot** separate them. Refusal safety comes from generation-time semantics, not a threshold.

Tracing the 7 false refusals: **0 were floor cuts.** 5 were **generation over-refusal** (the answer *was* in the retrieved context, but Gemini refused unless it appeared verbatim) and 2 were chunk-level retrieval gaps. So the fix was a prompt change, not a floor change. `SIMILARITY_FLOOR_BY_LANG` left at 0.35.

### 3. The real fix — relax the generation refusal, guard advice

[prompts.py](src/rag/prompts.py) `_SYSTEM`: now permits **applying stated rules/definitions to the user's case** (not just verbatim echo), and refuses only when sources are genuinely off-topic. A spot-check caught the relaxed prompt starting to *answer* adv-007 ("should I marry?"), so an explicit **personal-advice/opinion guard** was added — subjective questions still refuse even when related legal sources exist.

### Results — same bot+retriever, before vs after the prompt fix (linear, curated gold, o4-mini judge)

| Metric | strict prompt | **relaxed + guard** | Δ |
|---|---|---|---|
| in-scope answered | 28 | **34** | +6 recovered |
| **false refusals** (gold retrieved, bot refused) | 7/40 | **1/40** | −6 ✅ |
| **faithfulness** (per-claim vs context) | 99.6% | **100.0%** (34/34) | no hallucination from the relax |
| answer_correctness | 71.4% | **73.5%** (34) | held, +6 harder items |
| answer_relevancy | 86.8% | 80.6% | slight dip (more answered) |
| **adversarial refusal** | 100% (8/8) | **100% (8/8)** | safety preserved (advice guard) |
| hit@5 / recall@5 / MRR | 80% / 80% / 0.58 | 80% / 80% / 0.58 | unchanged (retrieval untouched) |

**The one residual false refusal is in-032** — a genuine *chunking* gap: the sick-day accrual chunk isn't retrievable for "how do I compute sick hours to days?" even at top-15. Documented as a known limit (needs chunking work, not a top-k bump). The 5 justified refusals (in-003/016/026/028/040) are correct — the gold page isn't retrieved at all.

### Still open
- **Task 8 — judge calibration:** worksheet generated (`eval/calibration_worksheet.txt`, 25 items); awaiting human labels → write `eval/calibration_he.jsonl` → the report auto-emits Cohen's κ + accuracy vs the o4-mini judge. This is the validation anchor.
- **Task 9 — RAGAS sanity sample: DROPPED.** Real `ragas` won't install here (no `scikit-network` wheel on Py3.14; conflicts with the released langchain v1 on 3.13). We use custom Hebrew-aware RAGAS-style judges as primary and human calibration as the cross-check. `ragas` commented out of `requirements.txt`.
- **Agent path** eval parked by choice; **in-032 chunking** is a follow-up.

---

## Full LangSmith observability — verified live

Every Telegram message and eval question now produces a complete trace tree with thread_id, model name, token counts, $ cost, and latency per node. Verified:

```
agent:run                   thread=verify_agent_001    tok=5651   $0.0156   9.2s
  LangGraph                                              tok=5651   $0.0156
    generate                                             tok=2998   $0.0098
    grade                                                tok=2653   $0.0059
    retrieve                                             tok=   0   $0.0000
    rewrite                                              tok=   0   $0.0000
answer:linear               thread=verify_linear_001   tok=3201   $0.0100   9.8s
    generate    model=gemini-3.5-flash                   tok=3201   $0.0100
    retrieve                                             tok=   0   $0.0000
      embed     model=gemini-embedding-001               tok=   0   $0.0000
```

- **Per-question cost**: linear $0.010 · agent $0.016 (~56% more expensive — agent has rewrite + grade + generate)
- **Thread IDs**: `eval:in-001` for eval questions, `chat:<chat_id>` for Telegram, `spot_check:<id>` for spot-checks. Filterable in LangSmith UI.
- **Cost roll-up**: parent traces sum child costs. The dashboard now answers "what did this run cost?" for free.

---

## Spot-check 2×2 — pipeline cutover + agent loop

Sample of 10 in-scope questions where **linear + corpus failed retrieval** (the most informative cases for testing brick 1 + brick 3). All four cells scored on the same 10 cases:

| | hit@5 | correct | mean latency |
|---|---|---|---|
| **linear + corpus** (baseline) | 0/10 | 0/10 | 3.6s (from baseline run) |
| **agent + corpus** | 0/10 | 2/10 | 7.2s |
| **linear + pipeline** | **4/10** | **3/10** | ~3s |
| **agent + pipeline** | 4/10 | 2/10 | ~5s |

### Conclusions

1. **Brick 1 (pipeline cutover) is the headline win.** Recovered **40% of retrieval misses** and **30% of correctness misses** on cases the corpus couldn't handle. This is the R1 + chunking + freshness hypothesis paying off in real numbers.
2. **Brick 3 (agent loop) gives a modest correctness lift on the corpus** (0→2/10) but doesn't compound on the pipeline — likely because R4's terminology-broaden runs on the *same* collection and can't fix "the answer isn't there." Agent helped most where the grader kept smarter context, not where retrieval was lacking.
3. **Agent latency on pipeline is workable** (~3-7s/question), much better than the 44.9s outlier from the initial sanity test (TPM contention with the running embed was the cause).
4. **Bot serves `linear + pipeline` by default** — that's the best-evidenced quality and the cheapest per-message. `KZ_ANSWER_PATH=agent` stays opt-in for future investigation (cross-lingual, follow-ups, where the agent has more room to help).

### Where the agent will likely *actually* matter (untested today)

- **Follow-up questions** (R5) — our golden set is single-turn, so the rewrite node never fires. A two-turn case like *"מה מגיע לי אחרי לידה?"* → *"ולעצמאים?"* would force the rewrite to condense, which the linear path can't do.
- **Cross-lingual** (R2) — none of our 10 cases were Russian-thin; the filter-relax path didn't get exercised.
- **Adversarial precision** — the agent's `grade_docs` returning `wrong_topic` is a different refusal mechanism than the linear path's template; the eval's adversarial set was already 7/8 on linear so there's little room to show improvement.

These are the right brick-3 evals to build for REPORT.md §4 in the coming days (T13).

---

## Cost spent this morning

- Pipeline embed (64,532 chunks × ~250 tok @ $0.15/1M): **~$2.40**
- 4 spot-check runs (2 cells × 10 questions × ~4 LLM calls + 2 judge calls): **~$0.05**
- **Total morning: ~$2.45**

---

## Human-only critical path (won't progress without you)

These can't be fanned out to CC. From PLAN.md A4 / T16 / R8:

- **2 stakeholder interviews** (ru-speaker / KZ user / social worker) — 15% of the grade
  (Market Research & Technical Discovery). Notes go to REPORT.md §2.
- **Russian golden set** (~20–30 questions from ru-native pages) — required for the
  bilingual eval claim. Hand-verify each.
- **Business-KPI numbers** for REPORT.md §4 (productivity/access estimates + KZ
  operational savings).
- **Pitch deck + backup demo video** Friday.

---

## Pre-demo checklist (anytime)

```bash
caffeinate -d -i &              # critical — laptop sleep kills the demo
scripts/status_bot.sh           # ✓ Bot is running …
# tail -f data/bot.log in another terminal for live monitoring
```
