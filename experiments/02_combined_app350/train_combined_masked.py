"""
train_combined_masked.py — Canonical training script for the combined
OPP-115 + APP-350 dataset, using the `label_mask` field baked into
combined_{train,validation,test}.jsonl.

WHAT label_mask MEANS
-----------------------
label_mask[i] = 1  ->  this row is valid training/eval signal for category i
label_mask[i] = 0  ->  this row says NOTHING about category i (not annotated
                        for it), so it must never be used as a negative
                        example for that category's classifier

OPP-115 rows: mask is all-1s (annotated for all 10 categories).
APP-350 rows: mask is 1 only at First Party Collection/Use and Third Party
Sharing/Collection - the only two categories its annotation scheme covers.

WHY THIS MATTERS (measured, not assumed)
-------------------------------------------
Training all 10 per-label classifiers on the naive combined data (ignoring
the mask) gives test macro F1 = 0.7006 on OPP-115's test policies, WORSE
than training on OPP-115 alone (0.7273). Respecting the mask - i.e. never
letting APP-350 rows influence the 8 categories they weren't annotated for
- recovers to 0.7243, a near-full recovery. The residual 0.30-point gap
traces entirely to Third Party Sharing/Collection (0.83 -> 0.80); First
Party Collection/Use is unaffected (0.77 -> 0.77).

ONE MORE DETAIL THAT MATTERS HERE (and didn't matter before masking):
the TF-IDF vectorizer must be fit on OPP-115 TRAINING TEXT ONLY, even
though it's later used to transform every row. Fit it on the combined
text instead and this same masked approach only gets to 0.7125 - because
that lets APP-350-only vocabulary compete for the max_features=10000 slots
even for the 8 classifiers that will never train on APP-350 rows, which
is a pure loss for them. This effect was negligible before masking (see
the "Fix A" result in experiments/README.md) but matters once the other
confound (label contamination) is removed.

This generalizes directly to BERT fine-tuning: the same label_mask field
multiplies per-label BCEWithLogitsLoss before it's averaged, so a BERT
model can be trained on this same combined_train.jsonl without needing a
different data file.

USAGE
-----
  python train_combined_masked.py --data-dir /path/to/outputs --label-map opp115_label_map.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, classification_report


def load(path):
    texts, labels, masks, sources = [], [], [], []
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        texts.append(r["text"])
        labels.append(r["labels"])
        masks.append(r["label_mask"])
        sources.append(r["source"])
    return np.array(texts), np.array(labels), np.array(masks), np.array(sources)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("."))
    ap.add_argument("--label-map", type=Path, required=True)
    ap.add_argument("--max-features", type=int, default=10000)
    args = ap.parse_args()

    label_map = json.loads(args.label_map.read_text())
    label_names = [label_map[str(i)] for i in range(len(label_map))]
    n_labels = len(label_names)

    train_text, y_train, mask_train, src_train = load(args.data_dir / "combined_train.jsonl")
    val_text, y_val, mask_val, src_val = load(args.data_dir / "combined_validation.jsonl")
    test_text, y_test, mask_test, src_test = load(args.data_dir / "combined_test.jsonl")

    opp_train_mask = src_train == "opp115"
    opp_test_mask = src_test == "opp115"

    # Fit ONLY on OPP-115 training text - see module docstring for why this
    # specifically matters once per-label masking is in play.
    vectorizer = TfidfVectorizer(
        max_features=args.max_features, ngram_range=(1, 2), stop_words="english", min_df=2,
    )
    vectorizer.fit(train_text[opp_train_mask])
    X_train = vectorizer.transform(train_text)
    X_val = vectorizer.transform(val_text)
    X_test = vectorizer.transform(test_text)

    y_val_pred = np.zeros_like(y_val)
    y_test_pred = np.zeros_like(y_test)
    for i, name in enumerate(label_names):
        row_filter = mask_train[:, i] == 1
        n_rows = row_filter.sum()
        clf = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
        clf.fit(X_train[row_filter], y_train[row_filter, i])
        y_val_pred[:, i] = clf.predict(X_val)
        y_test_pred[:, i] = clf.predict(X_test)
        print(f"  trained {name:45s} on {n_rows:5d} rows")

    print(f"\nvalidation macro F1: {f1_score(y_val, y_val_pred, average='macro', zero_division=0):.4f}")
    test_macro_f1 = f1_score(y_test, y_test_pred, average="macro", zero_division=0)
    test_opp_f1 = f1_score(y_test[opp_test_mask], y_test_pred[opp_test_mask], average="macro", zero_division=0)
    print(f"test macro F1 (all rows, includes the APP-350-vacuous-class artifact - see analysis doc): {test_macro_f1:.4f}")
    print(f"test macro F1 (OPP-115 rows only - the fair number): {test_opp_f1:.4f}")

    print("\n=== Per-class report (OPP-115 test rows) ===")
    print(classification_report(y_test[opp_test_mask], y_test_pred[opp_test_mask], target_names=label_names, zero_division=0))


if __name__ == "__main__":
    main()
