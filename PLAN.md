# Kol Zchut Rights Assistant — Project Plan

> **One-liner:** Your rights in Israel, answered in your own language — right inside Telegram.

A bilingual (Hebrew + Russian) Telegram agent that answers questions about legal
rights and government benefits in Israel, grounded in the
[Kol Zchut](https://www.kolzchut.org.il) knowledge base, with citations.

**Course:** Gen AI for AI Development (Google × Reichman University, Israel) — final project.
**Team:** 2 people. **Timeline:** ~1 week to a working demo.
**Status of this doc:** design/plan (approved direction), pre-implementation.

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
3. Embed with **Gemini embeddings**; upsert to **Chroma** with metadata `{pageid, title, url, lang, section, lastrevid}`.
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
3. **retrieve** — Chroma similarity search filtered by language (top-k), with a
   cross-lingual fallback (query the other language + translate result) when the
   user's language index is thin.
4. **grade_docs** *(agent step)* — score retrieved chunks for relevance; if weak,
   reformulate and retrieve **once more** (hard cap = 1 extra loop, demo-safe).
5. **generate** — answer **in the user's language**, strictly grounded in retrieved
   context, with inline **citations** (title + URL) and a **disclaimer**.
6. **output_guardrails** — faithfulness/grounding check, citation presence,
   language match, and **refuse-if-no-context** ("I couldn't find this in Kol Zchut").

**Memory:** per-user session (last N turns) via a LangGraph checkpointer keyed by
Telegram `chat_id`; `/reset` clears it. Enables follow-ups ("and for freelancers?").

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
- **Commands:** `/start`, `/help`, `/lang he|ru|auto`, `/reset`, `/sources`.
- **UX:** "typing…" action while processing; answer + clickable source links; language auto-detected, overridable.
- **Runtime:** long-polling locally (POC), **webhook on Cloud Run** for the final demo.
- **Thin layer:** all logic lives in the agent core; the bot only maps Telegram I/O ↔ agent.

---

## 10. Tech stack & key trade-offs

| Area | Choice | Why | Trade-off |
|---|---|---|---|
| LLM + embeddings | **Google Gemini** | Course fit, strong he/ru, native embeddings | Vendor lock, quota |
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
    rag/     retriever.py  graph.py  prompts.py  guardrails.py
    bot/     telegram_app.py  handlers.py  session.py
    eval/    golden_he.jsonl  golden_ru.jsonl  run_ragas.py  run_judge.py  report.py
  scripts/   sync.py        # acquire + index entrypoint (cron/scheduler)
  tests/
  docs/      presentation/
```

---

## 12. One-week plan (2 people)

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
| Russian coverage thin | Cross-lingual fallback (retrieve he, translate); translate golden subset |
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
