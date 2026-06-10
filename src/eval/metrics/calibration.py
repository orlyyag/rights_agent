"""Judge↔human agreement: Cohen's κ, accuracy, confusion. Pure functions."""
from __future__ import annotations


def cohen_kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0 or n != len(b):
        return 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1 = sum(a) / n
    pb1 = sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def calibration_report(human: dict[str, int], judge: dict[str, float],
                       *, threshold: float = 0.5) -> dict:
    ids = [i for i in human if i in judge]
    h = [int(human[i]) for i in ids]
    j = [1 if judge[i] >= threshold else 0 for i in ids]
    n = len(ids)
    acc = sum(1 for x, y in zip(h, j) if x == y) / n if n else 0.0
    tp = sum(1 for x, y in zip(h, j) if x == 1 and y == 1)
    tn = sum(1 for x, y in zip(h, j) if x == 0 and y == 0)
    fp = sum(1 for x, y in zip(h, j) if x == 0 and y == 1)
    fn = sum(1 for x, y in zip(h, j) if x == 1 and y == 0)
    return {
        "n": n,
        "accuracy": acc,
        "kappa": cohen_kappa(h, j),
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }
