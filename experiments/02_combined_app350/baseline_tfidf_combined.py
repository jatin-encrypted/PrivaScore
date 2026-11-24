"""
baseline_tfidf_combined.py — TF-IDF + Logistic Regression on the COMBINED
OPP-115 + APP-350 dataset. Same methodology as baseline_tfidf.py (fair
comparison), but reports test performance BOTH overall and split by source,
because a good combined score could otherwise hide a regression on OPP-115
specifically (which is the corpus that actually has all 10 categories).
"""
import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, classification_report


def load_split(path: Path):
    texts, labels, sources = [], [], []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        texts.append(rec["text"])
        labels.append(rec["labels"])
        sources.append(rec["source"])
    return texts, np.array(labels), np.array(sources)


def report(y_true, y_pred, label_names, title):
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    micro_f1 = f1_score(y_true, y_pred, average="micro", zero_division=0)
    macro_p = precision_score(y_true, y_pred, average="macro", zero_division=0)
    macro_r = recall_score(y_true, y_pred, average="macro", zero_division=0)
    print(f"\n=== {title} (n={len(y_true)}) ===")
    print(f"macro F1: {macro_f1:.4f}   micro F1: {micro_f1:.4f}   macro P: {macro_p:.4f}   macro R: {macro_r:.4f}")
    return macro_f1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("."))
    ap.add_argument("--label-map", type=Path, required=True)
    ap.add_argument("--max-features", type=int, default=10000)
    args = ap.parse_args()

    label_map = json.loads(args.label_map.read_text())
    label_names = [label_map[str(i)] for i in range(len(label_map))]

    X_train_text, y_train, src_train = load_split(args.data_dir / "combined_train.jsonl")
    X_val_text, y_val, src_val = load_split(args.data_dir / "combined_validation.jsonl")
    X_test_text, y_test, src_test = load_split(args.data_dir / "combined_test.jsonl")

    print(f"train={len(X_train_text)}  val={len(X_val_text)}  test={len(X_test_text)}")

    vectorizer = TfidfVectorizer(
        max_features=args.max_features, ngram_range=(1, 2), stop_words="english", min_df=2,
    )
    X_train = vectorizer.fit_transform(X_train_text)  # fit ONLY on train text
    X_val = vectorizer.transform(X_val_text)
    X_test = vectorizer.transform(X_test_text)

    clf = OneVsRestClassifier(
        LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    )
    clf.fit(X_train, y_train)

    y_train_pred = clf.predict(X_train)
    y_val_pred = clf.predict(X_val)
    y_test_pred = clf.predict(X_test)

    report(y_train, y_train_pred, label_names, "train (sanity check)")
    report(y_val, y_val_pred, label_names, "validation")
    test_macro_f1 = report(y_test, y_test_pred, label_names, "test — COMBINED (all sources)")

    # Per-source breakdown of the SAME test predictions - not a re-fit, just
    # sliced by which rows came from which corpus.
    opp_mask = src_test == "opp115"
    app_mask = src_test == "app350"
    opp_f1 = report(y_test[opp_mask], y_test_pred[opp_mask], label_names, "test — OPP-115 rows only")
    app_f1 = report(y_test[app_mask], y_test_pred[app_mask], label_names, "test — APP-350 rows only")

    print("\n=== Per-class report (combined test set) ===")
    print(classification_report(y_test, y_test_pred, target_names=label_names, zero_division=0))

    print("\n=== Per-class report (OPP-115 rows of test set only) ===")
    print(classification_report(y_test[opp_mask], y_test_pred[opp_mask], target_names=label_names, zero_division=0))

    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    print(f"{'Experiment':<28}{'Train F1':>10}{'Val F1':>10}{'Test F1':>10}")
    print(f"{'OPP-115 only':<28}{0.9022:>10.4f}{0.7251:>10.4f}{0.7273:>10.4f}")
    print(f"{'OPP-115 + APP-350 (combined)':<28}{f1_score(y_train, y_train_pred, average='macro', zero_division=0):>10.4f}"
          f"{f1_score(y_val, y_val_pred, average='macro', zero_division=0):>10.4f}{test_macro_f1:>10.4f}")
    print(f"\nCombined test macro F1 broken down by which rows: OPP-115-only={opp_f1:.4f}  APP-350-only={app_f1:.4f}")
    print("\nRemember: OPP-115's 8 categories APP-350 can't touch (Retention, Security,")
    print("User Choice, Policy Change, DNT, Int'l Audiences, Other, User Access) are")
    print("*included* in both the combined-test and OPP-115-only-rows numbers above -")
    print("so if those numbers moved, it's because the classifier's shared parameters")
    print("changed, not because APP-350 taught it anything new about those categories.")


if __name__ == "__main__":
    main()
