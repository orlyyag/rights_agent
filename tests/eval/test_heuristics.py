from eval.metrics import heuristics as h


def test_hit_at_k_set_and_scalar():
    assert h.hit_at_k(["a", "b", "c"], {"c"}, 5) is True
    assert h.hit_at_k(["a", "b", "c"], "c", 2) is False        # c is rank 3
    assert h.hit_at_k(["a", "b"], {"x", "b"}, 5) is True        # any gold in set


def test_recall_at_k():
    assert h.recall_at_k(["a", "b", "c"], {"a", "x"}, 5) == 0.5  # 1 of 2 golds found
    assert h.recall_at_k(["a"], set(), 5) == 0.0


def test_mrr():
    assert h.mrr(["a", "b", "c"], {"b"}) == 0.5                 # first gold at rank 2
    assert h.mrr(["a", "b"], {"z"}) == 0.0


def test_context_precision_at_k():
    assert h.context_precision_at_k([True, False, True], 3) == 2 / 3
    assert h.context_precision_at_k([], 3) == 0.0


def test_citation_present_and_valid():
    urls = ["https://www.kolzchut.org.il/he/דמי_אבטלה", "https://example.com/x"]
    assert h.citation_present(urls) is True
    assert h.citation_present([]) is False
    assert h.citation_valid(urls) == 0.5                         # 1 of 2 are KZ /he/ links


def test_language_match_hebrew():
    assert h.language_match("זוהי תשובה בעברית עם מספר 5", "he") is True
    assert h.language_match("This is English only", "he") is False
    assert h.language_match("עברית רובה עברית עם מילה אחת RAG", "he") is True  # majority he


def test_refusal_kind():
    assert h.refusal_kind(refused=False, hit=False) == "answered"
    assert h.refusal_kind(refused=True, hit=True) == "false_refusal"
    assert h.refusal_kind(refused=True, hit=False) == "justified_refusal"
