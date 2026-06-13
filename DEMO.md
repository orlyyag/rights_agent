# Demo runbook

A bilingual (Hebrew + Russian) rights assistant on Telegram, grounded in Kol Zchut and
served from the project's own pipeline index (`kz_v3`, ~104k chunks, he+ru). Answers are
cited and refuse-when-ungrounded. Any other language is handled by an auto mode that
retrieves cross-lingually and answers in the question's language.

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

Open Telegram (phone or Desktop), find the bot (`@kolzchut_bot`), then:

| # | Send | What to point out |
|---|---|---|
| 1 | `/start` | Bilingual welcome + the "feel free to mention age / family / employment" hint |
| 2 | **מה מגיע לי אחרי לידה?** | Structured Hebrew answer — bold section headers, `•` bullets, 3 tappable Kol Zchut citations, AI caveat, legal disclaimer |
| 3 | **Какие льготы положены пенсионеру в Израиле?** | Russian question → Russian answer with Russian-language citations — shows the native bilingual path |
| 4 | **מה מזג האוויר היום בתל אביב?** | Off-topic → exactly one terse refusal line, no citations, no disclaimer — proves the grounding guardrail |
| 5 | **שלום** | Single word → instant "על השאלה לכלול שלוש מילים לכל הפחות." — proves the input guardrail (no LLM call burned) |
| 6 | *(voice note or photo)* | "אפשר לכתוב את השאלה בטקסט?" — non-text handling (§0 #8) |

## What to highlight while demoing

- **Grounded & cited**: every substantive answer cites real Kol Zchut pages, tappable straight from Telegram.
- **Fresh numbers**: the pipeline reads the live wiki with tables→Markdown, so benefit amounts are current (e.g. the first-child birth grant is **2,103 ₪**, not the stale 1,986 ₪ from the off-the-shelf May-2024 corpus).
- **Bilingual, native**: Hebrew and Russian are first-class (own pipeline per language), not Hebrew-with-translation.
- **Two-layer transparency**: italic *"תשובה מבוססת AI…"* above the citations + italic legal disclaimer at the bottom (matches the official KZ on-site chat).
- **Refusal quality**: off-topic gets a clean one-sentence refusal, never a hallucinated answer.
- **Safe to open up**: per-chat rate cap (20/min) + daily cap (20/day), global throughput/daily caps, and load-shedding bound cost and abuse; short inputs are rejected before any LLM call.
- **Observability**: every call is traced in **LangSmith → kolzchut-bot project** at `smith.langchain.com` — show the dashboard if a screen is available.

## Known limitations (mention if asked)

- **Russian is served but not yet formally evaluated** — the golden-set evaluation is Hebrew; a human-verified Russian golden set is planned before production.
- **Agentic path is opt-in, not the default** — the LangGraph self-correction loop (`grade_docs` → re-retrieve) is built and evaluated, but measurement showed no quality gain over the linear path, so linear is the serving default (`KZ_ANSWER_PATH=agent` to try it).
- **In-memory state — restart wipes sessions and rate/quota counters.** Avoid restarting mid-demo.

## If something breaks mid-demo

| Symptom | Quick fix |
|---|---|
| Bot doesn't reply | `scripts/status_bot.sh` → if down, `scripts/run_bot.sh` |
| Answer looks weird (raw markdown asterisks, etc.) | the bot may be on an older commit; `git log -1`, then `scripts/run_bot.sh` to restart on current code |
| 429 RESOURCE_EXHAUSTED in logs | wait 60s (TPM cap) — exponential backoff retries automatically |
| "Service is at capacity" / "busy" replies | the global cap or load-shed tripped — expected under a flood; eases as traffic drops |
| Telegram says "Service is unavailable" | not us — Telegram. Wait 30s and retry |
| Laptop slept and bot stopped | `scripts/run_bot.sh` to restart; start `caffeinate -d -i` |

## After the demo

```bash
scripts/stop_bot.sh             # stop the bot when done
# kill the caffeinate too if you started one
```
