"""
train_bert_opp115.py - Phase 3: fine-tune BERT for multi-label clause
classification on OPP-115 ONLY (PrivaScore).

WHAT THIS DOES NOT TOUCH
--------------------------
- baseline_tfidf.py and its outputs are not modified.
- The policy-level splits are NOT regenerated. This script reads the existing
  opp115_{train,validation,test}.jsonl files and asserts that they are
  policy-disjoint and have the expected sizes (2582 / 627 / 582 segments).
- APP-350 / the combined dataset is not used.

HOW TO RUN (needs a GPU; Colab/Kaggle T4 is enough, ~10-15 min for 3 seeds)
-----------------------------------------------------------------------------
  pip install "transformers>=4.40" accelerate scikit-learn torch
  python train_bert_opp115.py --data-dir . --label-map opp115_label_map.json \
         --out-dir bert_runs --seeds 42,43,44 --with-baseline

THE DECISIONS, AND WHY (this is the "learn ML while building" part)
----------------------------------------------------------------------
Model: bert-base-uncased, 10 sigmoid outputs (NOT softmax).
  Softmax forces the 10 probabilities to sum to 1, i.e. "pick one category".
  OPP-115 segments are multi-label (~48% carry 2+ categories), so each output
  is an independent yes/no question answered by a sigmoid, trained with
  binary cross-entropy (BCEWithLogitsLoss).

max_length = 256 tokens.
  The 99th percentile segment is ~220 words (~300 WordPieces); the 95th is
  ~163 words (~215 tokens). 256 covers roughly 97% of segments untruncated.
  Going to 512 costs ~2-4x compute for almost no extra coverage.

Dynamic padding: each batch is padded only to its own longest sequence, so
  short segments (median 60 words) don't waste compute on padding.

Learning rate 2e-5, batch size 16, weight decay 0.01, warmup 10%, linear decay.
  Standard BERT fine-tuning range (2e-5 to 5e-5). The pretrained weights are
  already good; a small LR nudges them rather than overwriting them. Warmup
  avoids large early updates on randomly-initialised classifier weights.
  Weight decay is a mild L2-style regulariser against overfitting 2.5k examples.

Epochs: up to 8 with early stopping (patience 3) on VALIDATION macro F1, and
  the best-validation checkpoint is reloaded at the end. Test is never used
  for any choice. On small data the epoch count is the main overfitting knob.

Class imbalance: --pos-weight sqrt (default).
  The TF-IDF baseline used class_weight="balanced". The BERT analogue is
  BCE's pos_weight (multiplies the loss on positive examples per label).
  Fully balanced weights would be ~111x for Do Not Track (23 positives of
  2582), which makes training unstable; sqrt(neg/pos) (~10.5x) is a common
  compromise. Options: none | sqrt | balanced. Treat as an ablation.

Decision threshold: reported two ways.
  (a) fixed 0.5 for every label - the same decision rule the LogReg baseline
      uses, so this is the like-for-like comparison.
  (b) per-label thresholds tuned on VALIDATION only, then frozen and applied
      to test. Labels with < --min-threshold-support validation positives
      (Do Not Track has 4) keep 0.5, because tuning on a handful of examples
      just memorises them.

Seeds: fine-tuning has real run-to-run variance (init of the classifier head,
  batch order). With 18 test policies, one seed's number is not trustworthy,
  so run several and report mean +/- std.
"""
import argparse
import inspect
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (classification_report, f1_score, precision_score,
                             recall_score)
from torch import nn
from torch.utils.data import Dataset
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          DataCollatorWithPadding, EarlyStoppingCallback,
                          Trainer, TrainingArguments, set_seed)

BASELINE = {"train": 0.9022, "val": 0.7251, "test": 0.7273}  # TF-IDF + LogReg, OPP-115 only
EXPECTED_SIZES = {"train": 2582, "validation": 627, "test": 582}


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_split(path: Path):
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    texts = [r["text"] for r in rows]
    labels = np.array([r["labels"] for r in rows], dtype=np.float32)
    policies = [r["policy_id"] for r in rows]
    return texts, labels, policies


def check_splits(policies_by_split, check_sizes=True):
    """Hard guarantees that the existing policy-level splits are intact."""
    names = list(policies_by_split)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            overlap = set(policies_by_split[names[i]]) & set(policies_by_split[names[j]])
            assert not overlap, f"Policy leakage between {names[i]} and {names[j]}: {sorted(overlap)[:5]}"
    if check_sizes:
        for n, expected in EXPECTED_SIZES.items():
            got = len(policies_by_split[n])
            assert got == expected, (
                f"{n} has {got} segments, expected {expected}. The split files differ from the "
                f"ones the TF-IDF baseline used; pass --no-split-check only if that is intentional.")
    print("Split check OK: policy-disjoint; sizes "
          + " / ".join(f"{n}={len(p)}" for n, p in policies_by_split.items()))


class SegmentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length):
        # No padding here; DataCollatorWithPadding pads per batch (dynamic padding).
        self.enc = tokenizer(texts, truncation=True, max_length=max_length)
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        # plain list of floats: the padding collator turns the batch into a float tensor itself
        item["labels"] = self.labels[i].tolist()
        return item


# ----------------------------------------------------------------------------
# Metrics / thresholds
# ----------------------------------------------------------------------------
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def evaluate(y_true, y_pred, label_names):
    p, r, f, s = [], [], [], []
    for j in range(len(label_names)):
        p.append(precision_score(y_true[:, j], y_pred[:, j], zero_division=0))
        r.append(recall_score(y_true[:, j], y_pred[:, j], zero_division=0))
        f.append(f1_score(y_true[:, j], y_pred[:, j], zero_division=0))
        s.append(int(y_true[:, j].sum()))
    return {
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "micro_f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "macro_precision": float(np.mean(p)),
        "macro_recall": float(np.mean(r)),
        "per_class": {n: {"precision": p[j], "recall": r[j], "f1": f[j], "support": s[j]}
                      for j, n in enumerate(label_names)},
    }


def tune_thresholds(y_true, probs, min_support, grid=np.arange(0.05, 0.951, 0.05)):
    th = np.full(y_true.shape[1], 0.5)
    for j in range(y_true.shape[1]):
        if y_true[:, j].sum() < min_support:
            continue  # too few positives to tune on without memorising them
        best = None
        for t in grid:
            f = f1_score(y_true[:, j], probs[:, j] >= t, zero_division=0)
            key = (f, -abs(t - 0.5))  # tie-break toward 0.5
            if best is None or key > best[0]:
                best = (key, t)
        th[j] = best[1]
    return th


def compute_metrics_fn(eval_pred):
    logits, labels = eval_pred
    pred = (sigmoid(logits) >= 0.5).astype(int)
    return {"macro_f1": f1_score(labels, pred, average="macro", zero_division=0),
            "micro_f1": f1_score(labels, pred, average="micro", zero_division=0)}


# ----------------------------------------------------------------------------
# Trainer with weighted BCE
# ----------------------------------------------------------------------------
class WeightedBCETrainer(Trainer):
    def __init__(self, *args, pos_weight=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pos_weight = pos_weight

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        pw = self._pos_weight.to(logits.device) if self._pos_weight is not None else None
        loss = nn.functional.binary_cross_entropy_with_logits(
            logits, labels.to(logits.dtype), pos_weight=pw)
        return (loss, outputs) if return_outputs else loss


def make_pos_weight(y_train, mode):
    if mode == "none":
        return None
    pos = y_train.sum(0)
    neg = len(y_train) - pos
    ratio = neg / np.maximum(pos, 1)
    w = np.sqrt(ratio) if mode == "sqrt" else ratio
    return torch.tensor(w, dtype=torch.float32)


# ----------------------------------------------------------------------------
# Optional: re-run the TF-IDF baseline recipe (does not modify baseline files)
# ----------------------------------------------------------------------------
def rerun_tfidf_baseline(train_texts, y_train, test_texts, y_test, label_names):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.multiclass import OneVsRestClassifier
    vec = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words="english", min_df=2)
    Xtr = vec.fit_transform(train_texts)
    clf = OneVsRestClassifier(LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42))
    clf.fit(Xtr, y_train.astype(int))
    pred = clf.predict(vec.transform(test_texts))
    res = evaluate(y_test.astype(int), pred, label_names)
    if abs(res["macro_f1"] - BASELINE["test"]) > 2e-3:
        print(f"WARNING: re-run baseline test macro F1 {res['macro_f1']:.4f} != recorded {BASELINE['test']}")
    return res


# ----------------------------------------------------------------------------
# One training run
# ----------------------------------------------------------------------------
def run_one(seed, args, data, label_names, tokenizer, out_dir):
    set_seed(seed)
    n_labels = len(label_names)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name, num_labels=n_labels, problem_type="multi_label_classification")

    steps_per_epoch = math.ceil(len(data["train"]) / args.batch_size)
    total_steps = steps_per_epoch * args.epochs
    ta_params = inspect.signature(TrainingArguments.__init__).parameters
    eval_key = "eval_strategy" if "eval_strategy" in ta_params else "evaluation_strategy"
    targs = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=64,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        weight_decay=args.weight_decay,
        warmup_steps=int(args.warmup_frac * total_steps),
        lr_scheduler_type="linear",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=1,
        logging_steps=50,
        report_to="none",
        fp16=torch.cuda.is_available(),
        seed=seed,
        data_seed=seed,
        **{eval_key: "epoch"},
    )
    trainer = WeightedBCETrainer(
        model=model, args=targs,
        train_dataset=data["train"], eval_dataset=data["validation"],
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics_fn,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=args.patience)],
        pos_weight=data["pos_weight"],
    )
    t0 = time.time()
    trainer.train()
    train_secs = time.time() - t0

    probs = {s: sigmoid(trainer.predict(data[s]).predictions) for s in ["train", "validation", "test"]}
    y = data["y"]
    thresholds = tune_thresholds(y["validation"], probs["validation"], args.min_threshold_support)

    result = {"seed": seed, "train_seconds": round(train_secs, 1),
              "thresholds": dict(zip(label_names, thresholds.round(2).tolist())),
              "epochs_logged": [h for h in trainer.state.log_history if "eval_macro_f1" in h]}
    for s in ["train", "validation", "test"]:
        result[s] = {
            "fixed_0.5": evaluate(y[s].astype(int), (probs[s] >= 0.5).astype(int), label_names),
            "val_tuned": evaluate(y[s].astype(int), (probs[s] >= thresholds).astype(int), label_names),
        }
        np.save(out_dir / f"{s}_probs.npy", probs[s])
    (out_dir / "result.json").write_text(json.dumps(result, indent=2))
    del trainer, model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return result


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("."))
    ap.add_argument("--label-map", type=Path, default=Path("opp115_label_map.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("bert_runs"))
    ap.add_argument("--model-name", default="bert-base-uncased")
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--patience", type=int, default=3)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--warmup-frac", type=float, default=0.1)
    ap.add_argument("--pos-weight", choices=["none", "sqrt", "balanced"], default="sqrt")
    ap.add_argument("--min-threshold-support", type=int, default=10)
    ap.add_argument("--with-baseline", action="store_true",
                    help="Re-run the TF-IDF recipe for an exact per-class comparison table")
    ap.add_argument("--no-split-check", action="store_true")
    ap.add_argument("--max-train-samples", type=int, default=None, help="debug/smoke test only")
    ap.add_argument("--max-eval-samples", type=int, default=None, help="debug/smoke test only")
    args = ap.parse_args()

    label_map = json.loads(args.label_map.read_text())
    label_names = [label_map[str(i)] for i in range(len(label_map))]

    texts, labels, policies = {}, {}, {}
    for s in ["train", "validation", "test"]:
        texts[s], labels[s], policies[s] = load_split(args.data_dir / f"opp115_{s}.jsonl")
    check_splits(policies, check_sizes=not args.no_split_check)

    subsampled = args.max_train_samples or args.max_eval_samples
    if args.max_train_samples:
        texts["train"], labels["train"] = texts["train"][:args.max_train_samples], labels["train"][:args.max_train_samples]
    if args.max_eval_samples:
        for s in ["validation", "test"]:
            texts[s], labels[s] = texts[s][:args.max_eval_samples], labels[s][:args.max_eval_samples]

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    data = {s: SegmentDataset(texts[s], labels[s], tokenizer, args.max_length)
            for s in ["train", "validation", "test"]}
    data["y"] = labels
    data["pos_weight"] = make_pos_weight(labels["train"], args.pos_weight)
    if data["pos_weight"] is not None:
        print("pos_weight per label:", dict(zip(label_names, data["pos_weight"].numpy().round(1).tolist())))

    baseline_res = None
    if args.with_baseline and not subsampled:
        baseline_res = rerun_tfidf_baseline(texts["train"], labels["train"], texts["test"], labels["test"], label_names)
        print(f"Re-ran TF-IDF baseline: test macro F1 = {baseline_res['macro_f1']:.4f}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "config.json").write_text(json.dumps(
        {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}, indent=2))

    results = []
    for seed in [int(s) for s in args.seeds.split(",")]:
        print(f"\n{'=' * 70}\nSEED {seed}\n{'=' * 70}")
        run_dir = args.out_dir / f"seed_{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        results.append(run_one(seed, args, data, label_names, tokenizer, run_dir))

    # ---- summary ----
    print(f"\n{'=' * 70}\nSUMMARY (macro F1)\n{'=' * 70}")
    print(f"{'run':<22}{'val@0.5':>10}{'test@0.5':>10}{'val tuned':>11}{'test tuned':>12}")
    for r in results:
        print(f"{'BERT seed ' + str(r['seed']):<22}{r['validation']['fixed_0.5']['macro_f1']:>10.4f}"
              f"{r['test']['fixed_0.5']['macro_f1']:>10.4f}{r['validation']['val_tuned']['macro_f1']:>11.4f}"
              f"{r['test']['val_tuned']['macro_f1']:>12.4f}")
    t05 = np.array([r["test"]["fixed_0.5"]["macro_f1"] for r in results])
    ttu = np.array([r["test"]["val_tuned"]["macro_f1"] for r in results])
    print(f"{'BERT mean +/- std':<22}{'':>10}{t05.mean():>10.4f}{'':>11}{ttu.mean():>12.4f}   (std {t05.std():.4f} / {ttu.std():.4f})")
    print(f"{'TF-IDF baseline':<22}{BASELINE['val']:>10.4f}{BASELINE['test']:>10.4f}")
    print(f"\nTest macro F1 @0.5 vs baseline: {t05.mean() - BASELINE['test']:+.4f} absolute, "
          f"{100 * (t05.mean() / BASELINE['test'] - 1):+.1f}% relative")

    names = label_names
    print(f"\nPer-class test F1 (mean over seeds, threshold 0.5)" + (" vs re-run baseline" if baseline_res else ""))
    for n in names:
        m = np.mean([r["test"]["fixed_0.5"]["per_class"][n]["f1"] for r in results])
        sup = results[0]["test"]["fixed_0.5"]["per_class"][n]["support"]
        line = f"  {n:<40} BERT {m:.2f}"
        if baseline_res:
            line += f"   TF-IDF {baseline_res['per_class'][n]['f1']:.2f}"
        print(line + f"   (support {sup})")
    print("\nCaution: 18 test policies and tiny classes (Do Not Track support=5) make gaps under ~0.02 macro F1 "
          "indistinguishable from seed noise. Judge by the mean over seeds, not by one run.")

    (args.out_dir / "summary.json").write_text(json.dumps({
        "baseline": BASELINE, "baseline_rerun": baseline_res,
        "test_macro_f1_fixed_0.5": {"mean": float(t05.mean()), "std": float(t05.std()), "per_seed": t05.tolist()},
        "test_macro_f1_val_tuned": {"mean": float(ttu.mean()), "std": float(ttu.std()), "per_seed": ttu.tolist()},
    }, indent=2))


if __name__ == "__main__":
    main()
