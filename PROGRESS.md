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
| 1 | **Ingestion pipeline (HE)** — mediawiki + acquire + clean + chunk; tables→Markdown closes R1 | ✅ **Modules done + R1 verified** · 🌙 full HE crawl running overnight | See "Brick 1 results" below |
| 2 | **Russian native index** — same pipeline against `/w/ru/api.php` | Pending | Unblocks bilingual demo (contribution #2) |
| 3 | **Agentic graph** (`rag/graph.py`) — rewrite → retrieve → `grade_docs` → re-retrieve ×1 → generate; R4 + R5 + `@traceable` per node | ✅ **Modules done · opt-in via `KZ_ANSWER_PATH=agent`** | See "Brick 3 results" below — bot stays on linear path until you flip |
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
