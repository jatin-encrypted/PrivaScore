"""Evaluation script tests on synthetic gold labels and a synthetic run."""
import json

import pytest

from privascore.evaluate import evaluate, to_markdown, wilson
from privascore.flags import load_flags

FLAGS = [f.id for f in load_flags().flags]


def write_case(tmp_path, gold_states, pred_states, pred_status=None, gold_ids=None, pred_ids=None):
    labels = []
    for pid, st in gold_states.items():
        for f, s in st.items():
            labels.append({"policy_id": pid, "flag": f, "state": s, "snapshot_text_sha256": f"sha-{pid}",
                           "evidence": [{"id": i} for i in (gold_ids or {}).get((pid, f), [])], "related": []})
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"labels": labels}))
    run = tmp_path / "run"
    run.mkdir()
    for pid, st in pred_states.items():
        flags = {f: {"state": s, "status": (pred_status or {}).get((pid, f), "verified"),
                     "evidence": [{"id": i} for i in (pred_ids or {}).get((pid, f), [])]} for f, s in st.items()}
        for f, r in flags.items():
            if r["status"] == "rejected":
                r["state"] = None
        (run / f"{pid}_x.json").write_text(json.dumps({"policy_id": pid, "cohort": "ai", "text_sha256": f"sha-{pid}",
                                                       "flags": flags}))
    return run, gold


def full(state="CD", **over):
    d = {f: state for f in FLAGS}
    d.update(over)
    return d


def test_perfect_agreement(tmp_path):
    g = {"P01": full("CD"), "P02": full("NS", G2="ED", AI1="ED")}
    run, gold = write_case(tmp_path, g, g)
    r = evaluate(run, gold)
    assert r["state_accuracy"]["accuracy"] == 1.0 and r["presence_accuracy"]["accuracy"] == 1.0
    assert r["headline_pairs"] == 2 * 14          # G1 and DPDP4 excluded from the headline
    assert r["scores"]["risk_mad"] == 0 and r["scores"]["risk_rank_tau"] == pytest.approx(1.0)
    assert "State accuracy" in to_markdown(r)


def test_errors_false_not_stated_and_rejections(tmp_path):
    g = {"P01": full("CD")}
    p = {"P01": full("CD", G2="NS", G4="ED", AI3="CD")}
    run, gold = write_case(tmp_path, g, p, pred_status={("P01", "AI3"): "rejected"})
    r = evaluate(run, gold)
    assert r["state_accuracy"]["correct"] == 14 - 3
    assert r["false_not_stated"]["predicted_absent"] == 1          # G2
    assert r["rejected"] == 1                                      # AI3 counts as wrong
    assert r["confusion"]["CD"]["REJ"] == 1 and r["confusion"]["CD"]["ED"] == 1
    assert {d["flag"] for d in r["disagreements"]} == {"G2", "G4", "AI3"}


def test_evidence_overlap(tmp_path):
    g = {"P01": full("NS", G2="ED", G4="CD")}
    run, gold = write_case(tmp_path, g, g,
                           gold_ids={("P01", "G2"): ["p001.s1"], ("P01", "G4"): ["p005.s1"]},
                           pred_ids={("P01", "G2"): ["p001.s1", "p002.s1"], ("P01", "G4"): ["p009.s1"]})
    r = evaluate(run, gold)
    assert r["evidence_agreement"] == {"both_present": 2, "overlap": 1, "rate": 0.5}


def test_snapshot_mismatch_refused(tmp_path):
    run, gold = write_case(tmp_path, {"P01": full()}, {"P01": full()})
    f = next(run.glob("P01_*.json"))
    d = json.loads(f.read_text())
    d["text_sha256"] = "different"
    f.write_text(json.dumps(d))
    with pytest.raises(SystemExit, match="different snapshots"):
        evaluate(run, gold)


def test_partial_gold_only_scores_complete_policies(tmp_path):
    g = {"P01": {"G2": "ED", "G4": "CD"}}                    # labelling in progress
    run, gold = write_case(tmp_path, g, {"P01": full("CD", G2="ED")})
    r = evaluate(run, gold)
    assert r["evaluated_pairs"] == 2 and r["scores"]["policies"] == []


def test_wilson():
    lo, hi = wilson(12, 15)
    assert 0.5 < lo < 0.8 < hi < 1.0
    assert wilson(0, 0) == (None, None)


def test_repo_relative_hides_local_paths(tmp_path):
    from privascore.flags import REPO_ROOT, repo_relative
    assert repo_relative(REPO_ROOT / "gold_set" / "annotations" / "x.json") == "gold_set/annotations/x.json"
    assert repo_relative(tmp_path / "elsewhere.json") == str(tmp_path / "elsewhere.json")


def test_evaluate_records_repo_relative_gold_path():
    from privascore.evaluate import DEFAULT_GOLD
    from privascore.flags import repo_relative
    assert not repo_relative(DEFAULT_GOLD).startswith("/")
