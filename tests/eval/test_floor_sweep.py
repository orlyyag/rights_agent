from scripts.calibrate_floor import best_floor


def test_best_floor_separates_inscope_from_adversarial():
    # in-scope gold scores (want to KEEP) vs adversarial top-1 (want to CUT)
    inscope = [0.42, 0.48, 0.55, 0.30, 0.61]
    adversarial = [0.20, 0.25, 0.28, 0.22]
    floor = best_floor(inscope, adversarial, candidates=[0.25, 0.30, 0.35, 0.40])
    # 0.30 keeps 4/5 in-scope and cuts all adversarial; 0.35 cuts an extra in-scope
    assert floor == 0.30
