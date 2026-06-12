"""ANN-vs-true-NN recall gate for blue-green flips (the kz_v2 incident).

2026-06-11: a freshly built collection shipped with query-dependent HNSW recall
holes — for one golden query the true nearest neighbors (cosine-dist 0.2365)
were never surfaced and ~0.33 neighbors came back instead. Self-NN probes pass
on such a graph, so the only honest check is brute force: pull every stored
embedding, compute the true top-k for real query vectors, and require the ANN
result to match within epsilon. See eval/failure_analysis.txt,
"V2 RE-RUN FLIP ANALYSIS".

Cost: one full-embedding scan (~1.3 GB RAM at 104k × 3072-dim float32) plus
k ANN queries — seconds, run once per sync, before the pointer flip.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Material-hole threshold. ANN is approximate by nature: near-duplicate chunks
# hide behind each other and one of them may be skipped (observed gap ~0.007 on
# kz_v3 — the gold chunk itself was still returned). The incident this gate
# exists for had a 0.094 gap with the entire true neighborhood missing. 0.01
# sits an order of magnitude above ANN noise and well below any score
# difference that changes which documents reach the generator.
_EPS = 1e-2
_PAGE = 2000


@dataclass
class RecallReport:
    """Per-gate summary; ``failed`` holds (query_idx, true_top1, ann_top1, max_gap)."""

    queries: int = 0
    failed: list[tuple[int, float, float, float]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.queries > 0 and not self.failed


def _all_embeddings(col):
    import numpy as np

    mats = []
    offset = 0
    while True:
        page = col.get(limit=_PAGE, offset=offset, include=["embeddings"])
        ids = page.get("ids") or []
        if not len(ids):
            break
        offset += len(ids)
        mats.append(np.asarray(page["embeddings"], dtype=np.float32))
    if not mats:
        raise ValueError("collection has no embeddings")
    return np.vstack(mats)


def check(col, query_vectors, *, k: int = 5, eps: float = _EPS) -> RecallReport:
    """Compare ANN top-k distances against brute-force truth for each query.

    A query fails if any of its ANN top-k distances is worse than the true
    k-th distance by more than ``eps`` (ties are fine — we compare sorted
    distance lists, not ids, so equidistant chunks can swap freely).
    """
    import numpy as np

    mat = _all_embeddings(col)
    mat = mat / np.linalg.norm(mat, axis=1, keepdims=True)

    rep = RecallReport(queries=len(query_vectors))
    for i, q in enumerate(query_vectors):
        qv = np.asarray(q, dtype=np.float32)
        qv = qv / np.linalg.norm(qv)
        true_d = np.sort(1.0 - mat @ qv)[:k]
        res = col.query(query_embeddings=[[float(x) for x in q]], n_results=k,
                        include=["distances"])
        ann_d = sorted(float(d) for d in res["distances"][0])
        short = len(ann_d) < min(k, len(true_d))
        gaps = [a - t for a, t in zip(ann_d, true_d)]
        if short or any(g > eps for g in gaps):
            rep.failed.append((i, float(true_d[0]),
                               ann_d[0] if ann_d else float("inf"),
                               max(gaps) if gaps else float("inf")))
    return rep
