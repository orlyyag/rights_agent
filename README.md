# Kol Zchut Rights Assistant

Bilingual (Hebrew + Russian) Telegram agent answering Israeli rights/benefits
questions, grounded in [Kol Zchut](https://www.kolzchut.org.il) with citations.

See [PLAN.md](PLAN.md) for the design (architecture, decisions) and
[REPORT.md](REPORT.md) for the graded submission writeup.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate   # tested on Python 3.14
pip install -r requirements.txt
cp .env.example .env   # then fill GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_IDS
```

## Run

Build the index once (crawls both wikis politely at ~1 req/s, then chunks and
embeds — a few dollars of Gemini embedding credit):

```bash
export PYTHONPATH=.:src
python scripts/acquire.py he            # crawl Hebrew wiki  → data/raw/he/
python scripts/acquire.py ru            # crawl Russian wiki → data/raw/ru/
python scripts/build_pipeline.py he     # chunk+embed Hebrew → flip active pointer
python scripts/build_bilingual.py       # add Russian on top → bilingual kz_v2 → flip
```

Then ask a question from the CLI, or run the Telegram bot:

```bash
python scripts/ask.py "מה מגיע לי אחרי לידה?"
scripts/run_bot.sh                      # detached; status_bot.sh / stop_bot.sh to manage
```

Keep the index fresh with the incremental sync (manifest diff → blue-green
build → atomic pointer flip, no bot restart):

```bash
python scripts/sync.py he ru
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

## Language Behavior

The indexed Kol Zchut sources are Hebrew/Russian (`lang` metadata in Chroma).
By default, `KZ_ANSWER_LANGUAGE_MODE=auto` keeps explicit Hebrew and
Cyrillic/Russian routing; questions in any other language retrieve from the
**Hebrew** sources (the most complete corpus) and Gemini identifies the main
language of the question and answers in that same language. If the
language-filtered search comes back empty, retrieval retries unfiltered.
Set `KZ_ANSWER_LANGUAGE_MODE=he_ru` to restore the original Hebrew fallback for
Latin/ambiguous text.

**Citation links follow the question:** Russian questions present Russian
links; Hebrew and any other language present Hebrew links. When an answer used
a chunk from the other language (cross-lingual fallback), the cited page is
mapped to its counterpart via MediaWiki `langlinks` (cached per process). If no
translation exists, the original link is kept — attribution is never dropped.
