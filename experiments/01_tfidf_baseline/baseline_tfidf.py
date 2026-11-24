"""
baseline_tfidf.py — Phase 2 classical baseline for PrivaScore's clause
classifier: TF-IDF + Logistic Regression, evaluated with macro F1.

WHY THIS COMES BEFORE BERT
---------------------------
Without this, a BERT F1 score is just a number floating in space — you can't
tell if it's actually good or if a simple linear model gets you 90% of the
way there for 1% of the training cost. This script exists purely to give you
that comparison point. Ablation study material: this run vs. the BERT run.

WHY THESE SPECIFIC CHOICES
----------------------------
- TF-IDF: turns each clause into a sparse "which words appear, weighted by
  how distinctive they are" vector. No notion of word order or context —
  that's exactly BERT's advantage, and exactly why this makes a fair
  baseline to beat.
- OneVsRestClassifier(LogisticRegression): this is a MULTI-LABEL problem
  (one clause can be both "Third Party Sharing" AND "Data Retention" at
  once — see the earlier corpus inspection). Plain LogisticRegression only
  predicts one class per input. OneVsRest trains one independent binary
  classifier per label ("is this Data Retention? yes/no") and combines
  the results — the standard sklearn way to do multi-label with a
  single-label-native model.
- class_weight="balanced": without this, Logistic Regression will just
  learn to always predict "First Party Collection/Use" and "Other" (the
  two biggest classes) and mostly ignore rare ones like Do Not Track,
  because ignoring rare classes barely hurts the loss. "balanced" upweights
  errors on rare classes so the model actually has to try on them.
- macro F1: computed per class, then averaged un-weighted across classes.
  A model that nails the 2 big classes and totally fails the 8 small ones
  would still look "good" on accuracy or micro F1. Macro F1 punishes that.

USAGE
-----
  python baseline_tfidf.py --data-dir /path/to/opp115_{train,validation,test}.jsonl --label-map opp115_label_map.json
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
    texts, labels = [], []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        texts.append(rec["text"])
        labels.append(rec["labels"])
    return texts, np.array(labels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=".", type=Path, help="Dir containing opp115_train/validation/test.jsonl")
    ap.add_argument("--label-map", default="opp115_label_map.json", type=Path)
    ap.add_argument("--max-features", default=10000, type=int,
                     help="Vocabulary cap for TF-IDF. 10k is generous for a 2.5k-doc corpus; "
                          "raising it further mostly adds noise, not signal.")
    args = ap.parse_args()

    label_map = json.loads(args.label_map.read_text())
    label_names = [label_map[str(i)] for i in range(len(label_map))]

    X_train_text, y_train = load_split(args.data_dir / "opp115_train.jsonl")
    X_val_text, y_val = load_split(args.data_dir / "opp115_validation.jsonl")
    X_test_text, y_test = load_split(args.data_dir / "opp115_test.jsonl")

    print(f"train={len(X_train_text)}  val={len(X_val_text)}  test={len(X_test_text)}")

    # ngram_range=(1,2): unigrams alone miss phrases like "third party" or
    # "opt out" where the pair of words carries the meaning, not either word
    # alone. Bigrams add that at a modest vocab-size cost.
    vectorizer = TfidfVectorizer(
        max_features=args.max_features,
        ngram_range=(1, 2),
        stop_words="english",
        min_df=2,  # drop terms that appear in only 1 document — usually noise/typos
    )
    X_train = vectorizer.fit_transform(X_train_text)
    X_val = vectorizer.transform(X_val_text)
    X_test = vectorizer.transform(X_test_text)

    clf = OneVsRestClassifier(
        LogisticRegression(
            class_weight="balanced",
            max_iter=1000,  # TF-IDF features can need more iterations to converge than dense features
            random_state=42,
        )
    )
    clf.fit(X_train, y_train)

    def evaluate(X, y_true, split_name):
        y_pred = clf.predict(X)
        macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        micro_f1 = f1_score(y_true, y_pred, average="micro", zero_division=0)
        macro_p = precision_score(y_true, y_pred, average="macro", zero_division=0)
        macro_r = recall_score(y_true, y_pred, average="macro", zero_division=0)
        print(f"\n=== {split_name} ===")
        print(f"macro F1: {macro_f1:.4f}   micro F1: {micro_f1:.4f}   macro P: {macro_p:.4f}   macro R: {macro_r:.4f}")
        return y_pred, macro_f1

    evaluate(X_train, y_train, "train (sanity check — should be notably higher than val)")
    evaluate(X_val, y_val, "validation")
    y_test_pred, test_macro_f1 = evaluate(X_test, y_test, "test")

    print("\n=== Per-class report (test set) ===")
    print(classification_report(y_test, y_test_pred, target_names=label_names, zero_division=0))

    print(f"\nBASELINE RESULT: test macro F1 = {test_macro_f1:.4f}")
    print("This is the number BERT needs to beat. Project's target for the")
    print("BERT-vs-baseline F1 delta was +5% (stretch: +12%) — write this")
    print("number down before you train BERT, not after, or you'll be tempted")
    print("to move the goalposts.")


if __name__ == "__main__":
    main()
