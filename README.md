# Kol Zchut Rights Assistant

Bilingual (Hebrew + Russian) Telegram agent answering Israeli rights/benefits
questions, grounded in [Kol Zchut](https://www.kolzchut.org.il) with citations.

See [PLAN.md](PLAN.md) for the design (architecture, decisions) and
[REPORT.md](REPORT.md) for the graded submission writeup.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_IDS
```

## Layout

```
config.py    # frozen seam #1: models/dims, ACTIVE-collection pointer, thresholds, access control
schema.py    # frozen seam #3: ChunkMeta — the Chroma metadata contract (ingest writes, retriever reads)
src/
  rag/       llm.py (frozen seam #2: the one Gemini door) · retriever · graph · prompts · guardrails
  ingest/    mediawiki · acquire · clean · chunk · index
  bot/       telegram_app · handlers · session
  eval/      run_ragas · run_judge · report
scripts/     sync.py
tests/
```

The three **frozen seams** (`config.py`, `src/rag/llm.py`, `schema.py`) are the
Day-1 interface handshake (PLAN §21, R9): both build lanes depend on them, so
they are locked before either lane starts generating modules.

## Test

```bash
pytest -m "not integration"   # pure-logic, LLM-free (no network / API key)
```
