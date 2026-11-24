"""Unit tests for the scoring engine. Expected values are worked out by hand in the comments."""
import pytest

from privascore.flags import load_flags
from privascore.scoring import (EXPOSURE_RISK, PROTECTIVE_RISK, kendall_tau, ranking_stability, round_half_up,
                                score, weight_sensitivity)

FLAGS = load_flags().flags
IDS = [f.id for f in FLAGS]
EXPOSURE = [f.id for f in FLAGS if f.type == "exposure"]
PROTECTIVE = [f.id for f in FLAGS if f.type != "exposure" and f.weight > 0]


def all_state(st, **over):
    d = {i: st for i in IDS}
    d.update(over)
    return d


def test_flag_set_matches_schema():
    # 16 flags, weights unchanged from the draft schema; 29 risk points over the 15 scored flags
    assert len(FLAGS) == 16
    assert sum(f.weight for f in FLAGS) == 29
    assert set(EXPOSURE) == {"G1", "G2", "G3", "G6", "AI1", "AI3", "AI4", "AI5"}
    assert {f.id for f in FLAGS if f.weight == 0} == {"DPDP4"}


def test_worst_case_is_100():
    # every exposure practice explicitly disclosed, every protection explicitly denied
    st = {i: ("ED" if i in EXPOSURE else "EE") for i in IDS}
    st["AI1"] = "ED"          # keeps AI2 applicable
    r = score(st, FLAGS)
    assert r.risk_index == 100.0
    assert r.disclosure_quality == 100.0     # everything addressed explicitly
    assert r.n_applicable == 15              # DPDP4 informational


def test_best_case_is_0_with_full_quality():
    # no exposure practices, every protection present; AI1=EE makes AI2 not applicable
    st = {i: ("EE" if i in EXPOSURE else "ED") for i in IDS}
    r = score(st, FLAGS)
    assert r.risk_index == 0.0
    assert r.disclosure_quality == 100.0
    assert r.n_applicable == 14              # AI2 and DPDP4 excluded


def test_silent_policy_scores_zero_risk_and_zero_quality():
    r = score(all_state("NS"), FLAGS)
    assert r.risk_index == 0.0
    assert r.disclosure_quality == 0.0
    assert r.n_not_stated == 14              # AI2 excluded because AI1 is NS


def test_all_unclear_is_half_risk_and_quarter_quality():
    # AI1=UN -> AI2 not applicable; every remaining flag contributes 0.5*w; quality 0.5/2
    r = score(all_state("UN"), FLAGS)
    assert r.risk_index == pytest.approx(50.0)
    assert r.disclosure_quality == pytest.approx(25.0)


def test_hand_computed_mixed_policy():
    st = all_state("NS", G1="ED", G2="CD", G4="CD", G5="ED", AI1="CD", AI2="ED", DPDP1="EE", DPDP3="CD", DPDP4="ED")
    # risk: G1 1*1 + G2 .5*3 + G4 .5*2 + G5 0 + AI1 .5*3 + AI2 0 + DPDP1 1*2 + DPDP3 .5*1 = 7.5
    # max risk: all 15 scored flags applicable (AI1=CD) = 29
    # quality: G1 2 + G2 1.5 + G4 1.5 + G5 2 + AI1 1.5 + AI2 2 + DPDP1 2 + DPDP3 1.5 = 14 of 30
    r = score(st, FLAGS)
    assert r.risk_points == pytest.approx(7.5)
    assert r.max_risk_points == 29
    assert r.risk_index == pytest.approx(100 * 7.5 / 29)          # 25.86
    assert r.risk_index_display == 26
    assert r.disclosure_quality == pytest.approx(100 * 14 / 30)   # 46.67
    assert r.disclosure_quality_display == 47


def test_ai2_excluded_when_ai1_not_training():
    base = all_state("NS", AI1="EE", AI2="EE", G1="ED")
    r = score(base, FLAGS)
    ai2 = next(f for f in r.per_flag if f.flag == "AI2")
    assert not ai2.applicable and "AI1=EE" in ai2.reason
    assert r.max_risk_points == 29 - 2                 # AI2 weight removed from the denominator
    assert r.risk_points == pytest.approx(1.0)         # only G1; AI2's EE is ignored


def test_ai2_applicable_when_ai1_trains():
    r = score(all_state("NS", AI1="ED", AI2="EE"), FLAGS)
    ai2 = next(f for f in r.per_flag if f.flag == "AI2")
    assert ai2.applicable and ai2.risk_points == 2.0   # opt-out explicitly denied
    assert r.risk_points == pytest.approx(3.0 + 2.0)   # AI1 ED*3 + AI2 EE*2


def test_dpdp4_never_affects_scores():
    a = score(all_state("CD", DPDP4="NS"), FLAGS)
    b = score(all_state("CD", DPDP4="ED"), FLAGS)
    assert a.risk_index == b.risk_index and a.disclosure_quality == b.disclosure_quality


@pytest.mark.parametrize("flag", IDS)
def test_ns_never_adds_risk(flag):
    # switching any single flag from CD to NS can only lower (never raise) the risk points
    base = {} if flag == "AI1" else {"AI1": "CD"}   # AI1=CD keeps AI2 applicable
    with_cd = score(all_state("NS", **{**base, flag: "CD"}), FLAGS).risk_points
    with_ns = score(all_state("NS", **{**base, flag: "NS"}), FLAGS).risk_points
    assert with_ns <= with_cd
    assert EXPOSURE_RISK["NS"] == PROTECTIVE_RISK["NS"] == 0


@pytest.mark.parametrize("flag", ["G2", "AI1", "G3", "AI5"])
def test_exposure_monotone(flag):
    # more exposure must never lower the risk: EE <= CD <= ED
    vals = [score(all_state("NS", **{flag: s}), FLAGS).risk_index for s in ("EE", "CD", "ED")]
    assert vals[0] <= vals[1] <= vals[2] and vals[0] < vals[2]


@pytest.mark.parametrize("flag", ["G4", "G5", "G7", "DPDP1", "DPDP2", "DPDP3"])
def test_protective_monotone(flag):
    # weaker protection must never lower the risk: ED <= CD <= EE
    vals = [score(all_state("NS", **{flag: s}), FLAGS).risk_index for s in ("ED", "CD", "EE")]
    assert vals[0] <= vals[1] <= vals[2] and vals[0] < vals[2]


def test_scores_bounded():
    import itertools, random
    rng = random.Random(0)
    for _ in range(500):
        st = {i: rng.choice(["ED", "CD", "EE", "NS", "UN"]) for i in IDS}
        r = score(st, FLAGS)
        assert 0 <= r.risk_index <= 100 and 0 <= r.disclosure_quality <= 100


def test_input_validation():
    with pytest.raises(ValueError, match="missing"):
        score({"G1": "ED"}, FLAGS)
    with pytest.raises(ValueError, match="invalid"):
        score(all_state("NS", G1="YES"), FLAGS)


def test_round_half_up():
    assert round(42.5) == 42                     # why we don't use round()
    assert round_half_up(42.5) == 43 and round_half_up(42.49) == 42 and round_half_up(0) == 0


def test_weight_sensitivity_brackets_base():
    st = all_state("CD", AI1="ED", G2="ED", DPDP1="EE")
    s = weight_sensitivity(st, FLAGS)
    assert s["min"] <= s["base"] <= s["max"]
    assert len(s["variants"]) == 2 * 15
    assert 0 <= s["equal_weights"] <= 100


def test_kendall_tau():
    assert kendall_tau([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert kendall_tau([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)
    assert kendall_tau([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(4 / 6)


def test_ranking_stability_identical_policies_rank_unchanged():
    pols = {"A": all_state("ED"), "B": all_state("CD"), "C": all_state("NS", G2="ED")}
    out = ranking_stability(pols, FLAGS)
    assert out["policies"] == ["A", "B", "C"]
    assert -1 <= out["min_tau"] <= 1
