# Kol Zchut Rights Assistant — Project Overview

> **In one line:** Your rights in Israel, answered in your own language — right inside Telegram.

A short, high-level summary for sharing. Full design lives in [PLAN.md](PLAN.md); the
graded write-up is in [REPORT.md](REPORT.md).

---

## The problem

Every year, Israelis miss out on money and support they're legally entitled to —
unemployment pay, disability allowances, housing aid, pensions — because the rules are
buried in dense, Hebrew-first government material. For the **~1M+ Russian speakers** and
for elderly citizens, the language barrier turns "available" into "invisible."

There's a trusted source for all of this — **Kol Zchut**, a well-known Israeli rights
encyclopedia — but you have to know how to navigate it, and mostly in Hebrew.

## What we built

A **Telegram chatbot** that answers rights questions in plain **Hebrew or Russian**.
You ask a question the way you'd ask a friend — *"I just had a baby, what am I entitled
to?"* — and it replies with a clear answer, **in your language**, and **links to the
official Kol Zchut page** it's based on.

Three principles keep it trustworthy:

- **Grounded** — it only answers from real Kol Zchut content, never made-up.
- **Cited** — every answer shows its source so the user can verify.
- **Honest** — if the answer isn't in the source, it says so instead of guessing.
- It's **information, not legal advice**, and every answer says so.

## How it works (the short version)

```
  User asks in Telegram  →  the assistant finds the right Kol Zchut pages
  →  reads them  →  writes a grounded answer in the user's language  →  with sources
```

A few things happen behind the scenes that make it more than a simple search:

- It **understands the question** even in everyday wording, and remembers the last few
  messages so follow-ups ("...and for freelancers?") work.
- It **double-checks itself** — if the first set of pages looks weak, it tries again with
  better search terms before answering, and refuses if nothing good is found.
- It **stays fresh** — an automated job notices when Kol Zchut pages change and updates
  the assistant's knowledge, with no downtime.

## What makes it stand out

- **Bilingual by design**, with **first-class Russian** — not a Hebrew-only tool with
  translation bolted on.
- Meets people **where they already are** (Telegram), no new app or website to learn.
- A **self-checking agent**, not a one-shot lookup — it grades its own results and
  retries before it answers.
- Built on **openly-licensed** Kol Zchut content, always **credited and linked back**.

## How we know it works

We measure quality on a **human-verified question set** in both languages — checking that
answers are correct, grounded, in the right language, and that the bot **refuses correctly**
when a question is out of scope. Target: **90%+** of demo questions answered correctly,
with sources.

## Status & timeline

- **Course:** Gen AI development program (Google × Reichman University) — final project.
- **Team:** 2 people. **Target demo date:** Saturday, **June 13, 2026**.
- A working bilingual demo runs **locally**, reachable from a few paired phones — no cloud
  setup needed for the demo.

## What's next (beyond the course)

WhatsApp as a second channel · Arabic (Kol Zchut's third language) · voice questions for
accessibility · broader Russian coverage.

---

*Built on Kol Zchut (© Kol Zchut, CC BY-NC-SA) — content is attributed and linked on
every answer.*
