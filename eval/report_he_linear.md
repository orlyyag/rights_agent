# Hebrew evaluation — linear (Tier-0)

Answer path: **linear**. Golden set: 40 in-scope (random sample, seed=42, from `Webiks_KolZchut_QA_Training_DataSet_v0.1.csv` after cleaning) + 8 hand-written adversarial.

## Retrieval
| Metric | Value |
|---|---|
| hit@5 (gold `doc_id` in top-5) | 77.5% (31/40) |

## Answer quality (in-scope, judged via Gemini)
| Metric | Value |
|---|---|
| correct (matches reference paragraph) | 59.3% (16/27) |
| faithful (every claim supported by gold paragraph — strict) | 3.7% (1/27) |
| language match (answer in Hebrew) | 100.0% (27/27) |
| citation present | 100.0% (27/27) |
| in-scope items the bot pre-refused (likely false negative) | 32.5% (13/40) |

## Refusals (adversarial / off-topic)
| Metric | Value |
|---|---|
| correct refusal | 100.0% (8/8) |

## Latency (end-to-end per question, baseline for A2)
| Metric | Value |
|---|---|
| p50/p95/max | mean=5.68s · median=5.42s · p95=7.90s · max=9.79s |

## Errors
| Metric | Value |
|---|---|
| eval errors | 0 |

## Retrieval misses (9 items)

Gold `doc_id` not in top-K — these point at chunking/embedding issues.

| id | gold_doc_id | question |
|---|---|---|
| in-002 | (gold not retrieved) | מסיימי שירות לאומי שנתיים מה מקבלים הטבות שירשמו לימודים? |
| in-003 | (gold not retrieved) | מה זה אכשרה? כמה ימים זה? |
| in-005 | (gold not retrieved) | אבא שלי חולה בדימציה אם הןא זכאי לתג נכה או קרוב משפחתו המסייע לחולה? |
| in-008 | (gold not retrieved) | האם בן בת זוג של משרתי מילואים נחשבים גם ידוע/ה בציבור? |
| in-016 | (gold not retrieved) | חיילים צריכים להזמין תור להוציא דרכון? |
| in-022 | (gold not retrieved) | האם אני יכולה לבטל עסקה טלפונית באשראי אני בת 76 |
| in-026 | (gold not retrieved) | איפה הקלפי שלי ? |
| in-028 | (gold not retrieved) | איך אפשר לודע אם יש למתוך רישיון |
| in-040 | (gold not retrieved) | איך מקבלים מהקופת חולים תור מיידי לפסיכולוג |
