"""Central configuration and frozen interface seams.

Single source of truth (PLAN.md §0 R9, §21 — frozen Day-1 seam #1). Holds:
  * pinned model versions + embedding dims (§0 Grill Q1/Q2),
  * the ACTIVE-collection pointer, read PER REQUEST and flipped atomically (R7, §0 #4),
  * the ``source`` flag: corpus fast-start vs own pipeline (§0 #2),
  * access control + tunable retrieval/agent thresholds.

Everything imports from here; nothing here imports project modules.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # optional — this module must import without python-dotenv installed
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# ── Paths ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(_env("KZ_DATA_DIR", str(ROOT / "data")))
RAW_DIR = DATA_DIR / "raw"                # data/raw/{lang}/{pageid}.json
MANIFEST_DIR = DATA_DIR / "manifest"      # data/manifest/{lang}.json
CORPUS_DIR = DATA_DIR / "corpus"          # official paragraph corpus (fast-start, §0 #2)
CHROMA_DIR = Path(_env("KZ_CHROMA_DIR", str(DATA_DIR / "chroma")))
ACTIVE_POINTER = DATA_DIR / "active_collection"   # one-line file, flipped by sync (R7)

# ── Models — pinned, never ``-latest`` (§0 Grill Q1/Q2) ──────────────────────
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEN_MODEL = _env("KZ_GEN_MODEL", "gemini-3.5-flash")  # current GA Flash (verified 2026-06-09); 3.0/3.1 are preview only
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 3072                                    # full fidelity (Q1)
EMBED_TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"          # asymmetric: chunks (Q1)
EMBED_TASK_QUERY = "RETRIEVAL_QUERY"                # asymmetric: queries (Q1)
GEN_TEMPERATURE = 0.0
GEN_THINKING_BUDGET = 0                             # low/zero live thinking (Q2)

# ── Data source + languages (§0 #2) ─────────────────────────────────────────
SOURCE = _env("KZ_SOURCE", "corpus")               # "corpus" | "pipeline"
LANGS = ("he", "ru")

# ── Collections / blue-green (§0 #4) ─────────────────────────────────────────
COLLECTION_PREFIX = "kz_v"
DEFAULT_COLLECTION = "kz_v1"

# ── Retrieval + agent thresholds (§0 Grill Q4, R3/R4) ────────────────────────
TOP_K = 8                  # fetch top-8 → grade → keep ≤5
KEEP_K = 5
# LENIENT pre-filter ONLY — grade_docs is the authoritative gate (R3). Calibrate per-lang (T12).
SIMILARITY_FLOOR = _env_float("KZ_SIM_FLOOR", 0.35)
SIMILARITY_FLOOR_BY_LANG = {"he": SIMILARITY_FLOOR, "ru": SIMILARITY_FLOOR}  # set by T12

# ── Eval judge (OpenAI, cross-provider, EVAL-ONLY — the bot never calls OpenAI) ─
# gpt-4.1: calibration (vs source-aware adjudication) showed it tracks human judgment
# (~91% vs 88% correctness) far better than o4-mini (~56-73%, unstable). See PROGRESS.
OPENAI_JUDGE_MODEL = _env("OPENAI_JUDGE_MODEL", "gpt-4.1")
OPENAI_JUDGE_REASONING_EFFORT = _env("OPENAI_JUDGE_REASONING_EFFORT", "low")  # only for o-series
GRADE_LOOP_CAP = 1         # bounded self-correction, one extra loop (§0 #11, R4)
MEMORY_TURNS = 5           # in-memory checkpointer window (Q7)
REWRITE_HISTORY_TURNS = 3  # turns fed to the condense/rewrite step (R5)
# Default answer path. "linear" = Tier-0 (cheap, retrieve→generate). "agent" =
# Tier-1 (rewrite→retrieve→grade→re-retrieve→generate, R4/R5; more LLM calls
# per turn). Flip via .env once the agent path has been spot-checked live.
ANSWER_PATH = _env("KZ_ANSWER_PATH", "linear")

# ── Central LLM wrapper behavior (§0 #6) ─────────────────────────────────────
LLM_TIMEOUT_S = _env_float("KZ_LLM_TIMEOUT_S", 20.0)
LLM_RETRIES = _env_int("KZ_LLM_RETRIES", 4)         # 4 retries → 5 attempts (covers quota refresh)
LLM_BACKOFF_S = _env_float("KZ_LLM_BACKOFF_S", 5.0)  # base; doubles each attempt
# Pace embed batches so a sustained build stays under the 1M-TPM Gemini Embedding cap
# (a batch of 100 chunks ≈ 25k tokens; sleeping 0.5s between batches → ~24 batches/min
# ≈ 600k TPM, ~40% headroom). Set to 0 to disable.
INTER_BATCH_SLEEP_S = _env_float("KZ_INTER_BATCH_SLEEP_S", 0.5)

# ── Access control (§0 #5) ───────────────────────────────────────────────────
def _parse_ids(raw: str) -> frozenset[int]:
    out: set[int] = set()
    for part in raw.replace(",", " ").split():
        try:
            out.add(int(part))
        except ValueError:
            pass
    return frozenset(out)


ALLOWED_CHAT_IDS = _parse_ids(_env("ALLOWED_CHAT_IDS"))  # from @userinfobot
RATE_LIMIT_PER_MIN = _env_int("KZ_RATE_LIMIT_PER_MIN", 20)
MIN_QUESTION_WORDS = _env_int("KZ_MIN_QUESTION_WORDS", 3)  # short greetings retrieve noise
MAX_QUESTION_CHARS = _env_int("KZ_MAX_QUESTION_CHARS", 500)  # ~80–100 words; protects cost, retrieval quality, injection surface

# ── Observability — LangSmith tracing (A8) ──────────────────────────────────
# Opt-in: set LANGSMITH_API_KEY in .env and every embed/generate call (and Tier-1
# agent-graph nodes) shows up in https://smith.langchain.com under
# LANGSMITH_PROJECT. Zero overhead when the key is unset.
LANGSMITH_API_KEY = _env("LANGSMITH_API_KEY") or _env("LANGCHAIN_API_KEY")
LANGSMITH_PROJECT = _env("LANGSMITH_PROJECT") or _env("LANGCHAIN_PROJECT") or "kolzchut-bot"
if LANGSMITH_API_KEY:
    # langsmith SDK + langchain both look at the env; set both legacy + new names
    # so any caller (our @traceable + any langchain code Tier-1 might add) finds it.
    os.environ.setdefault("LANGSMITH_API_KEY", LANGSMITH_API_KEY)
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", LANGSMITH_PROJECT)
    os.environ.setdefault("LANGCHAIN_PROJECT", LANGSMITH_PROJECT)

# ── Telegram (§9, R6) ────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_PARSE_MODE = "HTML"          # NOT MarkdownV2 (R6) — Hebrew titles/URLs shatter MarkdownV2
DISABLE_WEB_PAGE_PREVIEW = True       # keep ≤3 citations from ballooning (R6)
MAX_CITATIONS = 3


# ── ACTIVE-collection pointer — read per-request, flip atomically (R7) ───────
def get_active_collection() -> str:
    """Return the live collection name.

    Read PER REQUEST (R7) so a ``sync`` flip takes effect with no bot restart —
    required because the in-memory checkpointer forbids mid-demo restart (Q7).
    Falls back to ``DEFAULT_COLLECTION`` when the pointer doesn't exist yet.
    """
    try:
        name = ACTIVE_POINTER.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, NotADirectoryError):
        return DEFAULT_COLLECTION
    return name or DEFAULT_COLLECTION


def set_active_collection(name: str) -> None:
    """Atomically flip the active pointer (write-temp + ``os.replace``) so a
    concurrent reader never sees a half-written name (R7, §0 #4)."""
    ACTIVE_POINTER.parent.mkdir(parents=True, exist_ok=True)
    tmp = ACTIVE_POINTER.with_suffix(".tmp")
    tmp.write_text(name.strip() + "\n", encoding="utf-8")
    os.replace(tmp, ACTIVE_POINTER)
