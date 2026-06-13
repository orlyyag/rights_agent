# PRESENTATION_BRIEF — Kol Zchut Rights Agent (8-minute pitch)

This brief is the **structure** for the slide deck. Build **9 core presenter slides** in the exact order below,
then **7 labeled backup slides (B1–B7)** at the end. Each entry gives the on-slide text (keep it sparse),
the visual, the speaker note (this carries the graded depth), and the exact figures to use.

> The slides are the **only graded document** — the written report is not submitted. So every rubric fact
> (market research, stakeholder interviews, tech-stack reasoning, evaluation methodology) must live in the
> deck itself: concise core slides + **speaker notes** + the **B1–B7 backup slides**.

**Project:** a bilingual (Hebrew/Russian) rights assistant grounded in Israel's Kol Zchut database, delivered
through a messaging bot. **Repo:** `https://github.com/orlyyag/rights_agent`. **Try it:** `t.me/kolzchut_bot`.

---

## Global rules (every slide)
- **Corner QR** (small, bottom-right) on every slide → `t.me/kolzchut_bot`.
- **Footer:** GitHub repo URL on every slide. **Title slide:** big QR + full GitHub URL.
- English slide text. Big fonts (24pt+), ≤4 bullets/slide, ≤8 words/bullet, one idea per slide. No paragraphs.
- Example questions stay in their original **Hebrew/Russian, verbatim**.
- Use **exact figures** from the eval reports — never round or invent.

## Exact figures (do not alter)
- Retrieval: **83.3% hit@5** (35/42), MRR 0.59
- Answer correctness: **89.5%** (34/38 answered), human-anchored 88.2%, judge↔human agreement ~82%
- Faithfulness: **99.5%** (per-claim vs retrieved context — zero fabrication)
- Refusal: **100%** correct on adversarial (incl. prompt injection); **1/42** false refusals (2.4%)
- Latency: **~8.7s median** (target was <2s — **missed**); Cost: **$0.010 / question**
- Journey: **27.5% → 89.5%** correctness, same bot + retriever (measurement + infra repair)
- Curation alone: 27.5% → 40%; Over-refusal fix: false refusals **7 → 1**, faithfulness held 100%
- Judge: `o4-mini` 73.5% agreement + verdict flips → `gpt-4.1` tracks human
- Agentic vs linear: agent **$0.0156** (+56%) vs linear **$0.010**, 2–5 LLM calls vs 1, same hit@5, no gain
- Freshness: first-child birth grant current **2,103₪** vs stale corpus **1,986₪**
- Test set: **50 questions** (42 in-scope + 8 adversarial), Hebrew, fully re-curated
- Corpus: Hebrew ≈24.5k chunks (May-2024) + Russian wiki ≈4,072 articles; license CC BY-NC-SA 2.5 IL
- Demographics: **~1.3M Russian speakers** in Israel (a ~4,072-article Russian wiki already exists)
- **Kol Zchut 2025 stats** (sourced — official year-summary, `assets/kolzchut_2025_stats.png`):
  **11M users** · **25.6M visits** · 38M pageviews · 30M browsing-minutes · **1.3M Russian-site visits** ·
  **2M Arabic-site visits** · **660K questions to the site's AI chatbot** · 3.25M hand-offs to government
  sites · 630K to forms · **70% exercised rights** with the site's help · **78% found meaningful info** ·
  50% repeat users

---

## CORE SLIDES

### Slide 1 — Title / Hook
- **On slide:** "Kol Zchut Rights Agent — your rights, in your language." Show one real question in both
  scripts: `נולד לי תינוק — מה מגיע לי?` and `У меня родился ребёнок — что мне положено?` · big QR to
  `t.me/kolzchut_bot` · GitHub URL `https://github.com/orlyyag/rights_agent`.
- **Visual:** big QR; the two questions; Telegram + WhatsApp glyphs.
- **Speaker note:** "Imagine texting that on WhatsApp and getting a correct, sourced answer in 10 seconds.
  Scan the code — you can try it during Q&A."

### Slide 2 — The Problem
- **On slide:** "Israelis forfeit benefits they're legally owed — the rules are buried in dense Hebrew."
  - Trusted source, national scale: **11M users · 25.6M visits** to Kol Zchut in 2025.
  - Non-Hebrew demand is already here: **1.3M Russian** + **2M Arabic** site visits (2025).
  - People already want to *ask*, not browse: **660K questions** to its chatbot in 2025.
  - "Publicly available ≠ findable" — barely reachable if you can't read Hebrew.
- **Visual:** the **Kol Zchut 2025 year-summary image** (`assets/kolzchut_2025_stats.png`); two stakeholder
  cards — **Zvi, 74** and **Zina, 70**: *neither had heard of Kol Zchut*; both delegate web tasks to their
  kids; both on Telegram/WhatsApp.
- **Speaker note:** Open personal ("a relative nearly missed a benefit because the rules were buried in
  Hebrew"). The 2025 numbers prove three things: the content is trusted at national scale (11M users); the
  non-Hebrew demand is real (1.3M Russian + 2M Arabic visits, atop ~1.3M Russian speakers in Israel); and
  people already want to *ask*, not browse (660K chatbot questions). And it works when reached — 70% exercised
  rights with the site's help, 78% found meaningful info — but only *if* you can read Hebrew on a web page.
  Two real interviews (Zvi, Zina) confirm the unmet need and that a messaging app is the right channel.
- **Use only sourced numbers** (the figures above + the Kol Zchut 2025 image); do not invent any statistic.

### Slide 3 — The Solution
- **On slide:** "A bilingual rights agent — on the apps people already use: **WhatsApp & Telegram**."
  Four properties: **Native** (your language, not translated) · **Grounded + cited** (≤3 Kol Zchut links) ·
  **Fresh** (live numbers) · **Refuses** when it doesn't know. Small tag: *"Demo today on Telegram."*
- **Visual:** a real bot reply screenshot (Hebrew maternity answer with citations + AI caveat + disclaimer).
- **Speaker note:** WhatsApp is where most Israelis already are; we demo on Telegram (zero-onboarding bot API)
  — same UX, WhatsApp is a deploy detail, not an architecture change. What exists today: Kol Zchut's beta *web*
  AI chat — web-only (people who need it can't read the wiki to find it), Hebrew-depth only, no published eval.
  The gap is channel, languages, and rigor.

### Slide 4 — Demo (right after the Solution)
- **On slide:** "See it live." Three labeled mini-shots: Hebrew maternity Q (structured answer + **2,103₪**
  current grant + 3 citations); Russian pensioner Q (native Russian path); off-topic Q (clean refusal, no
  citation). Corner QR doubles as "try it now."
- **Visual:** three phone screenshots; small "video backup ready" tag.
- **Speaker note:** Run live on Telegram if Wi-Fi holds; otherwise play the 60-sec backup video. Call out the
  fresh number: the static corpus said 1,986₪; the live pipeline pulls the current 2,103₪. Highlight the
  refusal — it says "I don't know" instead of inventing.

### Slide 5 — Architecture + Stack
- **On slide:** a clean two-lane diagram:
  - **Offline pipeline:** MediaWiki → clean (BeautifulSoup) → chunk (~512 tok) → embed → Chroma (blue-green swap).
  - **Live path:** WhatsApp/Telegram → guardrails → retrieve (top-8) → *[grade / agentic loop — opt-in]* →
    generate → cite → render.
  - **Stack one-liner:** Gemini 3.5 Flash · gemini-embedding-001 (3072-d) · ChromaDB · LangGraph ·
    python-telegram-bot.
- **Visual:** the data-flow diagram; small "linear default, agent opt-in" tag.
- **Speaker note:** One design call: we *measured* the agentic loop — it cost +56% with no accuracy gain, so
  linear is the default and the agent is opt-in. Full tech-stack reasoning is in backup B3; the agent
  measurement is in B4.

### Slide 6 — Evaluation was the hard part (the turn) ★ centerpiece
- **On slide:** big line **"We built the bot in 2 days. It scored 27.5%."** Then four chips:
  1. **Broken golds** — the test set's "right answers" were tangential training chunks → re-curated → 40%.
  2. **Mis-diagnosed over-refusal** — "floor too strict" disproved by a calibration sweep; real cause was
     generation over-refusal → prompt fix → false refusals **7 → 1**, faithfulness held 100%.
  3. **Unvalidated judge** — `o4-mini` flipped its own verdicts (73.5% human agreement) → anchored to humans,
     swapped to `gpt-4.1`.
  4. **Silent index regression** — a rebuild quietly broke ANN recall; caught only by re-running eval → a
     **recall gate now blocks every index flip**.
- **Visual:** a **27.5% → 89.5%** arrow with "same bot + retriever — measurement + infra repair."
- **Speaker note:** The headline. None of the +62 points came from changing the model or prompt-magic — they
  came from fixing what we *measured with* and the infra under it. "Every layer was wrong before the bot was."
  Cross-provider judging plus a human anchor caught all four.

### Slide 7 — The Scoreboard
- **On slide:** results grid:
  - **83.3% hit@5** (35/42) · **89.5%** answer correctness (34/38; human-anchored 88.2%)
  - **99.5%** faithfulness (per-claim vs retrieved context — zero fabrication)
  - **100%** correct refusal on adversarial (incl. prompt injection) · **1/42** false refusals
  - **~8.7s** median latency · **$0.010** / question
  - Method: **50-question golden set** (42 in-scope + 8 adversarial); cross-provider LLM judge validated against
    human labels.
- **Visual:** scoreboard tiles; latency tile flagged amber.
- **Speaker note:** Own the latency honestly — the <2s target was not met; grounded ~250-word answers cost time;
  a real trade-off we'd improve with streaming and routing, not one we hid.

### Slide 8 — Business impact + production mindset
- **On slide:** two columns:
  - **Impact:** ~5–10 min manual search → ~10s sourced answer · reaches 1.3M Russian speakers + elderly on the
    channel they already use · both interviewees asked to be kept informed and to share.
  - **Production-ready:** per-chat + global rate caps · load-shedding · PII-redacted logging · prompt-injection
    defense · LangSmith observability.
- **Visual:** before/after time bar; a small "safe to open" shield.
- **Speaker note:** The "treat us like investors" slide — tangible ROI plus evidence we thought about cost,
  abuse, and scale.

### Slide 9 — Next steps + Close
- **On slide:** Russian eval set · **Arabic next** (2M site visits in 2025) · chunking fix (the one residual
  false refusal) · Cloud Run deploy · confidence-routed agent rescue. Close line:
  **"Scan the code — ask about your own rights."**
- **Visual:** big QR + GitHub URL repeated.
- **Speaker note:** "Two more weeks: ship the Russian eval and deploy to Cloud Run. Arabic is the obvious next
  language — 2M Arabic visits in 2025 — and a Russian wiki already exists to ground it."

---

## BACKUP SLIDES (label clearly; place at the very end)

### B1 — Market landscape & gaps  *(rubric §2: market research)*
- Existing: Kol Zchut's beta **web** AI chat (open-source Webiks/NNLP-IL Hebrew RAGbot — Elasticsearch +
  fine-tuned `me5-large`).
- Gaps: web-widget-only · Hebrew-depth only (ignores the ~4,072-article Russian wiki) · single retrieval pass,
  no self-correction · no published evaluation.

### B2 — Stakeholder interviews  *(rubric §2: technical discovery)*
- **Zvi, 74** — retired + part-time: how does part-time affect pension? employer obligations? *Never heard of
  Kol Zchut.*
- **Zina, 70** — runs a small business: minimum old-age allowance? free transit at 70? *Unaware Kol Zchut
  existed.*
- Insights: (1) real, unmet, consequential need; (2) discovery gap — "available ≠ findable"; (3) channel fit —
  both comfortable on Telegram/WhatsApp, delegate web to kids; (4) organic distribution — both asked to be kept
  informed and to share with relatives.

### B3 — Tech stack & why  *(rubric §3: tech stack)*
| Component | Choice | Why |
|---|---|---|
| Generation LLM | Gemini 3.5 Flash | Strong multilingual (he/ru), GA, low cost, fast |
| Embeddings | gemini-embedding-001 @3072 | Asymmetric multilingual retrieval, full fidelity |
| Vector DB | ChromaDB (cosine HNSW) | Local, zero-ops, blue-green collection swap |
| Orchestration | LangGraph | Opt-in agentic loop (rewrite/grade/re-retrieve) |
| Channel | python-telegram-bot (long-poll) | Zero onboarding; no inbound endpoint to attack |
| Eval judge | OpenAI gpt-4.1 | Cross-provider — avoids self-preference bias |

### B4 — Why linear, not agentic
- Measured on the golden set: agent **$0.0156** vs linear **$0.010** (+56%), 2–5 LLM calls vs 1, **same hit@5**,
  no correctness gain → linear is default, agent is opt-in.

### B5 — Who judges the judge?
- `o4-mini` agreed with human only 73.5% and flipped its own verdicts → swapped to `gpt-4.1`, which tracks the
  human count (~82% agreement). LLM-as-judge must itself be validated against humans.

### B6 — Security / abuse model
- Allowlist · per-chat 20/min + 20/day · global 60/min + 1000/day · load-shedding · treat source text as data
  (prompt-injection defense) · long-poll means no inbound DDoS surface · 100% correct refusal on adversarial.

### B7 — Data, freshness & licensing
- Hebrew corpus ≈24.5k chunks (May-2024 snapshot) + Russian wiki ≈4,072 articles.
- Manifest-diff incremental sync keeps numbers current (2,103₪ vs stale 1,986₪); blue-green index swap = no
  downtime. License: CC BY-NC-SA 2.5 IL (attribution + link-back).
