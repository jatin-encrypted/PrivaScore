"""
paired_bootstrap_combined.py - did adding APP-350 (with masked loss) help BERT?

TWO PAIRED COMPARISONS, SAME UNIT OF RESAMPLING AS paired_bootstrap.py (the POLICY)
  A. OPP-115 test rows (582 segments, 18 policies), 10-class macro F1 @0.5
       combined-trained BERT (masked loss, 3 seeds)  vs  OPP-115-only BERT (3 seeds)
       and vs the OPP-115-only TF-IDF baseline (0.7273).
     This is the "did the extra data help / hurt where we already had data?" test.
  B. APP-350 test rows (662 segments, 51 policies), First/Third Party macro F1 @0.5
       combined-trained BERT  vs  OPP-115-only BERT run zero-shot (the earlier external test).
     Same 662 rows, same labels, same order as app350_external_eval.jsonl (asserted).
     This one is expected to favour the combined model - it has seen APP-350 training policies,
     the OPP-only model has not. It measures how much in-domain data buys, not generalisation.

WHAT THE CI COVERS: which test policies we happened to get (each draw resamples whole policies
with replacement and scores BOTH systems on the same draw). It does NOT cover training noise beyond
the 3 seeds per system - see the per-seed lines printed next to every comparison.

Reuses the vectorised count machinery from ../04_paired_bootstrap/paired_bootstrap.py.

--data-dir must contain opp115_label_map.json, opp115_train.jsonl, opp115_test.jsonl,
combined_test.jsonl and app350_external_eval.jsonl.

  python paired_bootstrap_combined.py --combined-dir bert_combined_runs \
      --opp-only-probs-dir probs --external-probs-dir bert_external --data-dir outputs
"""
import argparse
import importlib.util
import json
import warnings
from collections import OrderedDict
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location(
    "pb", Path(__file__).resolve().parent.parent / "04_paired_bootstrap" / "paired_bootstrap.py")
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)


def analyze(title, y, policies, names, preds, groups, comps, n_boot, rng_seed, show_policies=True):
    """preds: {system_key: binary (n, k) array}; groups: {group: [system_keys]} (mean over seeds);
    comps: [(group_a, group_b)] -> a minus b."""
    uniq = list(OrderedDict.fromkeys(policies))
    pol_idx = np.array([uniq.index(p) for p in policies])
    n_pol = len(uniq)
    seg_per_pol = np.bincount(pol_idx)
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    print(f"{len(y)} segments, {n_pol} policies (segments/policy min={seg_per_pol.min()} "
          f"median={int(np.median(seg_per_pol))} max={seg_per_pol.max()})")

    C = {k: pb.counts_by_policy(y, v, pol_idx, n_pol) for k, v in preds.items()}
    full = {k: float(pb.macro_f1_from_counts(c.sum(0))) for k, c in C.items()}
    print("full-test macro F1 per system:")
    for g, ks in groups.items():
        print(f"  {g:<22}" + "  ".join(f"{full[k]:.4f}" for k in ks)
              + (f"   mean {np.mean([full[k] for k in ks]):.4f}   std {np.std([full[k] for k in ks]):.4f}"
                 if len(ks) > 1 else ""))

    rng = np.random.default_rng(rng_seed)
    draws = rng.multinomial(n_pol, np.full(n_pol, 1 / n_pol), size=n_boot)
    boot = {k: pb.macro_f1_from_counts(np.einsum("bp,pcj->bcj", draws, c), False) for k, c in C.items()}
    gboot = {g: np.mean([boot[k] for k in ks], 0) for g, ks in groups.items()}
    gfull = {g: float(np.mean([full[k] for k in ks])) for g, ks in groups.items()}

    out = {"n_policies": n_pol, "n_segments": int(len(y)), "full": full, "group_mean": gfull, "comparisons": {}}
    print(f"\n{n_boot} paired policy-bootstrap draws, 95% percentile CI")
    print(f"{'comparison':<44}{'point':>9}{'95% CI':>20}{'P(delta>0)':>12}")
    for a, b in comps:
        d = gboot[a] - gboot[b]
        lo, hi = pb.ci(d)
        point = gfull[a] - gfull[b]
        print(f"{a + ' - ' + b:<44}{point:>+9.4f}   [{lo:+.4f}, {hi:+.4f}]{(d > 0).mean():>12.3f}")
        out["comparisons"][f"{a} - {b}"] = {"point": point, "ci95": [lo, hi], "p_gt0": float((d > 0).mean())}
    # each seed of the first group in each comparison vs the second group's mean
    for a, b in comps:
        for k in groups[a]:
            d = boot[k] - gboot[b]
            lo, hi = pb.ci(d)
            print(f"  {k + ' - ' + b + ' (mean)':<42}{full[k] - gfull[b]:>+9.4f}   [{lo:+.4f}, {hi:+.4f}]{(d > 0).mean():>12.3f}")

    # per-class F1 deltas for the first comparison
    a, b = comps[0]
    print(f"\nper-class F1 delta ({a} - {b}), bootstrap over policies")
    print(f"{'class':<40}{a[:8]:>9}{b[:8]:>9}{'delta':>8}{'95% CI':>20}{'P(>0)':>8}  support")
    cls = {}
    for j, n in enumerate(names):
        def cb(g):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return np.nanmean(np.stack([pb.per_class_f1(np.einsum("bp,pcj->bcj", draws, C[k]))[0][:, j]
                                            for k in groups[g]]), 0)
        d = cb(a) - cb(b)
        d = d[~np.isnan(d)]
        fa = np.mean([pb.per_class_f1(C[k].sum(0))[0][j] for k in groups[a]])
        fb = np.mean([pb.per_class_f1(C[k].sum(0))[0][j] for k in groups[b]])
        lo, hi = pb.ci(d)
        sup = int(y[:, j].sum())
        print(f"{n:<40}{fa:>9.3f}{fb:>9.3f}{fa - fb:>+8.3f}   [{lo:+.3f}, {hi:+.3f}]{(d > 0).mean():>8.2f}  {sup}")
        cls[n] = {"a": float(fa), "b": float(fb), "ci95": [lo, hi], "p_gt0": float((d > 0).mean()), "support": sup}
    out["per_class"] = cls

    # per-policy label errors (FP + FN), group a vs group b
    err = {g: np.mean([C[k][:, 1:, :].sum((1, 2)) for k in ks], 0) for g, ks in groups.items()}
    ea, eb = err[a], err[b]
    wins, ties, loss = int((ea < eb).sum()), int((ea == eb).sum()), int((ea > eb).sum())
    print(f"\nper-policy label errors (FP+FN): {a} has fewer in {wins} policies, tie in {ties}, "
          f"{b} has fewer in {loss} (of {n_pol})")
    out["per_policy"] = {"a_fewer": wins, "tie": ties, "b_fewer": loss}
    if show_policies:
        print(f"{'policy':<34}{'segs':>5}{a[:10] + ' err':>16}{b[:10] + ' err':>16}{'diff':>8}")
        for p in np.argsort(ea - eb):
            print(f"{uniq[p]:<34}{seg_per_pol[p]:>5}{ea[p]:>16.1f}{eb[p]:>16.1f}{ea[p] - eb[p]:>+8.1f}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combined-dir", type=Path, default=Path("bert_combined_runs"))
    ap.add_argument("--opp-only-probs-dir", type=Path, default=Path("probs"))
    ap.add_argument("--external-probs-dir", type=Path, default=Path("bert_external"))
    ap.add_argument("--data-dir", type=Path, default=Path("outputs"))
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--n-boot", type=int, default=20000)
    ap.add_argument("--rng", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("paired_bootstrap_combined_results.json"))
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]

    D = args.data_dir
    label_map = json.loads((D / "opp115_label_map.json").read_text())
    names = [label_map[str(i)] for i in range(10)]
    rd = lambda p: [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    opp_train, opp_test = rd(D / "opp115_train.jsonl"), rd(D / "opp115_test.jsonl")
    comb_test, ext = rd(D / "combined_test.jsonl"), rd(D / "app350_external_eval.jsonl")
    meta = rd(args.combined_dir / "test_meta.jsonl")

    # ---- alignment guards: every comparison below pairs rows by position
    assert len(meta) == len(comb_test) and all(
        m["policy_id"] == r["policy_id"] and m["source"] == r["source"] for m, r in zip(meta, comb_test)), \
        "test_meta.jsonl does not match combined_test.jsonl row order"
    src = np.array([r["source"] for r in comb_test])
    opp_idx, app_idx = np.where(src == "opp115")[0], np.where(src == "app350")[0]
    assert len(opp_idx) == len(opp_test) and all(
        comb_test[i]["text"] == o["text"] and comb_test[i]["policy_id"] == o["policy_id"]
        for i, o in zip(opp_idx, opp_test)), "combined OPP rows are not the OPP-115-only test rows"
    assert len(app_idx) == len(ext) and all(
        comb_test[i]["text"] == e["text"] and comb_test[i]["policy_id"] == e["policy_id"]
        and comb_test[i]["labels"][0] == e["y_first"] and comb_test[i]["labels"][1] == e["y_third"]
        for i, e in zip(app_idx, ext)), "combined APP rows are not the external-eval rows"
    print(f"alignment OK: {len(opp_idx)} OPP rows == opp115_test.jsonl; {len(app_idx)} APP rows == app350_external_eval.jsonl")

    results = {}

    # =========================== A. OPP-115 test rows ===========================
    y_opp = np.array([r["labels"] for r in opp_test], dtype=int)
    pol_opp = [r["policy_id"] for r in opp_test]
    preds = {}
    for s in seeds:
        pc = np.load(args.combined_dir / f"seed_{s}" / "test_probs.npy")
        assert pc.shape == (len(comb_test), 10)
        preds[f"comb_{s}"] = (pc[opp_idx] >= 0.5).astype(int)
        po = np.load(args.opp_only_probs_dir / f"seed_{s}" / "test_probs.npy")
        assert po.shape == y_opp.shape
        preds[f"oppOnly_{s}"] = (po >= 0.5).astype(int)
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.multiclass import OneVsRestClassifier
    vec = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words="english", min_df=2)
    Xtr = vec.fit_transform([r["text"] for r in opp_train])
    clf = OneVsRestClassifier(LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)).fit(
        Xtr, np.array([r["labels"] for r in opp_train], dtype=int))
    preds["tfidf"] = clf.predict(vec.transform([r["text"] for r in opp_test])).astype(int)
    groups = {"BERT-combined": [f"comb_{s}" for s in seeds],
              "BERT-OPP-only": [f"oppOnly_{s}" for s in seeds], "TF-IDF": ["tfidf"]}
    results["A_opp115"] = analyze(
        "A. OPP-115 TEST ROWS (10-class macro F1 @0.5): did APP-350 help where OPP-115 data already existed?",
        y_opp, pol_opp, names, preds, groups,
        [("BERT-combined", "BERT-OPP-only"), ("BERT-combined", "TF-IDF"), ("BERT-OPP-only", "TF-IDF")],
        args.n_boot, args.rng)

    # =========================== B. APP-350 test rows ===========================
    y_app = np.array([[e["y_first"], e["y_third"]] for e in ext], dtype=int)
    pol_app = [e["policy_id"] for e in ext]
    preds = {}
    for s in seeds:
        pc = np.load(args.combined_dir / f"seed_{s}" / "test_probs.npy")
        preds[f"comb_{s}"] = (pc[app_idx][:, :2] >= 0.5).astype(int)
        pe = np.load(args.external_probs_dir / f"bert_external_probs_seed_{s}.npy")
        assert pe.shape == (len(ext), 10)
        preds[f"oppOnly_{s}"] = (pe[:, :2] >= 0.5).astype(int)
    groups = {"BERT-combined": [f"comb_{s}" for s in seeds], "BERT-OPP-only(0-shot)": [f"oppOnly_{s}" for s in seeds]}
    results["B_app350"] = analyze(
        "B. APP-350 TEST ROWS (First/Third Party macro F1 @0.5): combined (saw APP-350 train) vs OPP-only zero-shot",
        y_app, pol_app, names[:2], preds, groups, [("BERT-combined", "BERT-OPP-only(0-shot)")],
        args.n_boot, args.rng, show_policies=False)

    args.out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
