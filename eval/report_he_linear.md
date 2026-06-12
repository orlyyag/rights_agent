# Hebrew evaluation — linear (Tier-0)

Answer path: **linear**. Golden set: 42 in-scope (random sample, seed=42, from `Webiks_KolZchut_QA_Training_DataSet_v0.1.csv` after cleaning) + 8 hand-written adversarial.

## Retrieval (heuristic)
| Metric | Value |
|---|---|
| hit@5 (gold `doc_id` in top-5) | 83.3% (35/42) |
| recall@5 (gold-set found) | 83.3% |
| MRR (first gold rank) | 0.59 |

## Answer quality (in-scope answered, judged via OpenAI gpt-4.1)
| Metric | Value |
|---|---|
| answer_correctness (no contradiction w/ gold + answers Q) | 89.5% (n=38) |
| answer_relevancy (addresses the question) | 91.6% (n=38) |
| faithfulness (per-claim vs **retrieved context**) | 99.5% (n=38) |
| language match (heuristic, Hebrew-script) | 100.0% (38/38) |
| citation present (heuristic) | 100.0% (38/38) |

## Refusals
| Metric | Value |
|---|---|
| correct refusal (adversarial) | 100.0% (8/8) |
| false refusals (gold WAS retrieved → R3/T12 bug) | 2.4% (1/42) |
| justified refusals (no gold retrieved) | 7.1% (3/42) |

## Latency (end-to-end per question, baseline for A2)
| Metric | Value |
|---|---|
| p50/p95/max | mean=8.51s · median=8.71s · p95=10.55s · max=11.99s |

## Errors
| Metric | Value |
|---|---|
| eval errors | 0 |

## Judge calibration (answer_correctness vs human)
| Metric | Value |
|---|---|
| labeled n | 34 |
| judge↔human accuracy | 82.4% |
| Cohen's κ | -0.09 |
| confusion (tp/tn/fp/fn) | 28/0/4/2 |

## Retrieval misses (7 items)

Gold `doc_id` not in top-K — these point at chunking/embedding issues.

| id | gold_doc_id | question |
|---|---|---|
| in-002 | (gold not retrieved) | מסיימי שירות לאומי שנתיים מה מקבלים הטבות שירשמו לימודים? |
| in-005 | (gold not retrieved) | אבא שלי חולה בדימציה אם הןא זכאי לתג נכה או קרוב משפחתו המסייע לחולה? |
| in-008 | (gold not retrieved) | האם בן בת זוג של משרתי מילואים נחשבים גם ידוע/ה בציבור? |
| in-016 | (gold not retrieved) | חיילים צריכים להזמין תור להוציא דרכון? |
| in-028 | (gold not retrieved) | איך אפשר לודע אם יש למתוך רישיון |
| in-040 | (gold not retrieved) | איך מקבלים מהקופת חולים תור מיידי לפסיכולוג |
| in-042 | (gold not retrieved) | פיטרו אותי מהעבודה, מתי בכלל נכנס הכסף הזה מביטוח לאומי? |
