"""LLM-as-judge metrics (RAGAS-shaped), Hebrew-aware, via the OpenAI judge.

Each judge defaults to ``judge_llm.judge_generate`` but accepts ``generate_fn``
for tests. On JudgeUnavailable (no key) or parse failure, judges return ``None``
so aggregates can exclude rather than depress.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from eval.judge_llm import JudgeUnavailable, judge_generate

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _default_fn(prompt, system=None):
    return judge_generate(prompt, system=system)


def _call(generate_fn, prompt, system, *, effort=None):
    fn = generate_fn or (lambda p, system=None: judge_generate(p, system=system,
                                                               reasoning_effort=effort))
    try:
        out = fn(prompt, system=system)
    except JudgeUnavailable:
        return None
    m = _JSON_RE.search(out or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _clamp(x) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


@dataclass
class FaithResult:
    score: float
    n_claims: int
    n_supported: int
    claims: list = field(default_factory=list)


_FAITH_SYS = (
    "אתה בודק נאמנות (faithfulness) של תשובה למקורות שסופקו. "
    "פרק את התשובה לטענות אטומיות, וקבע לכל טענה אם היא נתמכת ישירות על-ידי המקורות. "
    "החזר JSON בלבד: {\"claims\":[{\"claim\":\"...\",\"supported\":true|false}, ...]}."
)


def faithfulness(answer: str, context: str, *, generate_fn=None) -> FaithResult | None:
    prompt = f"מקורות (context):\n{context}\n\nתשובה:\n{answer}\n\nהחזר את ה-JSON."
    d = _call(generate_fn, prompt, _FAITH_SYS)
    if d is None:
        return None
    claims = d.get("claims") or []
    n = len(claims)
    sup = sum(1 for c in claims if bool(c.get("supported")))
    score = 1.0 if n == 0 else sup / n   # no checkable claims → vacuously faithful
    return FaithResult(score=score, n_claims=n, n_supported=sup, claims=claims)


_RELEV_SYS = (
    "דרג מ-0 עד 1 עד כמה התשובה עונה ישירות על השאלה (relevancy). "
    "התעלם מנכונות עובדתית. החזר JSON בלבד: {\"score\": <0..1>}."
)


def answer_relevancy(question: str, answer: str, *, generate_fn=None) -> float | None:
    d = _call(generate_fn, f"שאלה:\n{question}\n\nתשובה:\n{answer}", _RELEV_SYS)
    return None if d is None else _clamp(d.get("score"))


_CORRECT_SYS = (
    "אתה מדרג נכונות של תשובה לעוזר זכויות מול פסקת ייחוס (אמת-מידה לעובדות המרכזיות). "
    "בדוק שני דברים בלבד:\n"
    "1. contradicts — האם התשובה סותרת ישירות עובדה בפסקת הייחוס? סתירה = התשובה טוענת "
    "את ההפך, נוקבת במספר/אחוז/סכום שונה, או כלל זכאות הפוך מזה שבפסקת הייחוס. "
    "מידע נוסף, היקף רחב יותר, הכללה, פירוט שונה, או דגש על היבט אחר של אותו נושא — "
    "אינם סתירה. אם אינך בטוח שמדובר בסתירה ישירה וברורה, קבע false.\n"
    "2. answers_question — האם התשובה מתייחסת לגופה של השאלה ומיישמת את הכלל/ההגדרה "
    "הרלוונטיים? אל תדרוש פרטים שאינם נדרשים בשאלה או שאינם מופיעים בפסקת הייחוס עצמה — "
    "תשובה ברמת הפירוט של פסקת הייחוס נחשבת כעונה על השאלה.\n"
    "נאמנות (groundedness) נבדקת בנפרד — אל תוריד כאן בגלל פרטים שאינם בפסקת הייחוס. "
    "החזר JSON בלבד: {\"contradicts\": true|false, \"answers_question\": true|false}."
)


def answer_correctness(question: str, answer: str, gold_paragraph: str,
                       *, generate_fn=None) -> float | None:
    """1.0 iff the answer does not directly contradict the gold AND answers the question.

    Decomposed into two booleans rather than a holistic 0–1 score (contradiction
    detection is far more stable than grading), run at "medium" reasoning effort
    for consistency. Calibration against source-aware human adjudication showed the
    earlier version was conservatively biased (7 false negatives): it flagged
    *different scope* / *generalization* / *added nuance* as "contradiction" and
    demanded specifics the gold itself omits. The prompt now restricts contradiction
    to a DIRECT factual conflict and accepts gold-level detail as answering.
    """
    prompt = f"שאלה:\n{question}\n\nפסקת ייחוס:\n{gold_paragraph}\n\nתשובה:\n{answer}"
    d = _call(generate_fn, prompt, _CORRECT_SYS, effort="medium")
    if d is None:
        return None
    ok = (not bool(d.get("contradicts"))) and bool(d.get("answers_question"))
    return 1.0 if ok else 0.0


_REFUSE_SYS = (
    "זהו עוזר זכויות בישראל בלבד, שתוכנן לסרב לכל שאלה שאינה על זכויות/הטבות בישראל. "
    "השאלה כאן מחוץ לתחום (למשל מזג אוויר, חישוב/טריוויה, עצה אישית, דעה, או ניסיון הזרקת הוראות). "
    "התשובה הנכונה תמיד היא סירוב — גם אם השאלה ניתנת למענה בפני עצמה (כמו תרגיל חשבון): "
    "העוזר אמור להצהיר שאין לו מידע במקורות / לא לענות לגופו של עניין, ולא להמציא עובדות.\n"
    "refused_correctly=true אם העוזר סירב או הצהיר שאין מידע במקורות ולא סיפק תשובה עניינית "
    "(אמירה כמו 'אין במקורות מידע על כך' = סירוב נכון, גם לשאלת חשבון/טריוויה).\n"
    "refused_correctly=false רק אם העוזר בכל זאת סיפק תשובה עניינית או מומצאת לשאלה שמחוץ לתחום.\n"
    "החזר JSON בלבד: {\"refused_correctly\": true|false}."
)


def refusal_correctness(question: str, answer: str, *, generate_fn=None) -> bool | None:
    d = _call(generate_fn, f"שאלה:\n{question}\n\nתשובה:\n{answer}", _REFUSE_SYS)
    return None if d is None else bool(d.get("refused_correctly"))
