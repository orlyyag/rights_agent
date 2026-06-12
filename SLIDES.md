---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section {
    font-size: 28px;
    font-family: 'Inter', 'Helvetica Neue', sans-serif;
  }
  section h1 { font-size: 54px; color: #1a73e8; }
  section h2 { font-size: 40px; color: #1a73e8; }
  section h3 { font-size: 32px; }
  section.title h1 { font-size: 64px; margin-bottom: 0; }
  section.title p  { font-size: 32px; color: #5f6368; }
  table { font-size: 24px; }
  blockquote { border-left: 6px solid #1a73e8; color: #202124; }
  .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }
  .stat { font-size: 80px; color: #1a73e8; font-weight: 700; line-height: 1; }
  .label { font-size: 22px; color: #5f6368; }
  .muted { color: #5f6368; }
---

<!-- _class: title -->

# Kol Zchut Rights Assistant

A Hebrew Telegram bot that answers "what am I entitled to?" — grounded in real Kol Zchut pages, cited, in seconds.

<br>

**Team:** `<your names>`
Final Project · Generative AI Systems Design · 2026

---

## The problem

> **Personal hook:** *`<one-sentence story from your own life — e.g., a relative who almost missed a benefit because the rules are buried in Hebrew>`*

<div class="columns">

**The reality**
- Every year, Israelis don't claim benefits they're entitled to — unemployment, maternity, disability, housing aid
- The rules are buried in dense Hebrew on Kol Zchut (`kolzchut.org.il`)
- **1M+ Russian speakers** + many elderly citizens face a language wall

**Why now**
- LLMs can finally read a question in plain Hebrew and find the right answer in a trusted source
- Messaging apps are where people already are — no new app to install

</div>

---

## What we built

<div class="columns">

**Live Telegram bot**
- Answers Hebrew rights questions
- Every answer cites real KZ pages
- Refuses politely when off-topic (no hallucination)
- Two-layer transparency: *"AI-generated, verify via links"* + legal disclaimer
- Input guardrails: allowlist, rate-cap, 3-word minimum, 500-char maximum, injection-resistant

**Honest scope**
- Hebrew live · Russian served cross-lingually (native index in progress)
- **Auto language mode:** ask in any language, answered in that language from Hebrew sources
- Linear RAG default · LangGraph agent loop opt-in · follow-up memory per chat
- Local long-poll (no public URL needed for the demo)

</div>

<!-- speaker note: open with the screenshot on the next slide; this slide just lists what's there -->

---

## Architecture

```mermaid
flowchart LR
    subgraph live["Live path · ~3s per question"]
        TG[Telegram user] --> GR[Guardrails<br/>allowlist · rate · length<br/>injection · PII]
        GR --> RT[Retriever<br/>top-8 lang-filtered]
        RT --> GN[Gemini 3.5 Flash<br/>grounded generate]
        GN --> RD[render HTML<br/>+ ≤3 citations<br/>+ disclaimer]
        RD --> TG
    end
    subgraph offline["Offline pipeline · resumable"]
        MW[Kol Zchut<br/>MediaWiki API] --> AQ[acquire<br/>manifest-diff]
        AQ --> CL["clean<br/>HTML → text<br/><b>tables → Markdown</b>"]
        CL --> CH[chunk<br/>~512 tok + heading prefix]
        CH --> EM[embed<br/>gemini-embedding-001<br/>@3072 dim]
        EM --> CR[(Chroma<br/>per-request<br/>active pointer)]
    end
    CR -.->|read at every query| RT
    classDef hi fill:#e8f0fe,stroke:#1a73e8,color:#202124
    class GN,EM,CR hi
```

**Key idea:** offline plane and live plane never share a half-built index — the active pointer flips atomically.

---

## Tech stack — why each choice

| Component | Choice | Why |
|---|---|---|
| Generation | **Gemini 3.5 Flash** | Current GA Flash, strong Hebrew/Russian, low/zero thinking budget for speed |
| Embeddings | **`gemini-embedding-001` @ 3072** | Native multilingual, asymmetric task types for he↔ru recall |
| Vector store | **Chroma (local)** | Zero infra, metadata filter, blue-green-friendly |
| Orchestration | **LangGraph** | Inspectable agent graph; every node traceable |
| Observability | **LangSmith** | Per-call cost · tokens · latency · thread_id grouping |
| Bot | **python-telegram-bot** (long-poll) | No public URL needed; works from a laptop |
| Eval judge | **OpenAI gpt-4.1** (eval-only) | Cross-provider judge avoids self-grading bias; human-calibrated (o4-mini failed calibration) |

The bot itself never calls OpenAI — only the eval harness does.

---

## It actually works

<div class="columns">

**Question:** *"מה מגיע לי אחרי לידה?"* (what am I entitled to after giving birth?)

**Bot output:**
- Hospital stay rules · ambulance reimbursement
- **Birth grant 2,103 ₪** · child allowance 169 ₪/mo
- Maternity benefit eligibility tiers (15 vs 8 weeks)
- 3 clickable Kol Zchut citations
- Italic "AI-generated, verify" caveat
- Italic legal disclaimer

</div>

> The official Kol Zchut on-site AI chat returns the same numbers. Our pipeline pulls **today's amounts** (`2,103 ₪`); the off-the-shelf training corpus had stale `1,986 ₪` from May 2024.

*Screenshot placeholder: `![w:400](path/to/bot_screenshot.png)`*

---

## Evaluation

48 questions: 40 in-scope (curated from the Webiks QA dataset) + 8 hand-written adversarial.

<div class="columns">

<div>
<div class="stat">83.3%</div>
<div class="label">hit@5 / recall@5 — gold doc in top-5</div>
<br>
<div class="stat">89.5%</div>
<div class="label">answer correctness (gpt-4.1 judge, 34/38 answered · human-anchored 88.2%)</div>
<br>
<div class="stat">100%</div>
<div class="label">correct refusal on adversarial (incl. prompt-injection)</div>
</div>

<div>
<div class="stat">99.5%</div>
<div class="label">faithfulness — per-claim vs retrieved context · zero fabrication</div>
<br>
<div class="stat">100%</div>
<div class="label">language match · 100% cited · 1/42 false refusals</div>
<br>
<div class="stat">$0.010</div>
<div class="label">per question · ~8.7s median — full cost visible in LangSmith</div>
</div>

</div>

> **Full LangSmith trace tree per question:** model · tokens · cost · latency · thread_id — every call.

---

## The hardest part

> *"Build the eval before you trust the eval."*

<div class="columns">

**The crisis (×4)**
- Built the bot. Ran 48 questions. Got **27.5%** correctness. Read 11 failures by hand → the **golds were broken** (training-set chunks, often tangential). Re-curated all 40 against real page text → **40%**.
- Still refusing 7/40 in-scope questions. The suspected fix (similarity floor) was **disproved by a calibration sweep** — the real bug was generation over-refusal. Prompt fix → 1/40, faithfulness held at 100%.
- Then we **calibrated the judge against a human** — o4-mini under-credited correct answers and flipped its own verdicts. Swapped to gpt-4.1 → judge agrees with human adjudication.
- Then a routine index rebuild **silently broke ANN recall** (true nearest neighbors never surfaced — proven by brute force over the stored vectors). Caught only because we re-ran the eval after an infra change. Now a recall gate blocks every index flip.

**The lesson**
- Every layer was wrong before the bot was: gold → refusal hypothesis → judge → vector index
- Cross-provider judging + a human anchor + re-running the eval after EVERY change caught all four
- Same bot, same retriever throughout: **27.5% → 89.5%** was measurement + infra repair, not model work

</div>

> The rubric says *"a well-documented failure is worth more than a fudged success."* Honest failure analysis was the most valuable thing we did.

---

## What we learned

1. **Eval data quality > model tuning.** We almost shipped "the agent loop helps" — a more careful look showed the judge was wrong, not the bot.
2. **Observability is a force multiplier.** LangSmith trace trees with per-call cost + thread_id made every debugging session 5× faster.
3. **Freshness beats cleverness.** The biggest measurable win was our own ingestion pipeline with `tables → Markdown`, not the agentic loop.
4. **Hebrew RTL + Telegram HTML + Markdown is its own engineering project.** Three layers of escaping — every one of them had a bug at some point.
5. **Resumable everything.** Crawls die at 5 AM; embeds hit rate limits at 26%. Resumable by construction is non-optional.

---

## Next steps

<div class="columns">

**Two-week roadmap**
1. **Russian eval at parity** — native ru index + human-verified ru golden set; report native vs cross-lingual separately.
2. **Chunking fix for in-032-class gaps** — the one residual false refusal is a chunk-boundary problem, not retrieval depth.
3. **Cloud Run + webhook** — always-on, no laptop in the room.
4. **Production guardrails** — structured admin metrics from LangSmith, abuse monitoring.

**Could become**
- A pilot with **Israeli social-services NGOs** — they have the user base, we have the channel
- A **WhatsApp** version — bigger reach for the target audience
- **Arabic** as the third KZ language

</div>

> **Want a pilot?** Bot is live on Telegram, code on GitHub, eval reports in the repo. Talk to us.
