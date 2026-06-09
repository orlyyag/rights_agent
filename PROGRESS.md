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
| 1 | **Ingestion pipeline (HE)** — mediawiki + acquire + clean + chunk; tables→Markdown closes R1 | 🚧 In progress (overnight) | Modules + small validation tonight; full HE crawl awaiting user go |
| 2 | **Russian native index** — same pipeline against `/w/ru/api.php` | Pending | Unblocks bilingual demo (contribution #2) |
| 3 | **Agentic graph** (`rag/graph.py`) — rewrite → retrieve → `grade_docs` → re-retrieve ×1 → generate; R4 + R5 + `@traceable` per node | Pending | The "Agents" graded module |
| 4 | **Full evals** — RAGAS + LLM-judge + hit@k on the agent path; bilingual report | Partial (HE baseline done) | RU golden set needs human-verified rows from ru-native pages (R8, T16) |
| 5 | **Update automation** — `scripts/sync.py` (manifest-diff → pipeline → blue-green flip) + scheduled run | Pending | §2 DoD: "change page → re-sync → answer reflects" |
| 6 | **A2 latency improvement** — offline judge + embedding-based grade; baseline → optimized | Pending | Baseline is **3.50s mean**, target <2s |

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
