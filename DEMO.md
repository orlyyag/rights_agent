# Internal demo — Tier-0 runbook

The bot is a Hebrew rights assistant on Telegram, grounded in Kol Zchut.
**Russian and the agentic loop arrive in Tier-1 — Hebrew text-only for this demo.**

## Before the demo

1. **Keep the laptop awake** (the demo dies if macOS sleeps):
   ```bash
   caffeinate -d -i &
   ```
2. **Confirm the bot is up:**
   ```bash
   scripts/status_bot.sh        # ✓ Bot is running …
   ```
3. **If anything is off, restart cleanly:**
   ```bash
   scripts/run_bot.sh           # kills old, starts new, detached
   ```
4. (Optional) tail logs in another terminal: `tail -f data/bot.log`

## The demo flow

Open Telegram on a phone (or Telegram Desktop), find the bot, then:

| # | Send | What to point out |
|---|---|---|
| 1 | `/start` | Bilingual welcome + the "feel free to mention age / family / employment" hint |
| 2 | **מה מגיע לי אחרי לידה?** | Structured Hebrew answer with bold section headers, `•` bullets, 3 cited Kol Zchut pages (tappable), AI caveat, legal disclaimer at the bottom |
| 3 | **מה מזג האוויר היום בתל אביב?** | Off-topic → exactly one terse refusal line, no citations, no disclaimer — proves the grounding guardrail |
| 4 | **שלום** | Single-word → instant "על השאלה לכלול שלוש מילים לכל הפחות." — proves the input guardrail (no LLM call burned) |
| 5 | *(voice note or photo)* | "אפשר לכתוב את השאלה בטקסט?" — non-text handling (§0 #8) |

## What to highlight while demoing

- **Grounded**: every substantive answer cites real Kol Zchut pages, tappable straight from Telegram.
- **Two-layer transparency**: italic *"תשובה מבוססת AI…"* above the citations + italic legal disclaimer at the bottom (matches the official KZ on-site chat).
- **Refusal quality**: off-topic gets a clean one-sentence refusal, not a hallucinated answer.
- **Cost-aware**: 1–2-word inputs are rejected before any LLM/embedding call.
- **Observability**: every call is traced in **LangSmith → kolzchut-bot project** at `smith.langchain.com`. Show the dashboard if there's a screen.

## Known limitations (mention if asked)

- **Hebrew only** — Russian arrives in Tier-1 (own pipeline, no official RU corpus).
- **Linear RAG, not agentic** — the LangGraph self-correction loop (`grade_docs` → re-retrieve) is Tier-1.
- **Corpus snapshot is May 2024** — some benefit amounts may be stale; the cutover to our own pipeline closes that.
- **In-memory bot — restart wipes sessions.** Don't restart mid-demo.

## If something breaks mid-demo

| Symptom | Quick fix |
|---|---|
| Bot doesn't reply | `scripts/status_bot.sh` → if down, `scripts/run_bot.sh` |
| Answer looks weird (markdown asterisks visible, etc.) | the bot is on an older commit; `git log -1` should be `≥ 53dc71c`. If not, `git checkout tier-0-demo` then `scripts/run_bot.sh` |
| 429 RESOURCE_EXHAUSTED in logs | wait 60s (TPM cap) — exponential backoff retries automatically |
| Telegram says "Service is unavailable" | not us — Telegram. Wait 30s and retry |
| Laptop slept and bot stopped | `scripts/run_bot.sh` to restart; start `caffeinate -d -i` |

## After the demo

```bash
scripts/stop_bot.sh             # stop the bot when done
# kill the caffeinate too if you started one
```
