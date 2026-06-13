# Kol Zchut Rights Assistant — Project Plan

> **One-liner:** Your rights in Israel, answered in your own language — right inside Telegram.

A bilingual (Hebrew + Russian) Telegram agent that answers questions about legal
rights and government benefits in Israel, grounded in the
[Kol Zchut](https://www.kolzchut.org.il) knowledge base, with citations.

**Course:** Gen AI for AI Development (Google × Reichman University, Israel) — final project.
**Team:** originally planned for 2; **executed solo** (Orly Yagudayev). **Timeline:** ~1 week to a working demo.
**Status of this doc:** design/plan (engineering-reviewed 2026-06-07), pre-implementation. The
two-lane / "2 people" execution sections below reflect the original plan, not the final solo execution.

---

## 0. Engineering review decisions (LOCKED — supersede any conflicting detail below)

Decisions from the eng review on 2026-06-07. Where these conflict with later
sections, **these win** (later sections are pre-review and kept for context).

**Scope posture:** Full scope kept. **Cloud Run deploy is optional/stretch** — the
graded demo runs locally on this Mac via Telegram **long-polling** (no public URL or
webhook needed; the bot polls Telegram outbound), reachable by a few paired phone
users. Incremental manifest-diff sync **stays in core scope**.

| # | Decision | Affects |
|---|---|---|
| 1 | **One Chroma collection**, every chunk tagged `lang`. Retrieve **same-language first** (`where={"lang": ...}`); fallback = **relax/swap the filter**, not a live translation step. Validate he↔ru cross-lingual recall with a **Day-1/2 spike (~10 questions)** before trusting vector-only fallback. Use MediaWiki `langlinks` to offer the same-language source URL when a cross-lingual hit occurs. | retriever.py, index.py, graph.py |
| 2 | **Corpus = throwaway scaffolding.** Load official Paragraph Corpus under `source='corpus'`; bot uses it Day 1. After the pipeline is validated, **cut Hebrew over to `source='pipeline'`** and drop the corpus. **Never serve both at once.** Russian is pipeline-only. `source` is a config flag. | index.py, retriever.py, config |
| 3 | **clean.py models its output on the official corpus chunking format**; **verify** whether the corpus preserved tables. If tables were flattened, add **HTML-tables→Markdown** conversion in the cleaner for money/eligibility pages (Russian has no corpus, so it needs this regardless). | ingest/clean.py, chunk.py |
| 4 | **Blue-green index swap.** `sync.py` builds `kz_v{N+1}`, runs a smoke query, then **flips an active-collection pointer in config**; bot reads the active name **per-request** (see R7); previous collection retained for one-line rollback. Bot never reads a half-built index. | index.py, sync.py, retriever.py |
| 5 | **Access control.** `ALLOWED_CHAT_IDS` allowlist + **per-user/minute rate cap** enforced in `input_guardrails`; unknown IDs get a polite "private demo" reply. (Counts toward the Guardrails module.) | bot/handlers.py, guardrails.py, .env |
| 6 | **Graceful degradation.** Gemini calls wrapped with **timeout + 1 retry (backoff)**; Telegram sends in try/except; on failure send a localized "having trouble, try again" message; **never crash the process.** Centralized in one wrapper (DRY). | bot/handlers.py, rag/graph.py, central Gemini module |
| 7 | **acquire is resumable/idempotent by design** — diff manifest `lastrevid` vs the raw layer, fetch only missing/changed, safe to Ctrl-C and rerun. **Same diff function powers incremental sync.** | ingest/acquire.py, mediawiki.py |
| 8 | **Non-text handling.** Voice/photo/sticker → localized "please type your question." **Voice→text transcription is a stretch goal** (strong accessibility angle for the audience). | bot/handlers.py |
| 9 | **Test strategy.** Pure-logic units are **LLM-free**. LLM nodes are **mocked** in unit tests (assert citation present, refuse-if-empty, language match, grade loop cap ≤1) via the single central-wrapper mock point. **Real-model answer quality lives only in the eval harness** (RAGAS + judge on a held-out golden set). | tests/, rag/*, eval/* |
| 10 | **One E2E integration smoke** (he + ru): simulate a Telegram update, run the real graph against a small fixture index, assert grounded answer + ≥1 citation + language match. Marked `@pytest.mark.integration`. | tests/ |
| 11 | **Max-quality live path** (keep the live faithfulness LLM-judge and LLM grade_docs, loop cap 1). **Optimization lever, apply only if too slow/costly:** move the faithfulness judge offline and/or make grading embedding-based (cuts ~2 live LLM calls). | rag/graph.py, guardrails.py |

**Conventions:** all Gemini calls (LLM + embeddings) go through **one module** holding
the model-version constant — single mock point, single place to bump versions; ingest
is a single **`pipeline(lang)`** (no copy-pasted he/ru); all prompts + per-language
disclaimers live in **`prompts.py`** (eval-versioned).

**Stretch goals (only if core is solid):** Cloud Run webhook deploy · voice→text
transcription · the translate-in-the-loop cross-lingual fallback (only if the Issue-1
spike shows vector-only recall is weak) · the Issue-11 live-path optimization.

### Design decisions (2026-06-09 — concrete parameters)

Pins the choices the architecture review left vague. SDK: **`google-genai`**
(`client.models.*`).

| # | Decision |
|---|---|
| Q1 | **Embeddings:** `gemini-embedding-001` at **3072-dim (full)**. Asymmetric `task_type`: `RETRIEVAL_DOCUMENT` for chunks, `RETRIEVAL_QUERY` for queries. (Corpus is small; full fidelity helps he↔ru cross-lingual recall.) |
| Q2 | **Generation:** **`gemini-3.5-flash`** — current GA Flash, verified against the live ListModels endpoint 2026-06-09 (3.0/3.1 are preview-only). Used for rewrite + grade + generate. **Pin an explicit version** in config (not `-latest`); **low/zero live thinking budget**. ⚠️ Gemini 2.0 Flash was shut down 2026-06-01 — do not use. Escalate generate→Pro only if eval shows he/ru quality gaps. |
| Q3 | **Chunking:** section-based, **~512 tokens, ~50 overlap**, prepend `PageTitle > Section` to each chunk. Reverse-engineer the official corpus's chunk boundaries as a **reference** and compare our output on overlapping he pages. |
| Q4 | **Retrieval:** fetch **top-8 → grade_docs → keep ≤5** into generate. **Similarity floor** = the refuse/off-topic path (no separate scope-classifier LLM call). |
| Q5 | **Russian verification:** team reads Russian → **human-verified ru golden subset (~20–30 Q)** + native spot-checks. Russian is a first-class claim; demo both languages. |
| Q6 | **Index inclusion:** **curated**. He = mirror the official corpus's page set. Ru + new/changed pages = keep substantive rights guides (min length + content template/category); drop stubs, portals, lists, disambiguation. |
| Q7 | **Memory:** LangGraph **in-memory** checkpointer keyed by `chat_id`, last ~5 turns, `/reset` clears. ⚠️ Restart wipes sessions — avoid mid-demo restarts. |
| Q8 | **Logging/PII:** log question + retrieved doc-ids + answer + latency to a **local, gitignored** file; **regex-redact PII** (9-digit IL IDs, phone numbers) before writing; never shipped. Doubles as a source of real golden-set questions. |
| Q9 | **Quota:** **billing enabled** (paid tier) so the index build + RAGAS eval aren't throttled by free-tier rate limits. Batch embeds; throttle KZ fetches only. |
| — | **Lang detect:** script-based (Hebrew vs Cyrillic char counts), `/lang` overrides, lib fallback for Latin/ambiguous. **Injection defense:** grounding system prompt (answer only from retrieved KZ; ignore instructions in user input or page text) + retrieved-content-as-data + small denylist. **Bot ops:** BotFather token in `.env`; `ALLOWED_CHAT_IDS` from `@userinfobot`; rate cap ~15–20 msg/min/user. |

**Banked defaults:** citations = footer list of up to 3 `📄 [Title](url)` + per-language
disclaimer on every substantive answer; `grade_docs` scores each candidate (relevant/not
or 1–5), keep above threshold, refuse if none pass after one re-retrieve; sync = manual
`sync.py` + one scheduled run (cron/launchd) to *demonstrate* automation, not an always-on daemon.

### Delivery tiers (2026-06-09 — racing a 2–3 day POC)

⚠️ **"Optional for the POC" ≠ "optional for the grade."** Tier 1 modules are still
**required for the final submission** — they're just deferred past the 3-day POC.
This supersedes the front-loading in §12.

**Tier 0 — POC-core (Days 1–3, MUST work).** Goal: **Hebrew**, grounded, cited answers on Telegram.
- `config.py` + **`rag/llm.py`** central wrapper (gemini-embedding-001 @3072, Gemini 3 Flash, timeout/retry).
- **Fast-start only:** load the official **Hebrew corpus** → single Chroma collection (`source='corpus'`). No own pipeline yet.
- **Linear RAG** (no agent loop): retrieve (lang filter, top-k, **similarity floor**) → generate grounded answer + **citations + disclaimer** → **refuse-if-empty**.
- **Telegram bot** (`python-telegram-bot`, long-poll): text handler, `/start` `/help`, **`chat_id` allowlist**.
- A few smoke tests + manual demo.
- *Explicitly NOT in the POC:* own pipeline, Russian, agent self-correction, evals, sync.

**Tier 1 — POC-deferred (Days 4–6, REQUIRED for the grade).**
- Own **ingestion pipeline** (mediawiki/acquire/clean/chunk/index) → Hebrew **cutover** (`source='pipeline'`).
- **Russian** — first v1 add; own pipeline (cross-lingual generation is the cheap first step).
- **Agentic self-correction** (`grade_docs` → bounded re-retrieve) — upgrades linear RAG to the graded "Agent".
- **Guardrails depth** — injection patterns, PII-redacted logging, rate cap, language enforcement, output faithfulness.
- **Evaluations** — RAGAS + LLM-judge + hit@k + report over the golden set.
- **Update automation** — manifest-diff sync + blue-green swap + one scheduled run.
- **Memory / follow-ups** (in-memory checkpointer); `/lang` `/reset` `/sources`.

**Tier 2 — Genuinely optional (only if ahead; OK to omit even in the final).**
- Cloud Run deploy (local long-poll is the demo) · voice→text transcription (graceful "please type" is enough)
  · translate-in-loop cross-lingual fallback (only if the spike shows weak vector recall)
  · live-path LLM-call optimization (Issue-11 lever) · corpus chunk reverse-engineering comparison.

### Scope review round 2 — final scope + corrections (2026-06-09, LOCKED — supersede conflicting detail below)

Hard deadline: **ready by Saturday 2026-06-13** (~4-day clock from Tue 06-09: Tue–Fri build,
Sat submit; Fri-eve→Sat is Shabbat). **Implementation is fast** → coding is not the bottleneck;
the **critical path is** (Russian golden verification, similarity-floor calibration,
on-phone Hebrew bidi check, demo rehearsal). Scope cut to **must-have-only**: the 4 graded
modules (RAG, Agents, Guardrails, Evaluations) + bilingual demo + update automation.
**Never cut any of the four.**

| # | Decision | Affects |
|---|---|---|
| R1 | **Corpus tables are flattened** (official corpus is "paragraph text", May-2024 snapshot — verified upstream). Tier-0 Hebrew demo **avoids tabular benefit-amount questions**; correct numbers come only from our pipeline. Make **"table page renders numbers"** an explicit eval case that motivates the corpus→pipeline cutover. Do **not** patch the corpus. | clean.py, eval, demo script |
| R2 | **Native Russian is the required path** (ru wiki = **4,072 articles**, ~55% of he's 7,338 — verified). Cross-lingual fallback (filter-relax) is a **measured experiment, not load-bearing**; the T7 spike characterizes it. For the rare he-only topic a ru user hits: retrieve cross-lingual, answer in ru, cite the he page with a "source in Hebrew" note. Accept cross-lingual faithfulness as a known soft edge. | retriever, eval, §13 |
| R3 | **grade_docs is the authoritative scope/refuse gate;** the **similarity floor is a lenient pre-filter only.** Precedence: `floor (loose) → grade_docs (strict, re-retrieve ×1) → refuse`. **Calibrate the floor empirically, per-language** (in- vs out-of-scope top-1 distributions); record the separation in a config comment. No separate scope-classifier call — grade_docs doubles as it. | retriever, guardrails, config |
| R4 | **Re-retrieve = terminology-broadening (colloquial → official KZ term) + filter-relax — one mechanism, unified with R2.** grade_docs **returns a reason** that selects the transform. **Grading is ONE batched LLM call** over all candidates (not per-candidate). Add a **colloquial-recovery eval case** that pass-1 misses and pass-2 recovers (proves the agent loop earns its keep). | graph.py, retriever, eval |
| R5 | **Memory feeds the rewrite/retrieve step** (history-aware "condense question", last ~2–3 turns), with a **follow-up-vs-new-topic** decision in the rewrite prompt (prevents context bleed). Kept **minimal** (in-memory last-N + `/reset`). Two-turn follow-up is a golden case in he + ru. | graph.py, session.py, eval |
| R6 | **Telegram HTML parse mode** (not MarkdownV2 — Hebrew titles/URLs shatter MarkdownV2 escaping). **One `render_answer(body, citations, disclaimer, lang)`** owns all escaping + bidi. `disable_web_page_preview=True`. **Day-1 on-phone bidi smoke** (Hebrew body + long he-slug URL + disclaimer). | bot/handlers.py, prompts.py |
| R7 | **Retriever resolves the active-collection pointer PER-REQUEST** (cache the handle, reopen only on name change; atomic rename flip). Makes the live-update DoD work **without a restart** — required because in-memory memory forbids mid-demo restart. | retriever.py, sync.py, config |
| R8 | **Russian golden set is built from ru-native-page topics** (not translated he-only doc_ids). Report **native vs cross-lingual separately**. Sizes: he ~40–50, ru ~20–30 human-verified. **Don't claim he↔ru differences below the noise floor.** ~5–8 adversarial/out-of-scope per language. hit@k on the **pipeline** index. | eval/* |
| R9 | **§0 Delivery Tiers govern sequencing.** §12's day-grid is **illustrative/superseded** (do not follow its Day-1 he+ru). §21 lanes anchor to the **Tier-0 corpus** Chroma. **Interface-freeze (config active-pointer + `source` flag, `rag/llm.py` signature, chunk metadata schema) = deliverable #1, hour 1.** | §12, §21, all |

**Kept (must-have):** corpus fast-start as a Day-1 safety net (cutover optional); memory minimal.
**Cut (nice-to-have):** Cloud Run · voice→text (keep the free "please type" reply) · translate-in-loop ·
live-path optimization lever · corpus chunk reverse-engineering · corpus-vs-pipeline hit@k comparison ·
live-baseline comparison · fancy charts · blue-green smoke/rollback polish · `/lang` · `/sources`.
(`/start` `/help` `/reset` + auto language-detect stay.)

### Rubric alignment (2026-06-09 — official final-assignment spec)

Grade weights: Problem **5%** · Market Research **15%** · Architecture **20%** · Implementation **50%** · Pitch **10%**.
Architecture (§4) + Evaluations (§8) already meet/exceed the ask. **Confirmed: keep all four modules**
(RAG/Agents/Guardrails/Evaluations). These are **additive** deltas to serve the business/process half of the grade:

| # | Decision |
|---|---|
| A1 | **Submission doc = `REPORT.md`**, structured to the 5 rubric sections; reuses PLAN §4/§10 for architecture. PLAN.md stays the design source of truth. |
| A2 | **"Improve one dimension" is required (methodology step 6).** Promote §0 #11 from optional lever to a **demonstrated result**: measure **baseline latency/cost** (max-quality path ≈ 4 live LLM calls ≈ 3–6s) → apply offline-judge + embedding-grade → record **baseline→after**. Serves the latency KPI (**<2s** target) and the trade-off story in one move. |
| A3 | **Business impact = hybrid.** (a) User productivity/access: time-to-answer vs manual KZ navigation, estimated reach (1M+ ru speakers), demo-tester satisfaction rating; (b) Kol Zchut operational: estimated helpline/staff-hour savings. Fill the Business-KPI table baseline→after (estimates OK, **labeled as estimates**). |
| A4 | **Stakeholder interviews (part of the 15%)** — 2 informal: a ru-speaking immigrant / KZ user / social worker. Primary research; notes captured in REPORT §2. |
| A5 | **Technical-KPI table** filled with *achieved* values post-eval: accuracy (≥90% target), latency (<2s after A2), error rate (<5%), uptime (n/a local — note as polling demo). |
| A6 | **Pitch:** 8-min flow (Hook→Problem→Solution→Architecture→Eval→Impact→Demo→Next), practice to 6; **record a backup demo video**; pairs split parts; no "age of AI" opener. |
| A7 | **Problem §1 personal hook** — add "why this team chose it" (rubric prefers a problem you know from work/daily life). |
| A8 | **Observability — LangSmith tracing** (`LANGSMITH_API_KEY` in `.env`). The central LLM wrapper (`rag/llm.py`) decorates `embed`/`generate` with `@traceable`; Tier-1 will trace each agent-graph node (retrieve, rewrite, grade_docs, generate) and the eval harness. Powers (a) the **A2** baseline→optimized latency/cost measurement (per-call timings + token counts in the dashboard, no instrumentation code to write), (b) failure forensics (see exactly which retrieval/grade decision drove a bad answer), (c) the eval harness UI. **Opt-in via env var** — zero overhead if the key is unset; tests stay LLM-free. |

---

## 1. Project overview

Imagine asking a Telegram contact, *"I just had a baby — what am I entitled to?"*
and getting a clear, accurate answer in seconds. That's the project: a multilingual
rights assistant built on top of Israel's Kol Zchut database.

**The problem.** Every year, Israelis lose money and support they're legally
entitled to — unemployment pay, disability allowances, housing aid, pensions —
because the rules are buried in hard-to-navigate Hebrew. For the ~1M+ Russian
speakers and for elderly citizens, the language barrier turns "available" into
"invisible."

**Why now.** Gen AI can finally read a person's question in plain Hebrew or Russian
and find the right answer in a trusted source. Kol Zchut's content is openly
licensed and already translated into Russian, and messaging apps are where people
already are. The pieces are on the table for the first time.

**Our solution.** An agent that meets people where they are. Ask a question in
everyday language; the bot retrieves the matching Kol Zchut rights-guide, answers
in your language, and shows the source so you can trust it. No forms, no jargon,
no new app — just your rights, explained.

> **Scope note:** This is *rights/entitlements information*, not legal advice. Every
> answer is grounded in Kol Zchut, cites its source, and carries a disclaimer.

---

## 2. Goals & success criteria

**Primary (must demo):**
- A live Telegram bot that answers rights questions in **Hebrew and Russian**.
- Every answer is **grounded** in retrieved Kol Zchut content and **cites the source page**.
- Refuses gracefully when the answer isn't in the knowledge base.
- All four required modules present and explainable: **RAG, Agents, Guardrails, Evaluations**.
- An **update automation** that detects changed pages and rebuilds the index.
- A **presentation** that explains our choices and trade-offs.

**Definition of done:**
- ≥ 90% of demo questions answered with a correct, grounded, cited response in the right language.
- Eval report (RAGAS + LLM-as-judge) produced over a bilingual golden set.
- Update job runs end-to-end: change a page → re-sync → answer reflects it.

**Non-goals (YAGNI for this project):**
- Not legal advice; no case-specific guidance, no PII storage, no accounts.
- No Arabic in v1 (Kol Zchut has it; out of scope for the week).
- No fine-tuning of our own embedder (we use Gemini embeddings off the shelf).

---

## 3. Related work & our contribution (important for the writeup)

Kol Zchut already has an on-site AI chat (⁧"שאלו את ה-AI שלנו"⁩, in beta). It is
**open source** and worth citing:

| Component | Repo | Notes |
|---|---|---|
| On-site chatbot (MediaWiki ext.) | `kolzchut/mediawiki-extensions-KZChatbot` | Middleware between UI and RAG API |
| Chat UI | `kolzchut/react-app-KZChatbot` | React frontend |
| RAG content feed | `kolzchut/mediawiki-extensions-ChatbotRagContent` | Pushes content changes + retrieval API |
| RAG backend (MIT) | `NNLP-IL/Webiks-Hebrew-RAGbot` | Elasticsearch + fine-tuned `me5-large` + LLM client |
| Paragraph corpus | `NNLP-IL/Webiks-Hebrew-RAGbot-KolZchut-Paragraph-Corpus` | All KZ paragraphs, pre-chunked (≤512 tok) |
| QA dataset (CC-BY-4.0) | `NNLP-IL/Webiks-Hebrew-RAGbot-KolZchut-QA-Training-DataSet` | question → `doc_id` + gold paragraph |

**How our project differs (our contribution):**
1. **Channel:** Telegram (and a path to WhatsApp), not an on-site web widget.
2. **Bilingual / cross-lingual:** first-class **Russian** support, not Hebrew-only.
3. **Agentic RAG:** a LangGraph self-correcting agent (query rewrite → grade → re-retrieve → self-check), vs a single retrieval call.
4. **Stack:** Gemini embeddings + Chroma (zero-train, multilingual) vs fine-tuned `me5-large` + Elasticsearch.
5. **Our own Guardrails + Evaluations** layers and an **incremental update automation**.

We reuse their **published datasets** (with attribution) to bootstrap our corpus
and golden set, and we use their **live chatbot as a qualitative baseline** in the
demo. We do **not** copy their backend code.

---

## 4. Architecture overview

### 4.0 System at a glance (high-level)

Three planes over one shared store. §4.1 below zooms into the live path.

```
        ┌──────────────────────────────────────────────────────────────────────────┐
        │   CROSS-CUTTING:  config.py  ·  rag/llm.py (central Gemini wrapper)         │
        │   models + dims, ACTIVE-collection pointer, ALLOWED_CHAT_IDS, thresholds    │
        │   one embed()/generate() with timeout+retry+fallback — single mock point    │
        └─────▲───────────────────────────▲───────────────────────────────▲──────────┘
              │                            │                               │
  ┌───────────┴───────────┐   ┌────────────┴────────────────┐   ┌──────────┴───────────┐
  │  OFFLINE / DATA PLANE  │   │   ONLINE / SERVING PLANE    │   │     EVAL PLANE        │
  │  "build the knowledge" │   │   "answer a person"         │   │  "prove it works"     │
  │                        │   │                             │   │                       │
  │  Kol Zchut MediaWiki   │   │   Telegram user (he / ru)   │   │  golden_he/ru.jsonl   │
  │        API             │   │          │ long-poll        │   │        │              │
  │  ingest/ (mediawiki,   │   │   bot/ (telegram_app,       │   │  eval/ (run_ragas,    │
  │   acquire, clean,      │   │        handlers, session)   │   │   run_judge, report)  │
  │   chunk, index)        │   │          │                  │   │        │              │
  │        │  orchestrated │   │   rag/graph.py  ◀── prompts │   │   reuses rag/graph    │
  │        │  by scripts/  │   │   (LangGraph agent)         │   │   + rag/retriever     │
  │        ▼  sync.py      │   │   guardrails ▸ retrieve ▸   │   │        │              │
  │                        │   │   grade ▸ generate ▸ out    │   │        ▼  report      │
  │   ╔════════════════════╪═══╪═════════════╪═══════════════╪═══╪═══╗  (md / csv)       │
  │   ║   CHROMA — one multilingual collection (lang-tagged), blue-green ║              │
  │   ║  retriever reads ACTIVE collection · index builds kz_v{N+1}      ║              │
  └───╚═════════════════════════════════════════════════════════════════╝──────────────┘
```

The data and serving planes never touch the same Chroma copy live: `index.py`
builds a **new** collection, `sync.py` flips the **active pointer** (blue-green),
`retriever.py` only ever reads whatever is active.

**Module map — responsibility · calls · called by**

_Cross-cutting_
| Module | Responsibility | Calls | Called by |
|---|---|---|---|
| `config.py` | Models, embed dims, **active-collection** name, `ALLOWED_CHAT_IDS`, thresholds | — | everything |
| `rag/llm.py` | The one Gemini door: `embed()` + `generate()` w/ timeout/retry/fallback, pinned versions | Gemini API | `index`,`retriever`,`graph`,`eval` |

_Offline / data plane_
| Module | Responsibility | Calls | Called by |
|---|---|---|---|
| `ingest/mediawiki.py` | MediaWiki client: manifest, `parse` HTML, `langlinks`; WAF-safe UA + throttle | KZ API | `acquire` |
| `ingest/acquire.py` | **manifest-diff** (added/changed/deleted); **resumable** fetch → raw layer | `mediawiki` | `sync` |
| `ingest/clean.py` | HTML → clean text, **tables→Markdown**; corpus format as reference | — | `index` |
| `ingest/chunk.py` | **Section-based** ~512-tok chunks, title+heading prefix | — | `index` |
| `ingest/index.py` | clean→chunk→**embed**→upsert `kz_v{N+1}`; delete removed; **blue-green** | `clean`,`chunk`,`llm` | `sync` |
| `scripts/sync.py` | Entrypoint (cron/launchd): acquire+index, smoke-test, **flip active pointer** | `acquire`,`index`,`config` | cron / manual |

_Online / serving plane_
| Module | Responsibility | Calls | Called by |
|---|---|---|---|
| `bot/telegram_app.py` | Build `python-telegram-bot` app, register handlers, **`run_polling()`** | `handlers` | entrypoint |
| `bot/handlers.py` | Update ↔ agent; commands; non-text reply; error fallback | `graph`,`session` | `telegram_app` |
| `bot/session.py` | Per-`chat_id` **in-memory** memory (~5 turns; `/reset`) | — | `handlers` |
| `rag/graph.py` | **LangGraph agent**: in→router→retrieve→grade→generate→out; checkpointer | `guardrails`,`retriever`,`prompts`,`llm` | `handlers`,`eval` |
| `rag/retriever.py` | Chroma similarity over **active** collection, `lang` filter, top-8, **similarity floor** | Chroma,`llm` | `graph` |
| `rag/guardrails.py` | Input (allowlist, rate, lang, injection, PII) + output (citation, language, faithfulness, refuse-if-empty) | `llm` | `graph` |
| `rag/prompts.py` | System/answer prompts + per-language disclaimers (eval-versioned) | — | `graph` |

_Eval plane_
| Module | Responsibility | Calls | Called by |
|---|---|---|---|
| `eval/run_ragas.py` | RAGAS: faithfulness, relevancy, context precision/recall | `graph`/`retriever`,`llm` | manual |
| `eval/run_judge.py` | LLM-judge: correctness, **language match**, disclaimer, correct refusal | `graph`,`llm` | manual |
| `eval/report.py` | Aggregate → markdown + CSV + charts (he vs ru) | — | manual |

**Two flows that matter**

```
OFFLINE — keep knowledge fresh (sync.py)
  KZ MediaWiki API ─▶ mediawiki ─▶ acquire (manifest-diff, resumable)
     ─▶ raw layer data/raw/{lang}/{pageid}.json
     ─▶ index (clean ▸ chunk ▸ embed) ─▶ Chroma kz_v{N+1} ─▶ smoke ─▶ flip ACTIVE

ONLINE — one user message (rag/graph.py)
  Telegram msg ─▶ handlers ─▶ [input_guardrails] allowlist·rate·lang·injection·PII
     ─▶ [router] rewrite ─▶ [retrieve] active, lang filter, top-8
     ─▶ [grade_docs] keep ≤5 · weak? re-retrieve ×1 · below floor ⇒ refuse
     ─▶ [generate] grounded answer + citations + disclaimer
     ─▶ [output_guardrails] citation? language? faithful? else refuse ─▶ reply
```

**Domain glossary**

- **Kol Zchut / זכותון (zchuton)** — source wiki of Israeli rights guides; one page = one rights topic.
- **Raw layer** — local per-page snapshot decoupling *fetch* from *index*, so re-indexing never re-crawls.
- **manifest-diff** — compare each page's `lastrevid` vs last seen → added/changed/deleted; powers first crawl (resume) + incremental sync.
- **Fast-start corpus → cutover** — official Hebrew corpus (`source='corpus'`) serves Day-1, replaced by `source='pipeline'` once validated.
- **Blue-green swap** — build `kz_v{N+1}`, atomically flip the active pointer; bot never reads a half-built index.
- **Single multilingual collection** — one Chroma store, every chunk `lang`-tagged; same-language-first, filter-relax fallback.
- **Agentic self-correction (topology B)** — `grade_docs` can trigger one bounded re-retrieve; the graded "Agent".
- **Similarity floor** — best hit too weak ⇒ refuse; doubles as off-topic detection.
- **Guardrails / Evaluations** — the other two graded modules: live input/output checks; offline RAGAS + LLM-judge over a **golden set**.

### 4.1 Live-path detail (zoomed in)

```
                 ┌──────────────────────────────────────────────┐
                 │            Telegram user (he / ru)            │
                 └──────────────────┬───────────────────────────┘
                                    │ message
                 ┌──────────────────▼───────────────────────────┐
                 │  Telegram bot (python-telegram-bot)           │
                 │  /start /help /lang /reset /sources           │
                 └──────────────────┬───────────────────────────┘
                                    │ (chat_id, text)
                 ┌──────────────────▼───────────────────────────┐
                 │             LangGraph agent graph             │
                 │  [input guardrails] lang/scope/jailbreak/PII  │
                 │           │                                   │
                 │  [router / query understanding]  (agent)      │
                 │     rewrite + (optional) translate query      │
                 │           │                                   │
                 │  [retrieve] ───────────▶ Chroma (he / ru)     │
                 │           │                                   │
                 │  [grade docs] ── weak? ──▶ re-retrieve ×1     │
                 │           │ ok                                │
                 │  [generate] grounded answer + citations       │
                 │           │            + disclaimer (Gemini)  │
                 │  [output guardrails] faithfulness / citation /│
                 │           │           language / refuse-empty │
                 └──────────────────┬───────────────────────────┘
                                    │ answer (+ per-chat memory)
                 ┌──────────────────▼───────────────────────────┐
                 │              Telegram reply                    │
                 └──────────────────────────────────────────────┘

  OFFLINE PIPELINE (scheduled):
  MediaWiki API ─acquire(manifest-diff, action=parse HTML)→ raw layer
       ─index(clean → chunk → Gemini embed)→ Chroma (he + ru)
  fast-start (Hebrew only): official KolZchut Paragraph Corpus → Chroma
```

**Five components, each independently testable:**
1. **Ingestion pipeline** (offline) — acquire + index, manifest-diff sync.
2. **RAG/agent core** — LangGraph graph (provider-agnostic, no Telegram dependency).
3. **Telegram bot** — thin I/O layer over the agent core.
4. **Guardrails** — input/output checks, callable as functions/nodes.
5. **Evaluations** — offline harness over a golden set.

---

## 5. Data strategy

**Decision:** `action=parse` (rendered HTML) + **manifest-diff** sync (verified
working against the live API), with a **hybrid fast-start** from the official
Hebrew corpus.

### 5.1 Sources (verified facts)
- MediaWiki **1.35.14**; API open and read-accessible.
  - Hebrew API: `https://www.kolzchut.org.il/w/api.php` (~**7,338** content articles)
  - Russian API: `https://www.kolzchut.org.il/w/ru/api.php` (smaller, separate wiki)
- Content license: **Creative Commons BY-NC-SA 2.5 IL** (attribute, non-commercial, share-alike).
- Official **Paragraph Corpus** (Hebrew, pre-chunked ≤512 tok): `doc_id / title / link / content`.
- Official **QA dataset** (CC-BY-4.0): `doc_id / question / paragraph`.

### 5.2 Pipeline
**`acquire` (manifest-diff):**
1. Pull a cheap manifest per language: `generator=allpages&prop=info&inprop=url&gapfilterredir=nonredirects` → `{pageid, title, lastrevid, touched, url}` (~15 calls for Hebrew).
2. Diff `lastrevid` vs stored manifest → **added / changed / deleted** sets.
3. Fetch changed pages via `action=parse&prop=text` → rendered **HTML**.
4. Write to a **raw layer** on disk: `data/raw/{lang}/{pageid}.json` = `{pageid, title, url, lang, lastrevid, html, fetched_at}`.

**`index` (transform → embed):**
1. Clean HTML (drop nav/edit/infobox chrome; keep headings, paragraphs, flatten tables to text).
2. Chunk by section heading (~500–800 tokens, small overlap; keep section title as context).
3. Embed with **Gemini embeddings**; upsert to a **single Chroma collection** with metadata `{pageid, title, url, lang, section, lastrevid, source}` (see §0 #1, #2). Build into `kz_v{N+1}` and **blue-green swap** (see §0 #4).
4. Delete vectors for removed `pageid`s.

**Hybrid fast-start (Hebrew):** load the official Paragraph Corpus directly into
Chroma on Day 1 so the bot works immediately while our own pipeline is built and
validated against it. Russian and freshness come **only** from our pipeline.

### 5.3 Update automation & "recreate index"
- **Separate acquire from index** via the raw layer. Re-embedding/re-chunking never
  re-downloads from Kol Zchut — rebuild from the local raw copies.
- `scripts/sync.py` = acquire + index, idempotent. Run incrementally (cron locally,
  **Cloud Scheduler** in the cloud).
- Full rebuild trigger: when `EMBEDDING_MODEL_VERSION` or chunking logic changes.
- Corpus is small enough that a **full nightly rebuild** is a valid fallback if
  incremental upsert misbehaves.
- **Etiquette:** descriptive User-Agent + throttle (~1 req/s, `maxlag=5`); their CDN
  blocks default bot UAs (observed).

---

## 6. RAG + Agent design (LangGraph)

**Topology B — Agentic RAG with bounded self-correction** (approved). Nodes:

1. **input_guardrails** — language detect, length cap, scope check (is this a
   rights/benefits question?), jailbreak/prompt-injection patterns, PII scrub.
2. **router / query_understanding** *(agent step)* — normalize + rewrite the query;
   decide retrieval language; optionally translate query for cross-lingual recall.
3. **retrieve** — Chroma similarity search over the **single collection**, filtered
   `where={"lang": <user lang>}` (top-k). Cross-lingual fallback = **relax/swap the
   `lang` filter** (vector-only) when the user's language is thin; translate-in-loop
   is a stretch fallback only if the Issue-1 spike shows weak recall. See §0 #1.
4. **grade_docs** *(agent step)* — score retrieved chunks for relevance; if weak,
   reformulate and retrieve **once more** (hard cap = 1 extra loop, demo-safe).
5. **generate** — answer **in the user's language**, strictly grounded in retrieved
   context, with inline **citations** (title + URL) and a **disclaimer**.
6. **output_guardrails** — faithfulness/grounding check, citation presence,
   language match, and **refuse-if-no-context** ("I couldn't find this in Kol Zchut").

**Memory:** per-user session (last N turns) via a LangGraph checkpointer keyed by
Telegram `chat_id`; `/reset` clears it. Enables follow-ups ("and for freelancers?").

> **Round-2 wiring (R3–R7).** The **rewrite node consumes the last ~2–3 turns** to emit a
> standalone query (condense), and decides **follow-up vs new topic** (no context bleed) — memory
> feeds *retrieval*, not just generation. **grade_docs** is the authoritative refuse gate, runs as
> **one batched LLM call** returning a *reason*; the similarity floor is only a lenient pre-filter.
> Weak grade → **re-retrieve ×1** via terminology-broaden / filter-relax (same mechanism as the
> cross-lingual fallback).

---

## 7. Guardrails module

**Input:**
- Language detection (route + enforce response language).
- Length / rate cap.
- Scope filter: off-topic → polite redirect ("I answer questions about rights in Israel").
- Jailbreak / prompt-injection pattern checks.
- PII handling: do not log or store personal data from messages.

**Output:**
- **Grounding/faithfulness** check (LLM-as-judge): does the answer follow from retrieved context? If not → refuse/retry.
- **Citation presence:** every substantive answer links ≥1 Kol Zchut source.
- **Mandatory disclaimer**, per language. Examples:
  - HE: ⁧"המידע הוא כללי, מתוך אתר 'כל זכות', ואינו מהווה ייעוץ משפטי."⁩
  - RU: «Это общая информация с сайта «Коль Зхут», она не является юридической консультацией.»
- **Refuse-if-empty:** no relevant context → say so, don't invent.

**Implementation:** lightweight custom checks + Gemini safety settings for v1
(fast to build, fully explainable). Note alternatives considered: NeMo Guardrails,
Guardrails AI (heavier; deferred).

---

## 8. Evaluations module

**Golden set (bilingual):**
- **Seed from** the official `KolZchut-QA-Training-DataSet` (CC-BY-4.0): `question → doc_id + gold paragraph`.
- **Carve a held-out eval subset** (~40 questions) we never use for any tuning.
- **Russian set:** translate a subset of questions (same `doc_id` targets) and human-verify; tests cross-lingual retrieval.
- Add a few **adversarial/out-of-scope** questions to test refusals and guardrails.

**Metrics:**
- **RAGAS:** faithfulness, answer relevancy, context precision, context recall.
- **Retrieval:** hit@k / MRR against gold `doc_id` (the dataset gives us this for free).
- **Custom LLM-as-judge:** correctness vs gold paragraph, **language match**,
  **disclaimer present**, **correct refusal** on out-of-scope.

**Baseline comparison:** run the same questions through the **live on-site AI**
(manually) and compare qualitatively in the presentation — a baseline, not ground truth.

**Output:** `eval/report` — markdown + CSV + simple charts (scores per metric, he vs ru).

---

## 9. Telegram bot layer

- **Library:** `python-telegram-bot`.
- **Commands:** `/start`, `/help`, `/reset`; language **auto-detected** (he/ru). `/lang` and `/sources` cut (scope).
- **Formatting (R6):** **HTML parse mode** (not MarkdownV2); one `render_answer(body, citations, disclaimer, lang)` owns all escaping + bidi; `disable_web_page_preview=True`. Day-1 on-phone bidi smoke.
- **UX:** "typing…" action while processing; answer + clickable source links.
- **Runtime:** **long-polling** is the demo (local, paired phone users). Cloud Run webhook is cut (TODOS, Tier-2).
- **Thin layer:** all logic lives in the agent core; the bot only maps Telegram I/O ↔ agent.

---

## 10. Tech stack & key trade-offs

| Area | Choice | Why | Trade-off |
|---|---|---|---|
| LLM + embeddings | **`gemini-3.5-flash`** (gen, verified GA) + **`gemini-embedding-001`** @3072 (see §0 Q2) | Course fit, strong he/ru, native embeddings | Vendor lock, quota |
| Orchestration | **LangGraph** | Inspectable agent graph, easy guardrail/eval nodes | Learning curve vs plain calls |
| Vector store | **Chroma (local)** | Zero infra, metadata filter, demo-friendly | Not distributed/scale |
| Data ingest | **parse-HTML + manifest-diff** | Clean rendered content + cheap exact deltas | HTML cleaning effort |
| Fast-start data | **Official Paragraph Corpus (he)** | Instant RAG-ready Hebrew, de-risks week | Snapshot, Hebrew-only |
| Languages | **he + ru from start** | Better demo, forces multilingual design | 2× ingest/eval work |
| Evals | **RAGAS + LLM-as-judge** | Rigor + tone/language/safety coverage | More time |
| Agent topology | **B: agentic + self-correction** | Real "agent", demo-reliable | More than linear RAG |
| Deploy | **Local → Cloud Run** | Fast iteration, production-like final | GCP setup time |

---

## 11. Repository structure

```
kolzchut-bot/
  README.md
  PLAN.md
  pyproject.toml | requirements.txt
  .env.example
  config.py
  data/
    raw/{he,ru}/            # raw fetched HTML + metadata
    manifest/{he,ru}.json   # last-seen lastrevid per page
    corpus/                 # official paragraph corpus (fast-start)
  src/
    ingest/  mediawiki.py  acquire.py  clean.py  chunk.py  index.py
    rag/     llm.py  retriever.py  graph.py  prompts.py  guardrails.py
    bot/     telegram_app.py  handlers.py  session.py
    eval/    golden_he.jsonl  golden_ru.jsonl  run_ragas.py  run_judge.py  report.py
  scripts/   sync.py        # acquire + index entrypoint (cron/scheduler)
  tests/
  docs/      presentation/
```

---

## 12. One-week plan (2 people)

> ⚠️ **Illustrative / superseded by §0 Delivery Tiers + scope review round 2 (R9).** The real clock is
> **Tue 06-09 → Sat 06-13 (~4 days).** Do **not** follow this grid's
> Day-1 he+ru — Tier-0 is Hebrew-only. Kept for the task texture only.

Roles: **A = Data/RAG/Eval**, **B = Agent/Bot/Guardrails/Deploy** (swap as needed).

| Day | Goal | A | B |
|---|---|---|---|
| **1** | **Quick POC** | MediaWiki client + acquire (he+ru subset); load official corpus; clean/chunk/index to Chroma | Minimal retrieve→generate w/ Gemini + citations; CLI test |
| **2** | Telegram + memory | Tune chunking/retrieval; cross-lingual fallback | LangGraph graph + bot (polling) + session + commands |
| **3** | **Guardrails (MVP demo-able)** | Scope/golden seeds | Input+output guardrails, disclaimer, refusals, language enforce |
| **4** | Full ingest + automation | Full corpus he+ru; manifest-diff sync; scheduler | Wire sync to bot; logging |
| **5** | Evaluations | Golden set (he+ru); RAGAS + judge; report/charts | Fix issues found by evals |
| **6** | Deploy + polish | README, data docs | Cloud Run webhook; error handling; dry run |
| **7** | **Presentation** | Slides: data + evals + trade-offs | Slides: architecture + demo; rehearse; buffer |

**MVP line:** end of Day 3 the project is demo-able (bilingual grounded answers on
Telegram with guardrails). Days 4–6 are depth (automation, evals, deploy).

---

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| 1-week clock | Hard MVP at Day 3; official corpus fast-start; cap agent loops |
| Russian *topic-level* coverage gaps (not "thin" — ru wiki is 4,072 articles) | Native ru is the required path (R2); filter-relax fallback only for he-only topics; ru golden set targets ru-native pages |
| WAF blocks bot | Real User-Agent + throttle + `maxlag`; cache raw layer |
| HTML cleaning messy | Start from official corpus format; iterate cleaner on our HTML |
| Hallucination | Strict grounding prompt + output faithfulness guardrail + refuse-if-empty |
| Cloud Run setup eats time | Local polling always works as demo fallback |
| Eval contamination | Held-out subset; we don't train an embedder |

---

## 14. Ethics, license & attribution

- **Content:** Kol Zchut is **CC BY-NC-SA 2.5 IL** — attribute "Kol Zchut", link
  back to the source page (we cite by default), non-commercial, share-alike.
- **Datasets:** Webiks/NNLP-IL QA dataset & corpus — **CC-BY / CC-BY-4.0**, attribute.
- **Not legal advice:** explicit disclaimer on every answer; refuse case-specific legal guidance.
- **Privacy:** no accounts, no PII storage, minimal logging.

---

## 15. Presentation outline (explain our choices)

1. Problem → why now → solution (Section 1).
2. Live demo (he + ru, a follow-up question, a refusal).
3. Architecture walkthrough (Section 4 diagram).
4. Module deep-dives: RAG, Agents (topology B), Guardrails, Evaluations.
5. **Choices & trade-offs** (Section 10 table) + related work / how we differ (Section 3).
6. Eval results (RAGAS + judge; he vs ru; vs live baseline).
7. Update automation (manifest-diff demo).
8. Limitations, ethics/license, future work (WhatsApp, Arabic, more agents).

---

## 16. Open questions / future work

- WhatsApp channel (Business API) after Telegram.
- Arabic (third Kol Zchut language).
- Better Russian coverage (native ru index vs cross-lingual translate).
- Optional: compare Gemini embeddings vs the fine-tuned `me5-large` embedder.

---

## 17. References

- Kol Zchut: https://www.kolzchut.org.il — API `/w/api.php`, `/w/ru/api.php`
- Kol Zchut GitHub: https://github.com/kolzchut
- Webiks Hebrew RAGbot (MIT): https://github.com/NNLP-IL/Webiks-Hebrew-RAGbot
- KolZchut Paragraph Corpus: https://github.com/NNLP-IL/Webiks-Hebrew-RAGbot-KolZchut-Paragraph-Corpus
- KolZchut QA dataset (CC-BY-4.0): https://github.com/NNLP-IL/Webiks-Hebrew-RAGbot-KolZchut-QA-Training-DataSet
- LangGraph, Chroma, RAGAS, python-telegram-bot (official docs)

---

## 18. NOT in scope (considered, deferred)

| Item | Why deferred |
|---|---|
| Cloud Run / cloud deploy | Local long-polling demo is sufficient (graded demo runs on this Mac); deploy is a stretch |
| Translate-in-the-loop cross-lingual fallback | Replaced by filter-relax (§0 #1); build only if the Day-1/2 spike shows weak vector recall |
| Voice→text transcription | Stretch; graceful "please type" reply ships in core (§0 #8) |
| Live faithfulness optimization (offline judge / embedding grade) | Keeping max-quality live path; optimization is a ready lever if too slow/costly (§0 #11) |
| Arabic (3rd KZ language) | Out of scope for the week (PLAN §2 non-goals) |
| Fine-tuning our own embedder | Using Gemini embeddings off the shelf |
| Coexist corpus + pipeline with dedup | Rejected; clean cutover instead (§0 #2) |

## 19. What already exists (reuse vs rebuild)

- **Reused (data, with attribution):** official Paragraph Corpus (Hebrew fast-start), QA dataset (golden-set seed), live on-site chatbot (qualitative baseline). See §3.
- **Deliberately NOT reused (rebuilt for the assignment):** the Webiks RAG backend (Elasticsearch + me5-large). Reusing data is smart; reusing the backend would defeat the RAG/Agents/Guardrails/Evals grading. Correct call.
- **Internal:** greenfield repo — no internal code to reuse yet.

## 20. Failure modes (per new codepath)

| Codepath | Realistic prod failure | Test? | Error handling? | User sees |
|---|---|---|---|---|
| Gemini call (live) | 429 / timeout mid-answer | unit (mock) | timeout+retry+fallback (§0 #6) | "try again" (clear) |
| acquire / mediawiki | WAF 403 / maxlag / network drop | unit | retry+backoff, descriptive UA, **resume** (§0 #7) | n/a (offline) |
| clean.py tables | table flattened → wrong benefit number | unit (golden fixtures) | table→MD + **verify corpus** (§0 #3) | **SILENT if unverified — watch this** |
| retrieve fallback | poor he↔ru alignment → irrelevant docs | unit + spike | grade_docs + refuse-if-empty | refusal (clear) |
| sync vs live read | query hits half-built index | E2E | blue-green swap (§0 #4) | always finished index |
| bot input | non-allowlisted user / spam | unit | allowlist + rate cap (§0 #5) | "private demo" (clear) |
| bot input | voice/photo/sticker | unit | graceful reply (§0 #8) | "please type" (clear) |

**Critical gap to actively close:** table→number correctness is the one failure that is
*silent and user-visible-as-wrong*. **Update (R1):** the official corpus is confirmed-likely
*flattened* ("paragraph text"), so the **Tier-0 Hebrew demo curates away from tabular
benefit-amount questions**; correct numbers come only from our pipeline, gated by an eval case
on a known benefit-amount page (table→Markdown). Mitigation (§0 #3) lives in the pipeline, not the corpus.

## 21. Worktree parallelization strategy

Two people, two largely independent lanes after a Day-1 interface handshake.

| Lane | Modules | Depends on |
|---|---|---|
| A — Data/RAG/Eval | `ingest/`, `eval/`, Chroma index | config + Gemini-wrapper contract |
| B — Agent/Bot/Guardrails | `rag/`, `bot/` | the **fast-start corpus** Chroma (not Lane A's pipeline) |

- **Launch A + B in parallel.** B builds the agent/bot against the Day-1 corpus-loaded Chroma while A builds the real pipeline — B is unblocked from Day 1.
- **Shared seams (define Day 1, then freeze):** `config.py` (active-collection pointer, `source` flag), the **central Gemini wrapper** signature, and the chunk **metadata schema**. Both lanes touch these — agree the interfaces first to avoid merge conflicts.
- **Join points:** Hebrew **cutover** (A's pipeline replaces corpus) and **eval** (needs B's graph + A's index). Sequential after both lanes land.

## 22. Implementation Tasks
Synthesized from this review. Each derives from a specific decision above.

- [ ] **T1 (P1)** — ingest — Single-collection index + `source`/`lang` metadata + blue-green swap. Surfaced by §0 #1,#2,#4. Files: `ingest/index.py`, `config.py`, `rag/retriever.py`. Verify: build kz_v2, flip pointer, bot reads new; rollback works.
- [ ] **T2 (P1)** — ingest — Resumable acquire + shared manifest-diff. §0 #7. Files: `ingest/acquire.py`, `ingest/mediawiki.py`. Verify: Ctrl-C mid-crawl, rerun skips current pages.
- [ ] **T3 (P1)** — ingest — `clean.py` (corpus-format reference) + HTML-tables→Markdown + golden fixtures (3 page types) + verify corpus table preservation. §0 #3. Files: `ingest/clean.py`, `ingest/chunk.py`, `tests/fixtures/`. Verify: benefit-amount page keeps numbers as a table.
- [ ] **T4 (P1)** — guardrails — Allowlist + per-user rate cap in `input_guardrails`. §0 #5. Files: `rag/guardrails.py`, `bot/handlers.py`, `.env.example`. Verify: unknown chat_id blocked; cap enforced.
- [ ] **T5 (P1)** — core — Central Gemini wrapper (timeout+retry+fallback, model-version constant, single mock point). §0 #6,#9, conventions. Files: `rag/llm.py` (new), call sites. Verify: simulated 429 → retry → fallback msg; tests inject fake.
- [ ] **T6 (P2)** — bot — Non-text graceful reply. §0 #8. Files: `bot/handlers.py`. Verify: voice/photo → "please type".
- [ ] **T7 (P1)** — eval — Cross-lingual recall spike (~10 he↔ru questions) gating the fallback design. §0 #1. Files: `eval/spike_crosslingual.py`. Verify: report hit-rate; decide translate-fallback need.
- [ ] **T8 (P1)** — tests — Pure-logic unit suite (manifest-diff, clean/table, chunk, guardrail rules) + mocked-LLM node tests. §0 #9. Files: `tests/`. Verify: `pytest -m "not integration"` green, no network.
- [ ] **T9 (P2)** — tests — One E2E integration smoke (he+ru) vs fixture index. §0 #10. Files: `tests/test_e2e.py`. Verify: `pytest -m integration` returns cited answer, language matches.
- [ ] **T10 (P3)** — docs — Document the Issue-11 live-path optimization lever (offline judge / embedding grade) as a ready switch. §0 #11. Files: `PLAN.md`/`README.md`.
- [ ] **T11 (P1)** — bot — `render_answer()` in HTML parse mode (escaping + bidi + `disable_web_page_preview`). R6. Files: `bot/handlers.py`, `rag/prompts.py`. Verify: Hebrew answer + he-slug URL + disclaimer render correctly on a real phone.
- [ ] **T12 (P1)** — retriever — Similarity-floor calibration, per-language, against in/out-of-scope top-1 distributions; floor = lenient pre-filter, grade_docs is the gate. R3. Files: `rag/retriever.py`, `config.py`. Verify: off-topic refused, rare on-topic not wrongly refused.
- [ ] **T13 (P1)** — eval — Add follow-up (two-turn) + colloquial-recovery golden cases, he + ru; build ru set from ru-native topics; report native vs cross-lingual separately. R4/R5/R8. Files: `eval/golden_*.jsonl`, `eval/run_judge.py`. Verify: follow-up resolves; colloquial pass-2 recovers.
- [ ] **T14 (P1)** — retriever — Per-request active-collection pointer (handle-cached, atomic flip) so live-update needs no restart. R7. Files: `rag/retriever.py`, `scripts/sync.py`, `config.py`. Verify: flip pointer mid-session → next query uses new index, no restart.
- [ ] **T15 (P1)** — report — `REPORT.md` to the 5 rubric sections; §1–§3 drafted from PLAN, the business case + interview notes authored directly. A1. Verify: every rubric section present, repo link in place.
- [ ] **T16 (P1)** — research — 2 stakeholder interviews (ru-speaker / KZ user / social worker); notes → REPORT §2. A4. Verify: ≥2 insights summarized.
- [ ] **T17 (P1)** — perf — "Improve one dimension": measure baseline latency/cost, apply offline-judge + embedding-grade, record baseline→after; fill Technical-KPI table. A2/A5. Verify: after-latency < before; numbers in REPORT §4.
- [ ] **T18 (P2)** — pitch — Deck to the 8-min flow + **backup demo video** + rehearse. A6. Verify: runs in ≤8 min; video plays without network.

---

## Design review summary

An engineering-review pass over this plan raised 11 architecture/test issues; all 11 were
resolved before implementation. The one critical gap flagged to watch during the Hebrew
spike was silent table→number correctness (§20) — addressed by the tables→Markdown step in
the ingestion pipeline.

- **Unresolved issues:** 0 — every issue raised was decided.
- **Verdict:** ready to implement.
