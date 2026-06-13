# TODOS

Deferred stretch items beyond the core scope (RAG + agents + guardrails + evals +
bilingual demo + sync). Each is scoped with rationale and dependencies for future work.

## Stretch

- [ ] **Cloud Run webhook deploy**
  - **What:** Deploy the bot behind a Cloud Run webhook for a public, always-on URL.
  - **Why:** Always-on demo without the Mac running; production-like story.
  - **Pros:** Looks professional; survives laptop sleep. **Cons:** GCP setup time; webhook vs polling rework.
  - **Context:** Core demo runs locally via long-polling (works for paired phone users). Only worth it if core is done early.
  - **Depends on:** working local bot.

- [ ] **Voice→text transcription (he + ru)**
  - **What:** Download Telegram voice notes, transcribe via Gemini, answer them.
  - **Why:** The target audience (elderly, immigrants) is voice-first — high-impact accessibility + standout demo moment.
  - **Pros:** Strong differentiator. **Cons:** Audio handling + transcription + error cases in 2 languages.
  - **Context:** Core ships a graceful "please type" reply (PLAN §0 #8); this upgrades it.
  - **Depends on:** working text answer path.

- [ ] **Translate-in-the-loop cross-lingual fallback**
  - **What:** When the user's language index is thin, retrieve in the other language and machine-translate the result.
  - **Why:** Only if the Day-1/2 spike shows vector-only (filter-relax) cross-lingual recall is weak.
  - **Pros:** Better Russian coverage if vectors underperform. **Cons:** Latency + a failure point in the live path.
  - **Context:** Replaced by filter-relax by default (PLAN §0 #1). This is the reactive fallback.
  - **Depends on:** Issue-1 spike result (T7).

- [ ] **Live-path LLM-call optimization**
  - **What:** Move the faithfulness LLM-judge offline and/or make grade_docs embedding-based (cuts ~2 live LLM calls).
  - **Why:** Only if live latency/cost becomes a problem; default is max-quality live (PLAN §0 #11).
  - **Pros:** Faster, cheaper answers. **Cons:** Slightly weaker live guardrail (offline eval still covers it).
  - **Context:** A ready lever, not a planned change.
  - **Depends on:** observed demo latency/cost.
