# Kol Zchut Rights Assistant — Final Project Report

**Course:** Generative AI Systems Design & Implementation (Google × Reichman University)
**Team:** Student 1 — `<name>` · `<email>` | Student 2 — `<name>` · `<email>`
**Repo:** `<github link>` · **Submission date:** 2026-06-13

> This is the graded submission document, structured to the 5 rubric sections. Architecture
> details live in [PLAN.md](PLAN.md) (§4, §10) and are summarized here. Markers:
> 🖊️ **HUMAN** = needs your input/numbers · 🤖 **CC** = Claude Code can draft from PLAN.md.

---

## 1. Problem Selection & Definition (5%)

**Chosen business problem.** Every year, Israelis forfeit money and support they are
legally entitled to — unemployment pay, disability allowances, birth grants, housing aid —
because the rules live in long, jargon-heavy Hebrew wiki pages. Kol Zchut documents
~7,300 rights guides, but *finding and reading* the right one is the barrier: for the
~1M+ Russian speakers and for elderly citizens, "publicly available" effectively means
"invisible." The cost is concrete: benefits go unclaimed, helplines absorb repetitive
questions, and social workers spend hours translating bureaucracy instead of helping.

**Why we chose it.** 🖊️ HUMAN — personal connection (rubric prefers a problem you know from
work/daily life). E.g. "As a Russian-speaking immigrant / having watched a family member
struggle with bituach leumi forms, …"

**Background & Context**
- **Industry/Domain:** Govtech / civic access to rights & benefits (Israel).
- **Current Processes:** a person who suspects they're entitled to something today either
  (a) searches and reads the Kol Zchut Hebrew wiki themselves, (b) calls an NGO/government
  helpline, or (c) asks a social worker. All three are slow, Hebrew-first, and demand the
  user already knows the official name of the benefit ("מענק לידה") rather than their own
  words ("money after having a baby").
- **Pain Points:** language barrier (Hebrew-only depth), terminology gap (colloquial vs
  official terms), unclaimed benefits, no conversational entry point where people already
  are (messaging apps).
- **Business/Social Impact:** 🖊️ HUMAN — quantify the stake (estimated unclaimed benefits,
  population affected). See §4 Business KPIs.

---

## 2. Market Research & Technical Discovery (15%)

**Market Landscape**
- **Existing Solutions:** Kol Zchut runs its own beta on-site AI chat ("שאלו את ה-AI שלנו"),
  built on the open-source Webiks/NNLP-IL Hebrew RAGbot — Elasticsearch retrieval with a
  fine-tuned `me5-large` embedder and an LLM client
  ([Webiks-Hebrew-RAGbot](https://github.com/NNLP-IL/Webiks-Hebrew-RAGbot),
  [KZChatbot extensions](https://github.com/kolzchut)). It is a web widget on the wiki
  itself, Hebrew-only, with a single retrieval pass.
- **Market Gaps:** no messaging-app channel (people who need this most won't find a widget
  on a wiki they can't read); Hebrew-only depth despite a 4,072-article Russian wiki; a
  single retrieval call with no self-correction for colloquial phrasing; no published
  evaluation methodology.
- **Target Audience:** Russian-speaking immigrants, elderly citizens, and the social
  workers who serve them — populations that live in Telegram/WhatsApp and will not adopt a
  new app or website.

**Technical Discovery**
- **Stakeholder Interviews:** 🖊️ **HUMAN (T16)** — summarize ≥2 conversations (ru-speaker who
  navigated IL bureaucracy / KZ user / social worker). 2–3 insights each.
- **Data Availability & Quality:** Kol Zchut's MediaWiki API is open and read-accessible
  (he ~7,338 / ru ~4,072 content articles; CC BY-NC-SA 2.5 IL — attribute + link back,
  which our citation footer does by design). Two official datasets bootstrap the project:
  the Paragraph Corpus (Hebrew, pre-chunked, May-2024 snapshot — **benefit tables are
  flattened to text**, a verified data-quality finding that motivated building our own
  pipeline) and the QA dataset (CC-BY-4.0), which seeds the golden set.
- **Feasibility Assessment:** a zero-train stack (Gemini multilingual embeddings + local
  Chroma) makes bilingual retrieval feasible in days, not weeks. Verified constraints:
  the site's WAF blocks default bot user-agents (solved: descriptive UA + ~1 req/s
  throttle + `maxlag`), HTML needs custom cleaning (tables→Markdown to preserve benefit
  amounts), and cross-lingual recall is usable but weaker than native-language indexes —
  which is why native Russian is the required path and cross-lingual is a fallback.

---

## 3. Proposed GenAI System Architecture (20%)

**Solution Concept.** A multilingual Telegram agent for Israeli rights questions. The user
asks in their own words and language; the bot retrieves matching Kol Zchut guides from a
single lang-tagged Chroma store, generates a grounded answer **in the user's language**
with up to 3 source citations and a legal disclaimer, and refuses when the knowledge base
doesn't cover the question — it never invents. Hebrew and Russian are first-class (script
detection + native indexes); any other language is served by an auto mode that retrieves
cross-lingually and answers in the question's language.

**Key Functionalities** (technical → business benefit):
1. **Ingestion pipeline** (MediaWiki manifest-diff → clean → chunk → embed, blue-green
   index swap) → answers reflect the *current* wiki, including benefit amounts the static
   corpus had flattened or let go stale.
2. **Agentic RAG core** (LangGraph: history-aware rewrite → retrieve → grade_docs →
   bounded re-retrieve → generate) → colloquial questions and follow-ups get a second,
   smarter retrieval pass instead of a wrong answer.
3. **Telegram bot** (long-poll, HTML rendering, bidi-safe) → meets users where they
   already are; zero onboarding.
4. **Guardrails** (allowlist, rate cap, language enforcement, PII-redacted logging,
   injection defense, refuse-if-empty, personal-advice guard) → safe to expose to real
   users; answers stay informational, not legal advice.
5. **Evaluations** (golden set + heuristics + human-calibrated cross-provider LLM judge)
   → quality claims are measured, not vibes; regressions are caught before users see them.

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
| Eval | Heuristics + cross-provider LLM-judge (OpenAI gpt-4.1), RAGAS-style | hit/recall/MRR + per-claim faithfulness, correctness, refusal split; judge itself human-calibrated (o4-mini failed calibration and was replaced) |

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
4. **Testing & Validation** — heuristic retrieval metrics + cross-provider o4-mini judge (per-claim faithfulness, correctness, relevancy) + human calibration over the golden set; E2E smoke; unit suite.

**Challenges & Solutions** (the rubric rewards honest documentation)
- **Challenge:** official corpus flattened benefit tables (silent wrong-number risk) and
  was a stale May-2024 snapshot. **Solution (R1):** our pipeline converts HTML tables to
  Markdown with numbers verbatim; verified on real benefit pages — the corpus said 1,986₪
  for the first-child birth grant, the live pipeline pulls the current 2,103₪.
- **Challenge:** the golden set itself was noisy — the Webiks `gold_paragraph` is a
  retrieval-training chunk, often tangential to the question, so correct answers were
  failing eval. **Solution:** re-curated all 40 golds against the actual indexed page text
  (machine-verified verbatim); correctness moved +12.5pp from the *measurement* fix alone.
- **Challenge:** the LLM-as-judge was wrong before the bot was. The first judge (o4-mini)
  under-credited long correct answers and flipped verdicts between identical runs.
  **Solution:** human adjudication of all answered items as a calibration anchor → swapped
  the judge to gpt-4.1, which tracks human judgment (91.2% vs 88.2%). Full war story in
  [PROGRESS.md](PROGRESS.md).
- **Challenge:** 7/40 in-scope questions were falsely refused. The suspected cause
  (similarity floor too strict) was **disproved** by a calibration sweep — gold chunks
  score 0.67–0.84, far above the 0.35 floor. The real cause was generation-time
  over-refusal. **Solution:** prompt now permits applying stated rules to the user's case
  (plus an explicit personal-advice guard); false refusals 7 → 1 with faithfulness held
  at 100% and adversarial refusal at 100%.
- **Challenge:** the site's WAF blocks default bot user-agents. **Solution:** descriptive
  UA + ~1 req/s throttle + `maxlag=5` + resumable manifest-diff crawling.
- **If the POC missed target:** 🖊️ HUMAN — document what you tried + how you adjusted scope.

**System Performance — Technical KPIs** (🖊️ fill *Achieved* after eval / T17)

| Metric | Description | Target | Achieved |
|---|---|---|---|
| Accuracy | % correct, grounded, right-language | ≥90% | **73.5% answer-correctness**, **100% faithfulness** (grounded), **100%** right-language + cited on the curated golden set (see *Evaluation results* below) |
| Latency | avg input→response | <2s | ~6.5s median (linear; verbose grounded answers) — `<A2/T17 optimized: before → after>` |
| Error rate | % failed/incorrect | <5% | 0 eval/runtime errors; refusal-when-ungrounded (no fabrication observed) |
| Uptime | availability | 99% | local long-poll demo — N/A |

**Evaluation results (curated golden set, linear path over the pipeline collection)**

Golden set: 40 in-scope real user questions (held out from the Webiks KolZchut QA dataset) + 8 hand-written adversarial. The evaluation went through three honest iterations (full narrative in [PROGRESS.md](PROGRESS.md), spec/plan in `docs/superpowers/`):

1. **Gold curation.** The raw Webiks `gold_paragraph` is a retrieval-training chunk, not an answer key — usually a tangential page section — so it systematically under-credited correct answers. We re-curated all 40 golds against the actual indexed page text (every reference machine-verified verbatim; changelog in [eval/CURATION.md](eval/CURATION.md)).
2. **Metric redesign.** Reassigned every metric to the right mechanism: deterministic facts (hit/recall/MRR, citation, language, refusal split) are **heuristics**; semantic judgments use a **cross-provider OpenAI `o4-mini` judge** (the generator is Gemini, so the judge has no self-preference). Critically, **faithfulness is now judged per-claim against the retrieved context** (what the model actually saw), not the narrow gold paragraph — fixing a metric artifact that had pinned it at a meaningless 3.7%.
3. **Over-refusal fix.** The new refusal-split metric showed 7/40 *false* refusals. Investigation **disproved** the standing "similarity-floor too strict" hypothesis (gold chunks score 0.67–0.84, far above the 0.35 floor; the floor cuts nothing). The real cause was generation-time over-refusal; relaxing the prompt to apply stated rules (plus a personal-advice guard) cut false refusals 7 → 1 with **faithfulness staying at 100%** (no hallucination) and adversarial refusal staying at 100%.

| Metric | Value | Note |
|---|---|---|
| Retrieval hit@5 / recall@5 / MRR | **80%** (32/40) / 80% / 0.58 | gold-doc-set aware |
| **Faithfulness** (per-claim vs retrieved context) | **99.3%** (34/34) | answers grounded in sources; no fabrication |
| **Answer-correctness** (no contradiction w/ gold + answers Q) | **91.2%** judge · **88.2%** human-adjudicated (n=34) | gpt-4.1 judge now tracks adjudication closely (see below) |
| Answer-relevancy (addresses the question) | 92.4% (n=34) | |
| Language match / citation present | 100% / 100% | deterministic heuristics |
| Correct refusal (adversarial) | **100%** (8/8) | off-topic + prompt-injection all refused |
| False refusals (gold retrieved, bot refused) | **2.5%** (1/40) | down from 7/40; residual is one chunking gap (in-032) |

*Judge calibration (validation anchor) — and a judge-model finding.* All 34 answered items were independently re-adjudicated against the source pages (88.2% correct, 30/34). We **calibrated the LLM judge against that adjudication**, and it caught a real problem: the first judge (`o4-mini`) agreed only 73.5% and was systematically conservative (7 false negatives — it under-credited long, correct answers, and even *flipped its own verdict* across identical runs). Swapping the judge to **`gpt-4.1`** (a one-line, eval-only change — the bot stays Gemini) raised judge↔adjudication agreement to **79.4%** and brought the judge's correctness estimate (91.2%) in line with the human 88.2%. Lesson: an LLM-as-judge must itself be validated; the model matters. (Cohen's κ reads negative here, but that's the κ-paradox under ~90% one-class base rate — raw agreement and the aggregate match are the meaningful signals.) *Note on RAGAS:* the plan called for a real-RAGAS cross-check, but RAGAS is not installable here (Python 3.14 has no `scikit-network` wheel; on 3.13 RAGAS conflicts with the released langchain v1), so we use **custom, Hebrew-aware RAGAS-style judges** validated by human adjudication.

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
