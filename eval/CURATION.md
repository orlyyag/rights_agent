# Golden-set curation — Hebrew in-scope (in-001 … in-040)

**Date:** 2026-06-10  ·  **Author:** Claude (Opus 4.8), with 8 parallel research agents

## Why

The in-scope golden set was sampled from the Webiks KolZchut QA CSV — a dataset built to train a retrieval embedder, **not** to evaluate end-to-end answers. So each `gold_paragraph` is an arbitrary chunk of the page, frequently a *tangential* section (application process, payment-abroad rules, fee tables) rather than the passage that answers the question. A few `gold_doc_id`s pointed at the wrong page entirely, and one (`12622`) wasn't even in the indexed corpus. Because the LLM judge scores each answer against `gold_paragraph`, a bad reference wrongly fails a correct answer.

## What was done

Every in-scope item was re-curated against the **actual page text the bot indexes** (`data/raw/he/*.json` → `ingest.clean`, exposed via `eval/curate_lib.py`). For each item we (a) confirmed or replaced the canonical page, and (b) replaced the reference with the specific passage that *directly answers the question*. Every `gold_paragraph` was machine-verified at the sentence-segment level to contain only verbatim page text (no fabrication); every `gold_doc_id` is confirmed present in the index so `hit@5` is achievable.

| Verdict | Count | Meaning |
|---|---|---|
| `CHANGE_DOC` | 8 | Gold page was the wrong topic → switched to the page that answers it |
| `KEEP_DOC_FIX_PARA` | 22 | Page correct, paragraph tangential → replaced with the answering passage |
| `KEEP_DOC_KEEP_PARA` | 9 | Already good page + answering paragraph (re-extracted verbatim) |
| `REPLACED_QUESTION` | 1 | Question itself was not a real rights query → swapped for a vetted corner case |

**9 documents changed; 22 paragraphs replaced; 9 confirmed as-is; 1 question replaced.** Confidence: {'med': 13, 'high': 26, 'low': 1}.

Originals preserved in `eval/golden_he.jsonl.orig`. Per-item research output in `eval/curate_out/B*.jsonl`.

## Document / question changes

- **in-001** (CHANGE_DOC, med): `9247` → `6441` — דמי ביטוח לאומי לעובד במשק בית
  - Q: איך ומה אני כמעסיקה של עובדת משק בית צריכה לעשות במקרה שהעובדת נפגעה במהלך עבודת אצלי בבית? היא עובדת אצלי פעמיים בחודש 4 שעות בכל פעם
  - השאלה היא מה חובת המעסיקה של עובדת משק בית כשהעובדת נפגעה; הדף הנכון הוא חובות המעסיק (רישום, דיווח ותשלום דמי ביטוח לאומי) שעליהם מותנית זכאות העובדת לקצבה בעקבות הפגיעה. הדף הקודם (9247) הסביר רק מהי תאונת עבודה ולא התייחס כלל לחובות המעסיקה.
- **in-007** (REPLACED_QUESTION, high): `13254` → `6607` — פיצויי פיטורים לעובד שהתפטר עקב מעבר דירה
  - Q: התפטרתי כי עברתי לגור רחוק ממקום העבודה — מגיע לי פיצויי פיטורים?
  - Original was a meta-complaint with a false premise (the Michal Sela Forum IS listed). Replaced — at user request — with a hard corner case: resigning due to relocation can entitle to severance, on conditions. Gold is the dedicated canonical page (6607), which the retriever finds and the bot answers correctly.
- **in-008** (CHANGE_DOC, high): `8749` → `21595` — היעדרות מעבודה של בני זוג או שותפים להורות של משרתי מילואים
  - Q: האם בן בת זוג של משרתי מילואים נחשבים גם ידוע/ה בציבור?
  - Question asks whether common-law partners of reservists count too; old page 8749 is only a navigation portal that never states the definition. Page 21595 explicitly lists 'ידועים בציבור' among eligible spouse types, directly answering yes.
- **in-019** (CHANGE_DOC, high): `13723` → `13670` — קבלת רישיון להיות משפחת אומנה (רישוי אומנה)
  - Q: למי מגישים בקשה להיות משפחת אומנה?
  - Old page (גוף מפעיל) only described the operating body's role; switched to the foster-licensing page, which explicitly states you apply directly to one of the operating bodies by area of residence and fill out its application form.
- **in-022** (CHANGE_DOC, high): `9612` → `5110` — ביטול עסקה שנעשתה באינטרנט או בטלפון
  - Q: האם אני יכולה לבטל עסקה טלפונית באשראי אני בת 76
  - The question asks whether a 76-year-old can cancel a telephone credit-card transaction; the old doc 9612 lists transactions that CANNOT be cancelled (wrong topic). Page 5110 is the canonical page on cancelling distance/telephone transactions, and the chosen passage gives the senior-citizen (65+) extended 4-month cancellation right that directly answers her case.
- **in-032** (CHANGE_DOC, med): `2554` → `446` — ימי מחלה
  - Q: איך אני מחשבת שעות מחלה לימים?
  - The old page (2554) is about work-day/work-week length and does not address sick days at all; the canonical 'ימי מחלה' page explains how sick days accrue (1.5 days per full month worked), which is what converting worked time to sick days requires.
- **in-035** (CHANGE_DOC, med): `8873` → `16006` — אישור להוצאת רישיון נהיגה
  - Q: האם בשביל לקבל תאריך לטסט זה אומר שמשרד הרישוי חושב שאני כשירה לרישיון מבחינה רפואית?
  - The question — does getting a test date mean the licensing office deems me medically fit — is answered by the license-approval process: medical fitness (health declaration, vision tests, and any further checks) is a prerequisite gate cleared at the initial approval stage, so only those found fit ('למי שיימצאו כשירים') are invited to proceed. The old page (8873) covers only the מרב"ד fitness exam, not the place of the fitness check in the licensing flow.
- **in-036** (CHANGE_DOC, high): `12622` → `5063` — ביטול עסקה ברוכלות
  - Q: איך מחשבים 4 חודשים לביטול עסקה לפי החוק לצרכנים מעל גיל 65?
  - Original gold page 12622 is not in the corpus; page 5063 is the canonical KolZchut page on the consumer 4-month cancellation right for people over 65, and this passage states exactly how the period is counted — from receipt of the product or contract, whichever is later.
- **in-040** (CHANGE_DOC, high): `4399` → `5116` — טיפול מרפאתי בבריאות הנפש
  - Q: איך מקבלים מהקופת חולים תור מיידי לפסיכולוג
  - Original page 4399 is about specialized medical centers for rare diseases and does not address psychologist/mental-health access; page 5116 is the canonical mental-health outpatient page, and this passage directly answers the 'immediate appointment' need — when treatment is needed immediately, go straight to a 24/7 psychiatric ER at no charge.

## All 40 items

| id | verdict | conf | doc | title |
|---|---|---|---|---|
| in-001 | CHANGE_DOC | med | `9247`→`6441` | דמי ביטוח לאומי לעובד במשק בית |
| in-002 | KEEP_DOC_FIX_PARA | med | `20137` | סיוע במימון לימודים במכינות קדם-אקדמיות לחיילים משוחררים ומסיימי שירות לאומי-אזרחי |
| in-003 | KEEP_DOC_FIX_PARA | high | `1202` | תקופת אכשרה לדמי אבטלה |
| in-004 | KEEP_DOC_FIX_PARA | med | `2455` | קצבת נכות כללית |
| in-005 | KEEP_DOC_FIX_PARA | med | `54` | תג חניה לנכה ולקרוב המסיע בוגר או ילד נכה |
| in-006 | KEEP_DOC_FIX_PARA | med | `489` | הודעה מוקדמת לפיטורים או התפטרות |
| in-007 | REPLACED_QUESTION | high | `13254`→`6607` | פיצויי פיטורים לעובד שהתפטר עקב מעבר דירה |
| in-008 | CHANGE_DOC | high | `8749`→`21595` | היעדרות מעבודה של בני זוג או שותפים להורות של משרתי מילואים |
| in-009 | KEEP_DOC_FIX_PARA | high | `12187` | הודעה מוקדמת להתפטרות |
| in-010 | KEEP_DOC_FIX_PARA | med | `11552` | הגבלת שכר טרחה עבור סיוע או ייצוג בתביעה לקצבת נכות ומענק נכות לנפגעי עבודה |
| in-011 | KEEP_DOC_FIX_PARA | high | `5393` | החזר אגרת רישוי לרכב |
| in-012 | KEEP_DOC_KEEP_PARA | high | `5286` | טיפולי שיניים לאנשים עם מוגבלויות |
| in-013 | KEEP_DOC_KEEP_PARA | high | `13788` | אי הסכמת הורה ביולוגי לשילוב ילדו באומנה |
| in-014 | KEEP_DOC_KEEP_PARA | med | `506` | משפחות שבראשן הורה עצמאי (משפחות חד הוריות) |
| in-015 | KEEP_DOC_FIX_PARA | high | `4033` | הנחה בארנונה לנכים |
| in-016 | KEEP_DOC_FIX_PARA | high | `13072` | הוצאת דרכון ביומטרי |
| in-017 | KEEP_DOC_FIX_PARA | high | `1307` | דמי פגיעה לנפגע עבודה |
| in-018 | KEEP_DOC_KEEP_PARA | high | `5907` | הורה אומנה (משפחת אומנה) |
| in-019 | CHANGE_DOC | high | `13723`→`13670` | קבלת רישיון להיות משפחת אומנה (רישוי אומנה) |
| in-020 | KEEP_DOC_FIX_PARA | low | `2890` | התנדבות אוטיסטים לשירות לאומי-אזרחי |
| in-021 | KEEP_DOC_KEEP_PARA | high | `9989` | ועדה רפואית לילד נכה עד גיל 3 |
| in-022 | CHANGE_DOC | high | `9612`→`5110` | ביטול עסקה שנעשתה באינטרנט או בטלפון |
| in-023 | KEEP_DOC_FIX_PARA | med | `466` | מענק לידה |
| in-024 | KEEP_DOC_KEEP_PARA | high | `5081` | ביטול רכישה שנעשתה בבית העסק והחזרת המוצר |
| in-025 | KEEP_DOC_FIX_PARA | high | `12413` | דמי אבטלה לעובדים הנמצאים בחופשה ללא תשלום |
| in-026 | KEEP_DOC_FIX_PARA | high | `8717` | פנקס הבוחרים לרשויות המקומיות |
| in-027 | KEEP_DOC_FIX_PARA | high | `435` | דמי הבראה |
| in-028 | KEEP_DOC_FIX_PARA | high | `20816` | זכותון ללקוחות של מתווכי דירות ומקרקעין |
| in-029 | KEEP_DOC_FIX_PARA | med | `2351` | זכותון עובדים במשק בית (עוזרות בית ומטפלים/ות) |
| in-030 | KEEP_DOC_KEEP_PARA | high | `14532` | תוספת משכנתא בגין שירות חובה או שירות לאומי-אזרחי |
| in-031 | KEEP_DOC_KEEP_PARA | high | `1521` | דמי אבטלה |
| in-032 | CHANGE_DOC | med | `2554`→`446` | ימי מחלה |
| in-033 | KEEP_DOC_FIX_PARA | med | `5705` | משפחתון בפיקוח |
| in-034 | KEEP_DOC_KEEP_PARA | high | `16371` | תנאי העסקה של עובד זר בסיעוד המועסק בבית המטופל |
| in-035 | CHANGE_DOC | med | `8873`→`16006` | אישור להוצאת רישיון נהיגה |
| in-036 | CHANGE_DOC | high | `12622`→`5063` | ביטול עסקה ברוכלות |
| in-037 | KEEP_DOC_FIX_PARA | med | `15308` | מדריך הורות משותפת |
| in-038 | KEEP_DOC_FIX_PARA | high | `3654` | פטור מארנונה לחיילים בשירות חובה וחיילים משוחררים |
| in-039 | KEEP_DOC_FIX_PARA | high | `16302` | עובד בניין |
| in-040 | CHANGE_DOC | high | `4399`→`5116` | טיפול מרפאתי בבריאות הנפש |

## Flagged for reviewer attention

- **in-007** was replaced (user request). The original — "Why isn't the Michal Sela Forum on the site?" — is a meta-complaint whose premise is false (the forum *is* listed). It now asks a hard corner case: *"I resigned because I moved far from work — am I owed severance?"* with gold = the dedicated page `6607` (פיצויי פיטורים לעובד שהתפטר עקב מעבר דירה). The bot answers this correctly.
- **in-020** (`low`): asks for the *variety of roles* offered to autistic girls in national service. No page in the corpus enumerates such roles, so the gold answer is necessarily generic — a genuine corpus-coverage gap, not a gold error.
- **in-015**: the 75%→"up to 80%" discount value exists only inside a table on the page, so the gold paragraph necessarily contains raw `|` table markup. It is a *discount of up to 80%*, not a full exemption.
- **in-008**: gold moved to `21595`, the page that actually defines reservist-spouse common-law status. The retriever does **not** surface it, so this is now an honest `hit@5` miss — we kept the correct gold rather than a retrieval-friendly one.
