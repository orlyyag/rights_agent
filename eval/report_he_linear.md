# Hebrew evaluation — linear (Tier-0)

Answer path: **linear**. Golden set: 40 in-scope (random sample, seed=42, from `Webiks_KolZchut_QA_Training_DataSet_v0.1.csv` after cleaning) + 8 hand-written adversarial.

## Retrieval (heuristic)
| Metric | Value |
|---|---|
| hit@5 (gold `doc_id` in top-5) | 80.0% (32/40) |
| recall@5 (gold-set found) | 80.0% |
| MRR (first gold rank) | 0.58 |

## Answer quality (in-scope answered, judged via OpenAI gpt-4.1)
| Metric | Value |
|---|---|
| answer_correctness (no contradiction w/ gold + answers Q) | 91.2% (n=34) |
| answer_relevancy (addresses the question) | 92.4% (n=34) |
| faithfulness (per-claim vs **retrieved context**) | 99.3% (n=34) |
| language match (heuristic, Hebrew-script) | 100.0% (34/34) |
| citation present (heuristic) | 100.0% (34/34) |

## Refusals
| Metric | Value |
|---|---|
| correct refusal (adversarial) | 100.0% (8/8) |
| false refusals (gold WAS retrieved → R3/T12 bug) | 2.5% (1/40) |
| justified refusals (no gold retrieved) | 12.5% (5/40) |

## Latency (end-to-end per question, baseline for A2)
| Metric | Value |
|---|---|
| p50/p95/max | mean=6.68s · median=6.51s · p95=9.92s · max=18.13s |

## Errors
| Metric | Value |
|---|---|
| eval errors | 0 |

## Judge calibration (answer_correctness vs human)
| Metric | Value |
|---|---|
| labeled n | 34 |
| judge↔human accuracy | 79.4% |
| Cohen's κ | -0.11 |
| confusion (tp/tn/fp/fn) | 27/0/4/3 |

## Retrieval misses (8 items)

Gold `doc_id` not in top-K — these point at chunking/embedding issues.

| id | gold_doc_id | question |
|---|---|---|
| in-002 | (gold not retrieved) | מסיימי שירות לאומי שנתיים מה מקבלים הטבות שירשמו לימודים? |
| in-003 | (gold not retrieved) | מה זה אכשרה? כמה ימים זה? |
| in-005 | (gold not retrieved) | אבא שלי חולה בדימציה אם הןא זכאי לתג נכה או קרוב משפחתו המסייע לחולה? |
| in-008 | (gold not retrieved) | האם בן בת זוג של משרתי מילואים נחשבים גם ידוע/ה בציבור? |
| in-016 | (gold not retrieved) | חיילים צריכים להזמין תור להוציא דרכון? |
| in-026 | (gold not retrieved) | איפה הקלפי שלי ? |
| in-028 | (gold not retrieved) | איך אפשר לודע אם יש למתוך רישיון |
| in-040 | (gold not retrieved) | איך מקבלים מהקופת חולים תור מיידי לפסיכולוג |
