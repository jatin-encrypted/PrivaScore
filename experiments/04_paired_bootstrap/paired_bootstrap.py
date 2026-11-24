"""
paired_bootstrap.py - how strongly can "BERT beats TF-IDF" be claimed on the
18 held-out OPP-115 test policies?

WHY RESAMPLE POLICIES (not segments)
  Segments from one policy share vocabulary, boilerplate and annotator habits,
  so they are not independent. The unit of independence is the POLICY. Each
  bootstrap draw samples 18 policies with replacement, takes all their
  segments, and scores BOTH systems on that same resample (paired), so the
  difference isolates "which model is better" from "which policies happened
  to be drawn".

WHAT THE CI DOES AND DOES NOT COVER
  Covers: test-set sampling variability (which policies we got).
  Does not cover: training variability beyond the 3 seeds, or distribution
  shift to policies unlike OPP-115's (2016 website policies).

MACRO F1 IN A RESAMPLE
  A resample can contain zero positives for a rare class (Do Not Track has
  5 test examples, probably in 1-2 policies). Such a class has no defined F1,
  so it is excluded from that draw's macro average for BOTH systems.
  (--zero-fill scores it as 0 instead, as a sensitivity check.)

Fast implementation: per-policy TP/FP/FN counts are precomputed, so a
bootstrap draw is one multinomial count vector times a (policies x classes) matrix.
"""
import argparse
import json
from collections import OrderedDict
from pathlib import Path

import numpy as np

LABELS = None


def counts_by_policy(y, pred, pol_idx, n_pol):
    """-> array (n_pol, 3, n_classes) of TP, FP, FN."""
    out = np.zeros((n_pol, 3, y.shape[1]))
    for p in range(n_pol):
        m = pol_idx == p
        yt, yp = y[m], pred[m]
        out[p, 0] = (yt & yp).sum(0)
        out[p, 1] = ((1 - yt) & yp).sum(0)
        out[p, 2] = (yt & (1 - yp)).sum(0)
    return out


def macro_f1_from_counts(c, zero_fill=False):
    """c: (..., 3, n_classes) summed counts. Returns macro F1 over classes with support > 0."""
    tp, fp, fn = c[..., 0, :], c[..., 1, :], c[..., 2, :]
    denom = 2 * tp + fp + fn
    f1 = np.where(denom > 0, 2 * tp / np.maximum(denom, 1), 0.0)
    has_pos = (tp + fn) > 0
    if zero_fill:
        return f1.mean(-1)
    return (f1 * has_pos).sum(-1) / np.maximum(has_pos.sum(-1), 1)


def per_class_f1(c):
    tp, fp, fn = c[..., 0, :], c[..., 1, :], c[..., 2, :]
    denom = 2 * tp + fp + fn
    return np.where(denom > 0, 2 * tp / np.maximum(denom, 1), np.nan), (tp + fn) > 0


def ci(x, lo=2.5, hi=97.5):
    return float(np.percentile(x, lo)), float(np.percentile(x, hi))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs-dir", type=Path, default=Path("probs"))
    ap.add_argument("--data-dir", type=Path, default=Path("data/opp115"))
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--n-boot", type=int, default=20000)
    ap.add_argument("--rng", type=int, default=0)
    ap.add_argument("--zero-fill", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("paired_bootstrap_results.json"))
    args = ap.parse_args()

    label_map = json.loads((args.data_dir / "opp115_label_map.json").read_text())
    names = [label_map[str(i)] for i in range(10)]
    rows = {s: [json.loads(l) for l in (args.data_dir / f"opp115_{s}.jsonl").read_text().splitlines() if l.strip()]
            for s in ("train", "test")}
    y = np.array([r["labels"] for r in rows["test"]], dtype=int)
    policies = [r["policy_id"] for r in rows["test"]]
    uniq = list(OrderedDict.fromkeys(policies))
    pol_idx = np.array([uniq.index(p) for p in policies])
    n_pol = len(uniq)
    seg_per_pol = np.bincount(pol_idx)
    print(f"test: {len(y)} segments, {n_pol} policies; segments/policy min={seg_per_pol.min()} "
          f"median={int(np.median(seg_per_pol))} max={seg_per_pol.max()} (largest policy = {100 * seg_per_pol.max() / len(y):.1f}% of test)")
    pos_pols = (np.stack([np.bincount(pol_idx, weights=y[:, j], minlength=n_pol) for j in range(10)]) > 0).sum(1)
    print("policies containing >=1 positive per class:", dict(zip(names, pos_pols.tolist())))

    # ---- systems -> binary predictions on test
    preds = {}
    seeds = [int(s) for s in args.seeds.split(",")]
    for s in seeds:
        p = np.load(args.probs_dir / f"seed_{s}" / "test_probs.npy")
        assert p.shape == y.shape, (p.shape, y.shape)
        preds[f"bert_{s}"] = (p >= 0.5).astype(int)

    # TF-IDF baseline: identical recipe to baseline_tfidf.py (fit on train only)
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.multiclass import OneVsRestClassifier
    ytr = np.array([r["labels"] for r in rows["train"]], dtype=int)
    vec = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words="english", min_df=2)
    Xtr = vec.fit_transform([r["text"] for r in rows["train"]])
    clf = OneVsRestClassifier(LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)).fit(Xtr, ytr)
    preds["tfidf"] = clf.predict(vec.transform([r["text"] for r in rows["test"]])).astype(int)

    C = {k: counts_by_policy(y, v, pol_idx, n_pol) for k, v in preds.items()}

    # ---- sanity: full-test macro F1 must reproduce the stored numbers
    print("\nfull-test macro F1 (should equal stored: 0.7591 / 0.7620 / 0.7785 / 0.7273):")
    full = {k: float(macro_f1_from_counts(c.sum(0), args.zero_fill)) for k, c in C.items()}
    for k, v in full.items():
        print(f"  {k:<10} {v:.4f}")

    # ---- bootstrap
    rng = np.random.default_rng(args.rng)
    draws = rng.multinomial(n_pol, np.full(n_pol, 1 / n_pol), size=args.n_boot)  # (B, n_pol) policy multiplicities
    boot = {k: macro_f1_from_counts(np.einsum("bp,pcj->bcj", draws, c), args.zero_fill) for k, c in C.items()}
    bert_keys = [f"bert_{s}" for s in seeds]
    bert_mean = np.mean([boot[k] for k in bert_keys], axis=0)
    full_bert_mean = float(np.mean([full[k] for k in bert_keys]))

    res = {"n_policies": n_pol, "n_boot": args.n_boot, "zero_fill": args.zero_fill, "full": full, "systems": {}}
    print(f"\n=== paired policy bootstrap, {args.n_boot} draws, 95% percentile CI ===")
    print(f"{'comparison':<34}{'point':>9}{'95% CI':>20}{'P(delta>0)':>12}")

    def report(label, delta, point):
        lo, hi = ci(delta)
        pg = float((delta > 0).mean())
        print(f"{label:<34}{point:>+9.4f}   [{lo:+.4f}, {hi:+.4f}]{pg:>12.3f}")
        res["systems"][label] = {"point": point, "ci95": [lo, hi], "p_gt0": pg}

    report("BERT (mean of 3 seeds) - TF-IDF", bert_mean - boot["tfidf"], full_bert_mean - full["tfidf"])
    for k in bert_keys:
        report(f"{k} - TF-IDF", boot[k] - boot["tfidf"], full[k] - full["tfidf"])
    lo, hi = ci(bert_mean)
    print(f"\nBERT mean-of-seeds macro F1 itself: {full_bert_mean:.4f}, 95% CI [{lo:.4f}, {hi:.4f}]")
    lo, hi = ci(boot["tfidf"])
    print(f"TF-IDF macro F1 itself:             {full['tfidf']:.4f}, 95% CI [{lo:.4f}, {hi:.4f}]")
    # project target: +5% relative
    rel = bert_mean / boot["tfidf"] - 1
    lo, hi = ci(rel)
    print(f"relative gain (BERT mean / TF-IDF - 1): point {full_bert_mean / full['tfidf'] - 1:+.3%}, 95% CI [{lo:+.3%}, {hi:+.3%}], "
          f"P(>= +5%) = {(rel >= 0.05).mean():.3f}")

    # ---- per-class paired deltas (class-level F1 over the resample)
    print("\nper-class F1 delta (BERT mean-of-seeds - TF-IDF), bootstrap over policies")
    print(f"{'class':<40}{'BERT':>6}{'TFIDF':>7}{'delta':>8}{'95% CI':>20}{'P(>0)':>8}  support")
    bert_cls_boot, tf_cls_boot = [], None
    cls_res = {}
    for k in bert_keys:
        f, _ = per_class_f1(np.einsum("bp,pcj->bcj", draws, C[k]))
        bert_cls_boot.append(f)
    bert_cls_boot = np.nanmean(np.stack(bert_cls_boot), axis=0)
    tf_cls_boot, has_pos = per_class_f1(np.einsum("bp,pcj->bcj", draws, C["tfidf"]))
    fb = np.mean([per_class_f1(C[k].sum(0))[0] for k in bert_keys], axis=0)
    ft, _ = per_class_f1(C["tfidf"].sum(0))
    for j, n in enumerate(names):
        d = bert_cls_boot[:, j] - tf_cls_boot[:, j]
        d = d[~np.isnan(d)]
        lo, hi = ci(d)
        sup = int(y[:, j].sum())
        print(f"{n:<40}{fb[j]:>6.2f}{ft[j]:>7.2f}{fb[j] - ft[j]:>+8.3f}   [{lo:+.3f}, {hi:+.3f}]{(d > 0).mean():>8.2f}  {sup}"
              f"  (defined in {100 * len(d) / args.n_boot:.0f}% of draws)")
        cls_res[n] = {"bert": float(fb[j]), "tfidf": float(ft[j]), "ci95": [lo, hi], "p_gt0": float((d > 0).mean()), "support": sup}
    res["per_class"] = cls_res

    # ---- per-policy view: label-level errors (FP+FN) per policy, BERT seed-mean vs TF-IDF
    err_b = np.mean([C[k][:, 1:, :].sum((1, 2)) for k in bert_keys], axis=0)
    err_t = C["tfidf"][:, 1:, :].sum((1, 2))
    wins = int((err_b < err_t).sum()); ties = int((err_b == err_t).sum()); loss = int((err_b > err_t).sum())
    print(f"\nper-policy label errors (FP+FN): BERT fewer in {wins} policies, tie in {ties}, TF-IDF fewer in {loss} (of {n_pol})")
    order = np.argsort(err_b - err_t)
    print(f"{'policy':<34}{'segs':>5}{'BERT err':>10}{'TFIDF err':>10}{'diff':>8}")
    for p in order:
        print(f"{uniq[p]:<34}{seg_per_pol[p]:>5}{err_b[p]:>10.1f}{err_t[p]:>10.0f}{err_b[p] - err_t[p]:>+8.1f}")
    res["per_policy"] = {"bert_fewer": wins, "tie": ties, "tfidf_fewer": loss}

    args.out.write_text(json.dumps(res, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
