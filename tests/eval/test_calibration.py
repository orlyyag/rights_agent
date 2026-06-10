from eval.metrics import calibration as cal


def test_cohen_kappa_perfect():
    assert cal.cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0


def test_cohen_kappa_chance():
    # half agreement by chance → kappa near 0
    k = cal.cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0])
    assert abs(k) < 1e-9


def test_calibration_report():
    human = {"a": 1, "b": 0, "c": 1, "d": 0}
    judge = {"a": 0.9, "b": 0.1, "c": 0.2, "d": 0.4}  # c is judge-wrong at thr 0.5
    rep = cal.calibration_report(human, judge, threshold=0.5)
    assert rep["n"] == 4
    assert rep["accuracy"] == 0.75
    assert "kappa" in rep and "confusion" in rep
