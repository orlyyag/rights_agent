# Hebrew evaluation — linear (Tier-0)

Answer path: **linear**. Golden set: 40 in-scope (random sample, seed=42, from `Webiks_KolZchut_QA_Training_DataSet_v0.1.csv` after cleaning) + 8 hand-written adversarial.

## Retrieval
| Metric | Value |
|---|---|
| hit@5 (gold `doc_id` in top-5) | 70.0% (28/40) |

## Answer quality (in-scope, judged via Gemini)
| Metric | Value |
|---|---|
| correct (matches reference paragraph) | 39.3% (11/28) |
| faithful (every claim supported by gold paragraph — strict) | 17.9% (5/28) |
| language match (answer in Hebrew) | 100.0% (28/28) |
| citation present | 100.0% (28/28) |
| in-scope items the bot pre-refused (likely false negative) | 30.0% (12/40) |

## Refusals (adversarial / off-topic)
| Metric | Value |
|---|---|
| correct refusal | 100.0% (8/8) |

## Latency (end-to-end per question, baseline for A2)
| Metric | Value |
|---|---|
| p50/p95/max | mean=3.15s · median=3.22s · p95=6.25s · max=7.77s |

## Errors
| Metric | Value |
|---|---|
| eval errors | 0 |

## Retrieval misses (12 items)

Gold `doc_id` not in top-K — these point at chunking/embedding issues.

| id | gold_doc_id | question |
|---|---|---|
| in-001 | (gold not retrieved) | איך ומה אני כמעסיקה של עובדת משק בית צריכה לעשות במקרה שהעובדת נפגעה במהלך עבודת אצלי בבית… |
| in-002 | (gold not retrieved) | מסיימי שירות לאומי שנתיים מה מקבלים הטבות שירשמו לימודים? |
| in-003 | (gold not retrieved) | מה זה אכשרה? כמה ימים זה? |
| in-005 | (gold not retrieved) | אבא שלי חולה בדימציה אם הןא זכאי לתג נכה או קרוב משפחתו המסייע לחולה? |
| in-007 | (gold not retrieved) | למה לא מוזכר "פורום מיכל סלה" באתר, בנושא אלימות של בן זוג? |
| in-016 | (gold not retrieved) | חיילים צריכים להזמין תור להוציא דרכון? |
| in-022 | (gold not retrieved) | האם אני יכולה לבטל עסקה טלפונית באשראי אני בת 76 |
| in-026 | (gold not retrieved) | איפה הקלפי שלי ? |
| in-028 | (gold not retrieved) | איך אפשר לודע אם יש למתוך רישיון |
| in-032 | (gold not retrieved) | איך אני מחשבת שעות מחלה לימים? |
| in-036 | (gold not retrieved) | איך מחשבים 4 חודשים לביטול עסקה לפי החוק לצרכנים מעל גיל 65? |
| in-040 | (gold not retrieved) | איך מקבלים מהקופת חולים תור מיידי לפסיכולוג |
