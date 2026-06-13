# Kol Zchut Rights Assistant — Final Project Report

**Course:** Generative AI Systems Design & Implementation (Google × Reichman University)
**Team:** Orly Yagudayev · orli.yag@gmail.com (solo submission)
**Repo:** https://github.com/orlyyag/rights_agent (private) · **Submission date:** 2026-06-13

> This document is structured to the five rubric sections. Architecture details live in
> [PLAN.md](PLAN.md) (§4, §10) and are summarized here. Implementation was accelerated with
> AI coding assistance (Claude Code); all design decisions, evaluation methodology, and
> verification are the author's own and are documented throughout.

---

## 1. Problem Selection & Definition (5%)

**Chosen business problem.** Every year, Israelis forfeit money and support they are
legally entitled to — unemployment pay, disability allowances, birth grants, housing aid —
because the rules live in long, jargon-heavy Hebrew wiki pages. Kol Zchut documents
~7,300 rights guides, but *finding and reading* the right one is the barrier: for the
~1M+ Russian speakers and for elderly citizens, "publicly available" effectively means
"invisible." The cost is concrete: benefits go unclaimed, helplines absorb repetitive
questions, and social workers spend hours translating bureaucracy instead of helping.

**Why we chose it.** The gap is personal as well as systemic: navigating Israeli
bureaucracy in a second language is something many families experience directly — a
relative who nearly missed a benefit because the eligibility rules were buried in dense
Hebrew, or a parent who didn't know a grant existed at all. The problem is also a clean
fit for retrieval-augmented generation: a large, authoritative, frequently-updated
knowledge base (Kol Zchut) that people cannot navigate, where wrong answers carry real
cost — exactly the setting where grounding and refusal discipline matter more than
fluency.

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
- **Business/Social Impact (estimated).** The affected population is large: ~1.3M
  Russian speakers in Israel plus elderly and lower-literacy citizens who depend on
  Hebrew-only guidance. Social-rights take-up gaps are well documented internationally
  (non-take-up of entitlements commonly runs 20–40% for means-tested benefits), so even a
  modest improvement in discovery translates to meaningful unclaimed-benefit recovery and
  reduced helpline/social-worker load. Quantified KPIs (labelled as estimates) are in §4.

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
- **Stakeholder Interviews.** Two primary interviews with the core target population —
  Russian-speaking retirees:
  - **Zvi, 74** — retired and drawing his pension, but still working part-time. His open
    questions were concrete and high-stakes: how does part-time work affect his pension;
    what salary level keeps his pension rights intact; and is his employer obligated to
    pay him social/pension contributions? He had never heard of Kol Zchut.
  - **Zina, 70** — runs her own cosmetics business with no formal pension fund. She asked
    what minimum/basic payment she is entitled to (old-age allowance), and whether she
    qualifies for free public transport at 70. She, too, was unaware Kol Zchut existed.

  **Insights (each maps to a design decision):**
  1. **Real, unmet, consequential need.** Both had specific rights questions with direct
     financial impact (pension optimization, employer obligations, old-age allowance,
     senior transit) and did not know the answers — or that an authoritative source
     existed. → validates grounded, cited answers over generic chat.
  2. **Discovery gap.** Neither had heard of Kol Zchut; for this population "publicly
     available" is not the same as "findable." → the value is in the *channel*, not just
     the content.
  3. **Channel fit.** Both use WhatsApp/Telegram comfortably (simple, intuitive) and
     delegate complex web tasks to their children. → directly validates a messaging-bot
     interface over a website, and the Russian-native path.
  4. **Organic distribution.** Both asked to be kept informed when the bot is available
     and wanted to share the link with relatives and friends. → word-of-mouth reach is
     plausible within exactly the target community.
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
4. **Guardrails** (allowlist, per-minute rate cap, **per-chat daily question cap** for
   cost/abuse control, language enforcement, PII-redacted logging, injection defense,
   refuse-if-empty, personal-advice guard) → safe to expose to real users; answers stay
   informational, not legal advice; one user cannot drain the LLM budget.
5. **Evaluations** (golden set + heuristics + human-calibrated cross-provider LLM judge)
   → quality claims are measured, not vibes; regressions are caught before users see them.

**System Architecture Diagram.** Data sources → preprocessing → GenAI components →
output, with the offline pipeline feeding the live path through a per-request collection
pointer:

```mermaid
flowchart LR
    subgraph live["Live path · ~8.7s median per question"]
        TG[Telegram user] --> GR[Guardrails<br/>allowlist · rate · length<br/>injection · PII]
        GR --> RT[Retriever<br/>top-8 lang-filtered]
        RT --> GN[Gemini 3.5 Flash<br/>grounded generate]
        GN --> RD[render HTML<br/>+ ≤3 citations<br/>+ disclaimer]
        RD --> TG
    end
    subgraph offline["Offline pipeline · resumable"]
        MW[Kol Zchut<br/>MediaWiki API] --> AQ[acquire<br/>manifest-diff]
        AQ --> CL["clean<br/>HTML → text<br/>tables → Markdown"]
        CL --> CH[chunk<br/>~512 tok + heading prefix]
        CH --> EM[embed<br/>gemini-embedding-001<br/>@3072 dim]
        EM --> CR[(Chroma · 104,315 chunks<br/>he+ru · per-request<br/>active pointer)]
    end
    CR -.->|read at every query| RT
```

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
1. **Data Preparation** — corpus fast-start → own pipeline (acquire/clean/chunk/index),
   he+ru, tables→Markdown, single lang-tagged collection (104,315 chunks, active
   collection `kz_v3`).
2. **Model Integration** — central `rag/llm.py` wrapper (timeout/retry/fallback, pinned versions).
3. **Application Logic** — LangGraph agent: rewrite → retrieve → grade_docs → bounded re-retrieve
   → generate → output guardrails; per-`chat_id` memory.
4. **Testing & Validation** — heuristic retrieval metrics + a cross-provider LLM judge
   (OpenAI gpt-4.1, after calibration rejected the weaker o4-mini) for per-claim
   faithfulness, correctness, and relevancy + human calibration over the golden set; E2E
   smoke; unit suite (179 tests).

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
  the judge to gpt-4.1, which tracks human judgment closely (on the calibration run the
  judge scored 91.2% vs the human 88.2%). Full war story in [PROGRESS.md](PROGRESS.md).
- **Challenge:** 7/40 in-scope questions were falsely refused. The suspected cause
  (similarity floor too strict) was **disproved** by a calibration sweep — gold chunks
  score 0.67–0.84, far above the 0.35 floor. The real cause was generation-time
  over-refusal. **Solution:** prompt now permits applying stated rules to the user's case
  (plus an explicit personal-advice guard); false refusals 7 → 1 with faithfulness held
  at 100% and adversarial refusal at 100%.
- **Challenge:** the agentic loop didn't earn its latency. We built the full LangGraph
  path (rewrite → grade_docs → bounded re-retrieve) and **measured it against linear** on
  the golden set: ~56% higher cost per question ($0.0156 vs $0.010), ~1.7× latency
  (2–5 sequential LLM round-trips vs 1), same hit@5, no correctness gain — terminology
  broadening cannot fix "the answer isn't in the index", which is what most hard failures
  are. **Decision:** linear stays the serving default; the agent stays opt-in
  (`KZ_ANSWER_PATH=agent`). **Designed simplification (post-submission):** a
  *confidence-routed rescue* — two free signals (retrieval top-1 score, already computed;
  and the generator's own `[REFUSAL]` marker, which already judges context sufficiency)
  gate a single broaden→re-retrieve→regenerate rescue on the ~10–15% weak-retrieval tail.
  Median latency stays at linear; `grade_docs` and `rewrite` leave the hot path; the
  graph collapses from 6 nodes to 4. This is the same engineering loop as the judge and
  index findings: measure, then keep only what pays for itself.
- **Challenge:** the site's WAF blocks default bot user-agents. **Solution:** descriptive
  UA + ~1 req/s throttle + `maxlag=5` + resumable manifest-diff crawling.

**System Performance — Technical KPIs**

| Metric | Description | Target | Achieved |
|---|---|---|---|
| Accuracy | % correct, grounded, right-language | ≥90% | **89.5% answer-correctness** (34/38 answered of 42), **99.5% faithfulness** (grounded), **100%** right-language + cited on the curated golden set (see *Evaluation results* below) |
| Latency | avg input→response | <2s | **~8.7s median** (clean idle measurement, 2026-06-12; verbose ~250-word grounded answers, thinking budget 0). The <2s target is not met on the live path and we report that honestly rather than trim answer quality; A2 ("improve one dimension") was realized as the measured quality delta of the eval-system repair (see step-6 note below) |
| Error rate | % failed/incorrect | <5% | 0 eval/runtime errors; refusal-when-ungrounded (no fabrication observed) |
| Uptime | availability | 99% | local long-poll demo — N/A |

**Evaluation results (curated golden set, linear path over the pipeline collection)**

Golden set: 42 in-scope real user questions (held out from the Webiks KolZchut QA dataset) + 8 hand-written adversarial. The evaluation went through four honest iterations (full narrative in [PROGRESS.md](PROGRESS.md)):

1. **Gold curation.** The raw Webiks `gold_paragraph` is a retrieval-training chunk, not an answer key — usually a tangential page section — so it systematically under-credited correct answers. We re-curated all 40 golds against the actual indexed page text (every reference machine-verified verbatim; changelog in [eval/CURATION.md](eval/CURATION.md)).
2. **Metric redesign.** Reassigned every metric to the right mechanism: deterministic facts (hit/recall/MRR, citation, language, refusal split) are **heuristics**; semantic judgments use a **cross-provider OpenAI judge** (the generator is Gemini, so the judge has no self-preference — initially `o4-mini`, later replaced by `gpt-4.1`; see calibration below). Critically, **faithfulness is now judged per-claim against the retrieved context** (what the model actually saw), not the narrow gold paragraph — fixing a metric artifact that had pinned it at a meaningless 3.7%.
3. **Over-refusal fix.** The new refusal-split metric showed 7/40 *false* refusals. Investigation **disproved** the standing "similarity-floor too strict" hypothesis (gold chunks score 0.67–0.84, far above the 0.35 floor; the floor cuts nothing). The real cause was generation-time over-refusal; relaxing the prompt to apply stated rules (plus a personal-advice guard) cut false refusals 7 → 1 with **faithfulness staying at 100%** (no hallucination) and adversarial refusal staying at 100%.
4. **The eval as an infra regression net.** Re-running the eval after a routine index rebuild caught two silent regressions the same day: (a) the rebuilt Chroma collection had **query-dependent ANN recall holes** (true nearest neighbors at cosine-distance 0.24 never surfaced; proven by brute-force over the stored embeddings) — fixed with explicit HNSW build parameters plus a **brute-force-vs-ANN recall gate** that now blocks every blue-green pointer flip on a defective graph; and (b) a prompt rework had silently re-introduced over-refusal and dropped eligibility hedging (proven by A/B at temperature 0 on identical retrieved context) — fixed and pinned with regression tests. Full evidence chain in `eval/failure_analysis.txt`.

| Metric | Value | Note |
|---|---|---|
| Retrieval hit@5 / recall@5 / MRR | **83.3%** (35/42) / 83.3% / 0.59 | gold-doc-set aware |
| **Faithfulness** (per-claim vs retrieved context) | **99.5%** (n=38) | answers grounded in sources; no fabrication |
| **Answer-correctness** (no contradiction w/ gold + answers Q) | **89.5%** judge (34/38 answered) | judge validated against human adjudication of the prior run (88.2%, n=34); judge↔human agreement 82.4% |
| Answer-relevancy (addresses the question) | 91.6% (n=38) | |
| Language match / citation present | 100% / 100% | deterministic heuristics |
| Correct refusal (adversarial) | **100%** (8/8) | off-topic + prompt-injection all refused |
| False refusals (gold retrieved, bot refused) | **2.4%** (1/42) | down from 7/40; residual is one chunking gap (in-032) |

*Judge calibration (validation anchor) — and a judge-model finding.* All 34 answered items were independently re-adjudicated against the source pages (88.2% correct, 30/34). We **calibrated the LLM judge against that adjudication**, and it caught a real problem: the first judge (`o4-mini`) agreed only 73.5% and was systematically conservative (7 false negatives — it under-credited long, correct answers, and even *flipped its own verdict* across identical runs). Swapping the judge to **`gpt-4.1`** (a one-line, eval-only change — the bot stays Gemini) raised judge↔adjudication agreement to **~80%** (82.4% against the current run) and brought the judge's correctness estimate in line with the human 88.2%. Lesson: an LLM-as-judge must itself be validated; the model matters. (Cohen's κ reads negative here, but that's the κ-paradox under ~90% one-class base rate — raw agreement and the aggregate match are the meaningful signals.) *Note on RAGAS:* the plan called for a real-RAGAS cross-check, but RAGAS is not installable here (Python 3.14 has no `scikit-network` wheel; on 3.13 RAGAS conflicts with the released langchain v1), so we use **custom, Hebrew-aware RAGAS-style judges** validated by human adjudication.

**System Performance — Business KPIs** (hybrid framing; estimates OK, **label them**)

All figures below are **estimates**, labelled as such; they frame the value case rather than claim measured outcomes.

| Metric | Description | Baseline | After (est.) |
|---|---|---|---|
| Productivity gain | time-to-answer vs manual KZ navigation | ~5–10 min manual search & read | ~10s bot answer with citations |
| Reach / access | population the channel unlocks | Hebrew-only web widget | ~1.3M ru speakers + elderly, via Telegram |
| Customer satisfaction | demo-tester rating | — | _to add: ≥3 demo-tester ratings, x/5_ |
| Operational savings | est. KZ helpline / staff-hours saved | manual triage of repetitive Qs | deflects common look-ups; est. minutes saved per query |

**"Improve one dimension" (methodology step 6 / A2).** The dimension we improved is
**answer-quality measurement and reliability**, not raw latency. The headline result —
27.5% → 89.5% answer-correctness — came entirely from repairing the evaluation and serving
stack (broken golds → curated golds; mis-assigned metrics → mechanism-correct metrics;
an under-crediting judge → a calibrated cross-provider judge; a silently-degraded vector
index → explicit HNSW params + a recall gate), with the bot's model untouched. On the
latency dimension we made a deliberate, documented trade-off: the agentic path (≈2–5 LLM
calls) was measured against the linear path (1 call) and dropped as the default because it
cost ~56% more for no correctness gain (see Challenges). The designed next step
(confidence-routed rescue) recovers the agent's only real benefit at linear latency.

**Screenshots / Code Snippets:** _[To add before submission: Telegram screenshots — a
Hebrew answer with citations, a Russian answer, a follow-up, and a refusal. The live bot
and the pitch deck ([SLIDES.md](SLIDES.md)) carry these for the demo.]_

**Code repository:** https://github.com/orlyyag/rights_agent (private)

---

## 5. Pitch to Class (10%)

8-min deck, backup demo video. Flow:
- **Hook** — a concrete stat/story: open with the live bot (QR code) and a real benefit
  question, not an abstract "age of AI" framing.
- **Problem** — unclaimed rights + language barrier; why we chose it.
- **Solution** — bilingual grounded RAG agent in Telegram.
- **Architecture** — the §3 diagram, 30s.
- **Evaluation** — RAGAS/judge numbers, he vs ru; "improve one dimension" before→after.
- **Business value** — hybrid KPIs (productivity/access + operational).
- **Demo** — live query + backup video.
- **Next steps** — WhatsApp, Arabic, better Russian, voice→text; **confidence-routed
  rescue** (the agent's rescue value at linear latency — free score gate + refusal-triggered
  broaden, designed in §4 Challenges).

---

## Appendix — Full code

https://github.com/orlyyag/rights_agent (private)
