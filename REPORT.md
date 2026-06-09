# Kol Zchut Rights Assistant — Final Project Report

**Course:** Generative AI Systems Design & Implementation (Google × Reichman University)
**Team:** Student 1 — `<name>` · `<email>` | Student 2 — `<name>` · `<email>`
**Repo:** `<github link>` · **Submission date:** 2026-06-13

> This is the graded submission document, structured to the 5 rubric sections. Architecture
> details live in [PLAN.md](PLAN.md) (§4, §10) and are summarized here. Markers:
> 🖊️ **HUMAN** = needs your input/numbers · 🤖 **CC** = Claude Code can draft from PLAN.md.

---

## 1. Problem Selection & Definition (5%)

**Chosen business problem.** 🤖 CC — adapt from PLAN §1: every year Israelis lose money and
support they're legally entitled to because the rules are buried in hard-to-navigate Hebrew;
for ~1M+ Russian speakers and elderly citizens the language barrier turns "available" into
"invisible."

**Why we chose it.** 🖊️ HUMAN — personal connection (rubric prefers a problem you know from
work/daily life). E.g. "As a Russian-speaking immigrant / having watched a family member
struggle with bituach leumi forms, …"

**Background & Context**
- **Industry/Domain:** Govtech / civic access to rights & benefits (Israel).
- **Current Processes:** 🤖 CC — manual navigation of the Kol Zchut Hebrew wiki / calling
  helplines / social workers; slow, inconsistent, Hebrew-first.
- **Pain Points:** language barrier (he-only depth), unclaimed benefits, no conversational entry point.
- **Business/Social Impact:** 🖊️ HUMAN — quantify the stake (estimated unclaimed benefits,
  population affected). See §4 Business KPIs.

---

## 2. Market Research & Technical Discovery (15%)

**Market Landscape**
- **Existing Solutions:** 🤖 CC — from PLAN §3 (Kol Zchut's own beta on-site AI chat + the
  Webiks/NNLP-IL RAG backend, Elasticsearch + fine-tuned me5-large). Cite the repos.
- **Market Gaps:** 🤖 CC — from PLAN §3: no Telegram/messaging channel; Hebrew-only; single
  retrieval call (not agentic); no first-class Russian.
- **Target Audience:** 🖊️/🤖 — Russian-speaking immigrants, elderly citizens, social workers;
  people who live in messaging apps and won't use a web widget.

**Technical Discovery**
- **Stakeholder Interviews:** 🖊️ **HUMAN (T16)** — summarize ≥2 conversations (ru-speaker who
  navigated IL bureaucracy / KZ user / social worker). 2–3 insights each.
- **Data Availability & Quality:** 🤖 CC — from PLAN §5.1: KZ MediaWiki API (he ~7,338 / ru
  4,072 articles), CC BY-NC-SA license, official Paragraph Corpus (he, pre-chunked, May-2024
  snapshot — **tables flattened**), QA dataset (CC-BY-4.0) for the golden set.
- **Feasibility Assessment:** 🤖 CC — from PLAN §10/§13: Gemini + Chroma zero-train stack;
  constraints = WAF throttling, HTML cleaning, cross-lingual recall (validated by the spike).

---

## 3. Proposed GenAI System Architecture (20%)

**Solution Concept.** 🤖 CC — from PLAN §4.0: a bilingual Telegram agent; agentic RAG over a
single multilingual Chroma store, grounded answers with citations + disclaimer, refuse-if-empty.

**Key Functionalities** (technical + business benefit). 🤖 CC — from PLAN §4 "Five components":
ingestion pipeline, LangGraph agent core, Telegram bot, Guardrails, Evaluations.

**System Architecture Diagram.** Reuse PLAN [§4.0](PLAN.md) (system-at-a-glance) + [§4.1](PLAN.md)
(live-path zoom). 🖊️ HUMAN — redraw in draw.io/Figma for the slide (the rubric wants data
sources → preprocessing → GenAI components → output/feedback).

**Technology Stack** — from PLAN §10:

| Component | Choice | Reason |
|---|---|---|
| LLM (gen) | Gemini 3 Flash (pinned) | Course fit, strong he/ru, low latency |
| Embeddings | `gemini-embedding-001` @3072 | Native multilingual, strong he↔ru recall |
| Orchestration | LangGraph | Inspectable agent graph; guardrail/eval nodes |
| Vector store | Chroma (local) | Zero infra, metadata filter, demo-friendly |
| Bot | python-telegram-bot (long-poll) | No public URL needed; paired-phone demo |
| Eval | RAGAS + LLM-as-judge | Faithfulness/relevancy + tone/language/safety |

---

## 4. Implementation (50%)

**Scoping the POC** (from PLAN §0 tiers)
- **Input:** a rights question in Hebrew or Russian (Telegram text).
- **Output:** a grounded answer in the user's language + ≤3 citations + disclaimer; or a refusal.
- **Success metric:** ≥90% of demo questions correct + grounded + cited + right language.
- **Minimum viable test set:** golden set — he ~40–50, ru ~20–30 (human-verified) + ~5–8 adversarial/lang.
- **Target before adding complexity:** Tier-0 Hebrew grounded+cited answers on Telegram.

**Development Steps**
1. **Data Preparation** — 🤖 CC: corpus fast-start → own pipeline (acquire/clean/chunk/index),
   he+ru, tables→Markdown, single lang-tagged collection.
2. **Model Integration** — central `rag/llm.py` wrapper (timeout/retry/fallback, pinned versions).
3. **Application Logic** — LangGraph agent: rewrite → retrieve → grade_docs → bounded re-retrieve
   → generate → output guardrails; per-`chat_id` memory.
4. **Testing & Validation** — RAGAS + LLM-judge + hit@k over the golden set; E2E smoke; unit suite.

**Challenges & Solutions** (the rubric rewards honest documentation)
- **Challenge:** official corpus flattened benefit tables (silent wrong-number risk).
  **Solution (R1):** Tier-0 demo curates away from tabular amounts; our pipeline does tables→Markdown,
  gated by an eval case on a known benefit page.
- **Challenge:** cross-lingual recall uncertainty. **Solution:** the spike (T7) characterizes
  filter-relax; native Russian is the required path (4,072 ru articles).
- **Challenge:** 🖊️ HUMAN — add the real ones you hit (WAF, latency, …).
- **If the POC missed target:** 🖊️ HUMAN — document what you tried + how you adjusted scope.

**System Performance — Technical KPIs** (🖊️ fill *Achieved* after eval / T17)

| Metric | Description | Target | Achieved |
|---|---|---|---|
| Accuracy | % correct, grounded, right-language | ≥90% | `<value>` |
| Latency | avg input→response | <2s | `<before → after, T17>` |
| Error rate | % failed/incorrect | <5% | `<value>` |
| Uptime | availability | 99% | local long-poll demo — note as N/A |

**System Performance — Business KPIs** (hybrid framing; estimates OK, **label them**)

| Metric | Description | Baseline | After |
|---|---|---|---|
| Productivity gain | time-to-answer vs manual KZ navigation | `<~X min manual>` | `<~10s bot>` |
| Reach / access | population the channel unlocks | — | ~1M+ ru speakers (est.) |
| Customer satisfaction | demo-tester rating | `<x/5>` | `<x/5>` |
| Operational savings | est. KZ helpline / staff-hours saved | `<$/hrs>` | `<$/hrs>` |

**"Improve one dimension" (methodology step 6 / A2):** 🖊️/🤖 — baseline max-quality live path
(≈4 LLM calls) vs optimized (offline faithfulness judge + embedding-based grading): report
latency/cost **before → after** with the quality trade-off.

**Screenshots / Code Snippets:** 🖊️ HUMAN — Telegram he + ru answer, a follow-up, a refusal.

**Code repository:** `<github link>`

---

## 5. Pitch to Class (10%)

8-min deck (practice to 6), backup demo video, pairs split. Flow:
- **Hook** — 🖊️ a concrete stat/story (NOT "the age of AI").
- **Problem** — unclaimed rights + language barrier; why we chose it.
- **Solution** — bilingual grounded RAG agent in Telegram.
- **Architecture** — the §3 diagram, 30s.
- **Evaluation** — RAGAS/judge numbers, he vs ru; "improve one dimension" before→after.
- **Business value** — hybrid KPIs (productivity/access + operational).
- **Demo** — live query + backup video.
- **Next steps** — WhatsApp, Arabic, better Russian, voice→text.

---

## Appendix — Full code

`<github repo link>`
