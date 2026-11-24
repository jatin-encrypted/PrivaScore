"""
evaluate_app350_external.py - APP-350 external generalization test for the
OPP-115-trained classifiers. First Party / Third Party ONLY.

FAIRNESS RULES (all enforced or checked here)
  1. BERT: existing seed 42/43/44 checkpoints, NOT retrained (probabilities come
     from predict_bert_external.py, run separately on the GPU machine).
  2. TF-IDF: vectorizer and classifier fit on OPP-115 TRAIN only, original
     baseline configuration. Regression-checked: must reproduce 0.7273 on the
     OPP-115 test split before it is used here.
  3. Fixed 0.5 threshold for every system. No tuning on APP-350.
  4. Only the two mapped categories are scored. No 10-class APP-350 score exists.
  5. Evaluation set = 52 non-synthetic held-out APP-350 test policies (built and
     verified by build_app350_eval_set.py; sha256 of the file is checked against
     the BERT probability metadata so row order can't silently differ).
  6. Unannotated segments are excluded, never negatives. Within an annotated
     segment, a category is negative iff no practice of that party is annotated.
     RECALL needs no negatives (assumption-free); PRECISION and F1 rely on that
     within-segment assumption.

CAVEATS TO CARRY INTO ANY WRITE-UP
  * Operational mapping, not equivalence: APP-350 "third party" = ad/analytics
    SDKs only, narrower than OPP-115 Third Party, so Third Party precision is a
    lower bound.
  * The evaluated population is annotated segments only, where 84% are First
    Party positives. The all-positive rows show what a classifier that says
    "yes" to everything would score.

USAGE
  python evaluate_app350_external.py --eval-dir ext --bert-dir bert_external --outputs-dir data/opp115
  (omit --bert-dir, or pass a folder without the files, to get TF-IDF only)
"""
import argparse
import hashlib
import json
from collections import OrderedDict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.multiclass import OneVsRestClassifier

CATS = ["First Party Collection/Use", "Third Party Sharing/Collection"]  # label ids 0 and 1
OPP_BASELINE_TEST_F1 = 0.7273


def prf(y, p):
    tp = int(((y == 1) & (p == 1)).sum()); fp = int(((y == 0) & (p == 1)).sum())
    fn = int(((y == 1) & (p == 0)).sum()); tn = int(((y == 0) & (p == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def score(Y, P):
    """Y, P: (n, 2) binary arrays -> per-category metrics and macro over the 2 categories."""
    per = {c: prf(Y[:, j], P[:, j]) for j, c in enumerate(CATS)}
    return {"per_category": per, "macro_f1": float(np.mean([per[c]["f1"] for c in CATS])),
            "macro_precision": float(np.mean([per[c]["precision"] for c in CATS])),
            "macro_recall": float(np.mean([per[c]["recall"] for c in CATS]))}


def policy_counts(Y, P, pol_idx, n_pol):
    """-> (n_pol, 2 cats, 4) counts of TP, FP, FN, TN"""
    out = np.zeros((n_pol, 2, 4))
    for p in range(n_pol):
        m = pol_idx == p
        y, q = Y[m], P[m]
        out[p, :, 0] = ((y == 1) & (q == 1)).sum(0); out[p, :, 1] = ((y == 0) & (q == 1)).sum(0)
        out[p, :, 2] = ((y == 1) & (q == 0)).sum(0); out[p, :, 3] = ((y == 0) & (q == 0)).sum(0)
    return out


def f1_from_counts(c):
    tp, fp, fn = c[..., 0], c[..., 1], c[..., 2]
    d = 2 * tp + fp + fn
    return np.where(d > 0, 2 * tp / np.maximum(d, 1), 0.0)


def ci(x):
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-dir", type=Path, default=Path("ext"))
    ap.add_argument("--bert-dir", type=Path, default=None)
    ap.add_argument("--outputs-dir", type=Path, default=Path("data/opp115"))
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--n-boot", type=int, default=20000)
    ap.add_argument("--out-prefix", type=Path, default=Path("app350_external"))
    args = ap.parse_args()

    # ---------------- evaluation set
    eval_path = args.eval_dir / "app350_external_eval.jsonl"
    rows = [json.loads(l) for l in eval_path.read_text().splitlines() if l.strip()]
    sha = hashlib.sha256(eval_path.read_bytes()).hexdigest()
    Y = np.array([[r["y_first"], r["y_third"]] for r in rows], dtype=int)
    texts = [r["text"] for r in rows]
    pol_ids = list(dict.fromkeys(r["policy_id"] for r in rows))
    pol_idx = np.array([pol_ids.index(r["policy_id"]) for r in rows])
    n_pol = len(pol_ids)

    print("=" * 78)
    print("EVALUATION SET (APP-350, held-out, non-synthetic, annotated segments only)")
    print("=" * 78)
    print(f"policies with >=1 evaluable segment : {n_pol} (of 52 held-out test policies)")
    print(f"segments evaluated                  : {len(rows)}")
    for j, c in enumerate(CATS):
        print(f"  {c:<34} positives {int(Y[:, j].sum()):>4}   negatives {int((1 - Y[:, j]).sum()):>4}   "
              f"prevalence {Y[:, j].mean():.1%}")
    print(f"  both categories positive           : {int(((Y[:, 0] == 1) & (Y[:, 1] == 1)).sum())}")
    print(f"eval-set sha256: {sha[:16]}...")

    # ---------------- TF-IDF: OPP-115 train ONLY, original configuration
    opp = {s: [json.loads(l) for l in (args.outputs_dir / f"opp115_{s}.jsonl").read_text().splitlines() if l.strip()]
           for s in ("train", "test")}
    Xtr_t = [r["text"] for r in opp["train"]]
    ytr = np.array([r["labels"] for r in opp["train"]], dtype=int)
    vec = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words="english", min_df=2)
    Xtr = vec.fit_transform(Xtr_t)  # fit on OPP-115 TRAIN text only
    clf = OneVsRestClassifier(LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)).fit(Xtr, ytr)

    # regression check: reproduces the frozen baseline on the OPP-115 test split
    opp_test_pred = clf.predict(vec.transform([r["text"] for r in opp["test"]]))
    opp_test_f1 = f1_score(np.array([r["labels"] for r in opp["test"]]), opp_test_pred, average="macro", zero_division=0)
    assert abs(opp_test_f1 - OPP_BASELINE_TEST_F1) < 5e-4, f"TF-IDF regression failed: {opp_test_f1:.4f}"
    print(f"\nTF-IDF regression check on OPP-115 test: macro F1 = {opp_test_f1:.4f} (frozen baseline {OPP_BASELINE_TEST_F1}) OK")

    tfidf_proba = clf.predict_proba(vec.transform(texts))[:, :2]
    systems = OrderedDict()
    probs = OrderedDict()
    systems["TF-IDF (OPP-115 only)"] = (tfidf_proba >= 0.5).astype(int)
    probs["TF-IDF (OPP-115 only)"] = tfidf_proba
    np.save(f"{args.out_prefix}_tfidf_probs.npy", tfidf_proba)

    # ---------------- BERT probabilities (optional, produced on the GPU machine)
    seeds = [int(s) for s in args.seeds.split(",")]
    bert_available = False
    bert_meta = None
    if args.bert_dir and all((args.bert_dir / f"bert_external_probs_seed_{s}.npy").exists() for s in seeds):
        bert_meta = json.loads((args.bert_dir / "bert_external_meta.json").read_text())
        assert bert_meta["eval_set_sha256"] == sha, "BERT probabilities were made for a different eval-set file/order"
        for s in seeds:
            p = np.load(args.bert_dir / f"bert_external_probs_seed_{s}.npy")
            assert p.shape[0] == len(rows), (p.shape, len(rows))
            systems[f"BERT seed {s}"] = (p[:, :2] >= 0.5).astype(int)  # columns 0,1 only; other 8 outputs ignored
            probs[f"BERT seed {s}"] = p[:, :2]
        bert_available = True
        print(f"BERT probabilities loaded for seeds {seeds}; eval-set sha256 matches. "
              f"OPP-115 sanity (stored vs rescored test macro F1): {bert_meta.get('opp115_sanity')}")
    else:
        print("\n[BERT probabilities not found: reporting TF-IDF only. Run predict_bert_external.py on the GPU machine.]")

    # reference: predict-everything-positive (shows the floor implied by prevalence)
    ref = np.ones_like(Y)

    results = {"eval_set_sha256": sha, "n_policies": n_pol, "n_segments": len(rows),
               "positives": {c: int(Y[:, j].sum()) for j, c in enumerate(CATS)},
               "negatives": {c: int((1 - Y[:, j]).sum()) for j, c in enumerate(CATS)},
               "threshold": 0.5, "systems": {}, "reference_all_positive": score(Y, ref),
               "tfidf_opp115_regression_f1": float(opp_test_f1)}
    for name, P in systems.items():
        results["systems"][name] = score(Y, P)
        results["systems"][name]["threshold_free"] = {
            c: {"roc_auc": float(roc_auc_score(Y[:, j], probs[name][:, j])),
                "average_precision": float(average_precision_score(Y[:, j], probs[name][:, j]))}
            for j, c in enumerate(CATS)}

    if bert_available:
        mean_per = {}
        for c in CATS:
            mean_per[c] = {m: float(np.mean([results["systems"][f"BERT seed {s}"]["per_category"][c][m] for s in seeds]))
                           for m in ("precision", "recall", "f1")}
        results["bert_mean_of_seeds"] = {
            "per_category": mean_per,
            "macro_f1": float(np.mean([results["systems"][f"BERT seed {s}"]["macro_f1"] for s in seeds])),
            "macro_f1_std_sample": float(np.std([results["systems"][f"BERT seed {s}"]["macro_f1"] for s in seeds], ddof=1)),
        }

    # ---------------- report tables
    def row(label, m):
        a, b = m["per_category"][CATS[0]], m["per_category"][CATS[1]]
        return (f"{label:<26}| {a['precision']:.3f} {a['recall']:.3f} {a['f1']:.3f} "
                f"| {b['precision']:.3f} {b['recall']:.3f} {b['f1']:.3f} | {m['macro_f1']:.4f}")

    print("\n" + "=" * 78)
    print("RESULTS @ threshold 0.5   (P = precision, R = recall)")
    print("=" * 78)
    print(f"{'':<26}| First Party P  R  F1   | Third Party P  R  F1   | Macro F1 (2 cats)")
    print("-" * 78)
    for name in systems:
        print(row(name, results["systems"][name]))
    if bert_available:
        bm = results["bert_mean_of_seeds"]
        a, b = bm["per_category"][CATS[0]], bm["per_category"][CATS[1]]
        print(f"{'BERT mean of 3 seeds':<26}| {a['precision']:.3f} {a['recall']:.3f} {a['f1']:.3f} "
              f"| {b['precision']:.3f} {b['recall']:.3f} {b['f1']:.3f} | {bm['macro_f1']:.4f} (sample std {bm['macro_f1_std_sample']:.4f})")
    print("-" * 78)
    print(row("reference: all-positive", results["reference_all_positive"]) +
          "   <- floor implied by prevalence, not a model")

    print("\nTHRESHOLD-FREE DIAGNOSTIC (no threshold involved; ranking quality of the raw probabilities)")
    print(f"{'':<26}| First Party AUC  AP    | Third Party AUC  AP")
    for name in systems:
        t = results["systems"][name]["threshold_free"]
        print(f"{name:<26}|        {t[CATS[0]]['roc_auc']:.3f}  {t[CATS[0]]['average_precision']:.3f} "
              f"|        {t[CATS[1]]['roc_auc']:.3f}  {t[CATS[1]]['average_precision']:.3f}")
    if bert_available:
        mt = {c: {k: float(np.mean([results["systems"][f"BERT seed {s}"]["threshold_free"][c][k] for s in seeds]))
                  for k in ("roc_auc", "average_precision")} for c in CATS}
        results["bert_mean_of_seeds"]["threshold_free"] = mt
        print(f"{'BERT mean of 3 seeds':<26}|        {mt[CATS[0]]['roc_auc']:.3f}  {mt[CATS[0]]['average_precision']:.3f} "
              f"|        {mt[CATS[1]]['roc_auc']:.3f}  {mt[CATS[1]]['average_precision']:.3f}")
    print(f"{'chance (AUC 0.5 / AP = prevalence)':<26}|        0.500  {Y[:, 0].mean():.3f} |        0.500  {Y[:, 1].mean():.3f}")

    print("\nconfusion counts (TP / FP / FN / TN)")
    for name in systems:
        for c in CATS:
            m = results["systems"][name]["per_category"][c]
            print(f"  {name:<24}{c:<34}{m['tp']:>4} / {m['fp']:>4} / {m['fn']:>4} / {m['tn']:>4}")

    # ---------------- paired bootstrap over policies (BERT vs TF-IDF)
    if bert_available:
        rng = np.random.default_rng(0)
        draws = rng.multinomial(n_pol, np.full(n_pol, 1 / n_pol), size=args.n_boot)
        C = {name: policy_counts(Y, P, pol_idx, n_pol) for name, P in systems.items()}
        boot = {name: f1_from_counts(np.einsum("bp,pcj->bcj", draws, c)) for name, c in C.items()}  # (B, 2)
        bert_f1 = np.mean([boot[f"BERT seed {s}"] for s in seeds], axis=0)          # mean of seeds, per category
        tf_f1 = boot["TF-IDF (OPP-115 only)"]
        print("\n" + "=" * 78)
        print(f"PAIRED POLICY BOOTSTRAP ({args.n_boot} draws over {n_pol} policies), BERT mean-of-seeds minus TF-IDF")
        print("=" * 78)
        print(f"{'':<34}{'point':>9}{'95% CI':>22}{'P(delta>0)':>12}")
        boot_res = {}
        for j, c in enumerate(CATS):
            d = bert_f1[:, j] - tf_f1[:, j]
            point = results["bert_mean_of_seeds"]["per_category"][c]["f1"] - results["systems"]["TF-IDF (OPP-115 only)"]["per_category"][c]["f1"]
            lo, hi = ci(d)
            print(f"{c + ' F1':<34}{point:>+9.4f}   [{lo:+.4f}, {hi:+.4f}]{(d > 0).mean():>12.3f}")
            boot_res[c] = {"point": point, "ci95": [lo, hi], "p_gt0": float((d > 0).mean())}
        d = bert_f1.mean(1) - tf_f1.mean(1)
        point = results["bert_mean_of_seeds"]["macro_f1"] - results["systems"]["TF-IDF (OPP-115 only)"]["macro_f1"]
        lo, hi = ci(d)
        print(f"{'Macro F1 (2 categories)':<34}{point:>+9.4f}   [{lo:+.4f}, {hi:+.4f}]{(d > 0).mean():>12.3f}")
        boot_res["macro_f1_2cat"] = {"point": point, "ci95": [lo, hi], "p_gt0": float((d > 0).mean())}
        for s in seeds:
            ds = boot[f"BERT seed {s}"].mean(1) - tf_f1.mean(1)
            lo, hi = ci(ds)
            pt = results["systems"][f"BERT seed {s}"]["macro_f1"] - results["systems"]["TF-IDF (OPP-115 only)"]["macro_f1"]
            print(f"{'  seed ' + str(s) + ' macro F1':<34}{pt:>+9.4f}   [{lo:+.4f}, {hi:+.4f}]{(ds > 0).mean():>12.3f}")
            boot_res[f"seed_{s}_macro"] = {"point": pt, "ci95": [lo, hi], "p_gt0": float((ds > 0).mean())}
        results["paired_bootstrap"] = boot_res
        seg = np.bincount(pol_idx)
        print(f"\npolicy concentration: largest policy = {seg.max()} of {len(rows)} segments ({seg.max() / len(rows):.1%})")

    out_json = Path(f"{args.out_prefix}_results.json")
    out_json.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out_json}")


if __name__ == "__main__":
    main()
