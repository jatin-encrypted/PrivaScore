"""
train_bert_combined_masked.py - fine-tune a FRESH bert-base-uncased on the combined
OPP-115 + APP-350 data (combined_train.jsonl) with a MASKED multi-label loss.

THE ONE IDEA THIS SCRIPT IS ABOUT
-----------------------------------
Every row carries label_mask (10 values, 0/1):
    label_mask[j] = 1 -> label j was actually annotated for this segment, so the 0/1 in
                         labels[j] is a real answer (a confirmed positive OR a confirmed negative)
    label_mask[j] = 0 -> label j was NEVER annotated for this segment (APP-350 only knows
                         First Party / Third Party). The 0 in labels[j] means "unknown", not "no".

A normal BCE loss would treat those unknown 0s as confirmed negatives and teach BERT that
APP-350 segments never mention Data Retention, Data Security, ... which is false. That is
exactly the contamination that dropped the TF-IDF model from 0.7273 to 0.7006 before masking.

Masked loss, per batch:
    per_entry = BCEWithLogits(logits, labels, pos_weight, reduction="none")   # (B, 10)
    loss      = (per_entry * label_mask).sum() / label_mask.sum()
  * a masked entry is multiplied by 0 -> contributes 0 to the loss AND exactly 0 gradient
  * dividing by label_mask.sum() (not B*10) makes the loss "mean over VALID annotations", so an
    APP-350 row (2 valid entries) simply counts for less than an OPP-115 row (10 valid entries)
    instead of its 8 blanks diluting the average.

OTHER DECISIONS (same recipe as train_bert_opp115.py so results stay comparable)
-------------------------------------------------------------------------------
- Model: fresh bert-base-uncased (NOT the OPP-115-finetuned checkpoints), 10 sigmoid outputs.
- pos_weight = sqrt(neg/pos) per label, counted ONLY over rows where that label's mask == 1
  (otherwise APP-350's unknown 0s would inflate the "negatives" for classes 2-9).
- max_length 256, lr 2e-5, batch 16, weight decay 0.01, 10% warmup, linear decay,
  up to 8 epochs, early stopping (patience 3) on VALIDATION macro F1, seeds 42/43/44.
- Validation macro F1 is mask-aware too: each class is scored only on rows where its mask == 1.
  --select-metric masked_all (default): that score over ALL validation rows (OPP + APP)
  --select-metric opp115             : that score over OPP-115 validation rows only
  Test is never used for any choice.
- The best checkpoint is reloaded with from_pretrained() (Transformers 5.x LayerNorm
  gamma/beta renaming quirk, see verify_best_checkpoint.py) and re-scored; the script warns
  if that does not reproduce the validation score logged during training.

HOW TO READ THE RESULTS
-------------------------
- Headline = OPP-115 test rows, 10-class macro F1 @0.5. Same 582 rows / 18 policies as
  TF-IDF OPP-only 0.7273, TF-IDF masked-combined 0.7243 and BERT OPP-only 0.7665.
- APP-350 test rows are scored on First Party / Third Party only (the only annotated labels):
  a 2-class number, never a 10-class score. Because APP-350 train rows are in training here,
  it is an in-distribution number, NOT the external-generalisation test (0.7715) from before.

USAGE (Colab, T4 GPU)
-----------------------
  !pip install -q "transformers>=4.40" accelerate scikit-learn
  !python train_bert_combined_masked.py --self-test          # 5 seconds, checks the loss maths
  !python train_bert_combined_masked.py --data-dir . --label-map opp115_label_map.json \
        --seeds 42 --epochs 1 --max-train-samples 300 --max-eval-samples 100   # smoke test
  !python train_bert_combined_masked.py --data-dir . --label-map opp115_label_map.json \
        --out-dir bert_combined_runs --seeds 42,43,44
"""
import argparse
import inspect
import json
import math
import shutil
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, Dataset
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          EarlyStoppingCallback, Trainer, TrainingArguments, set_seed)

FP_NAME = "First Party Collection/Use"
TP_NAME = "Third Party Sharing/Collection"
REFERENCE = {  # recorded results, for the summary printout only
    "TF-IDF OPP-115-only": 0.7273,
    "TF-IDF masked combined": 0.7243,
    "BERT OPP-115-only (3-seed mean)": 0.7665,
}
EXPECTED = {  # segments per split in combined_*.jsonl
    "train": {"opp115": 2582, "app350": 2726},
    "validation": {"opp115": 627, "app350": 549},
    "test": {"opp115": 582, "app350": 662},
}


# ----------------------------------------------------------------------------
# Masked loss (the core of this script)
# ----------------------------------------------------------------------------
def masked_bce_with_logits(logits, labels, label_mask, pos_weight=None):
    """Mean BCE over VALID annotations only. Masked entries: zero loss, zero gradient."""
    per_entry = F.binary_cross_entropy_with_logits(
        logits.float(), labels.float(), pos_weight=pos_weight, reduction="none")  # (B, n_labels)
    label_mask = label_mask.float()
    return (per_entry * label_mask).sum() / label_mask.sum().clamp(min=1.0)


def self_test():
    """Checks the properties the masked loss must have. Needs only torch, runs in seconds."""
    torch.manual_seed(0)
    B, L = 8, 10
    logits = torch.randn(B, L, requires_grad=True)
    labels = torch.randint(0, 2, (B, L)).float()
    pw = torch.rand(L) * 5 + 1

    # 1. all-ones mask reproduces the ordinary (OPP-115-only) loss exactly
    a = masked_bce_with_logits(logits, labels, torch.ones(B, L), pw)
    b = F.binary_cross_entropy_with_logits(logits, labels, pos_weight=pw)
    assert torch.allclose(a, b, atol=1e-6), (a.item(), b.item())

    # 2. masked entries receive exactly zero gradient; valid entries receive some
    mask = (torch.rand(B, L) > 0.5).float()
    mask[0, 0] = 1.0
    loss = masked_bce_with_logits(logits, labels, mask, pw)
    (g,) = torch.autograd.grad(loss, logits)
    assert torch.all(g[mask == 0] == 0), "gradient leaked into masked entries"
    assert g[mask == 1].abs().sum() > 0

    # 3. flipping labels / shifting logits at masked positions cannot change the loss
    labels2 = labels.clone()
    labels2[mask == 0] = 1 - labels2[mask == 0]
    logits2 = logits.detach().clone()
    logits2[mask == 0] += 5.0
    assert torch.allclose(masked_bce_with_logits(logits2, labels2, mask, pw), loss.detach(), atol=1e-6)

    # 4. a batch with no valid entries gives a finite zero (no 0/0 NaN)
    assert masked_bce_with_logits(logits, labels, torch.zeros(B, L), pw).item() == 0.0

    # 5. APP-350-style rows (only columns 0 and 1 valid) move only those two output columns
    app_mask = torch.zeros(B, L)
    app_mask[:, :2] = 1.0
    (g2,) = torch.autograd.grad(masked_bce_with_logits(logits, labels, app_mask, pw), logits)
    assert torch.all(g2[:, 2:] == 0) and g2[:, :2].abs().sum() > 0
    print("self-test OK: all-ones mask == plain BCE; masked entries have zero loss and zero gradient; "
          "no-valid-entry batch is finite; APP-style rows only train columns 0/1")


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_split(path: Path):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {
        "texts": [r["text"] for r in rows],
        "y": np.array([r["labels"] for r in rows], dtype=np.float32),
        "mask": np.array([r["label_mask"] for r in rows], dtype=np.float32),
        "src": np.array([r["source"] for r in rows]),
        "policy": [r["policy_id"] for r in rows],
    }


def check_data(data, label_names, check_sizes=True):
    """Hard guarantees: policy-disjoint splits, well-formed masks, expected sizes."""
    fp, tp = label_names.index(FP_NAME), label_names.index(TP_NAME)
    names = list(data)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            overlap = set(data[names[i]]["policy"]) & set(data[names[j]]["policy"])
            assert not overlap, f"Policy leakage {names[i]}/{names[j]}: {sorted(overlap)[:5]}"
    for s, d in data.items():
        assert set(np.unique(d["mask"])) <= {0.0, 1.0}, f"{s}: mask must be 0/1"
        opp, app = d["src"] == "opp115", d["src"] == "app350"
        assert (opp | app).all(), f"{s}: unknown source value"
        assert (d["mask"][opp] == 1).all(), f"{s}: OPP-115 rows must have an all-ones mask"
        app_expected = np.zeros(len(label_names), dtype=np.float32)
        app_expected[[fp, tp]] = 1
        assert (d["mask"][app] == app_expected).all(), f"{s}: APP-350 mask must be 1 only at First/Third Party"
        assert (d["y"][d["mask"] == 0] == 0).all(), f"{s}: masked-out labels should all be 0 (unannotated)"
        if check_sizes:
            for src, n in EXPECTED[s].items():
                got = int((d["src"] == src).sum())
                assert got == n, (f"{s}/{src}: {got} segments, expected {n}. These are not the files "
                                  f"split_combined.py produced; use --no-split-check if intentional.")
    print("Data check OK: policy-disjoint; masks valid; sizes "
          + " | ".join(f"{s}: opp115={int((d['src']=='opp115').sum())} app350={int((d['src']=='app350').sum())}"
                       for s, d in data.items()))


def subsample(d, k, seed=0):
    if k is None or k >= len(d["texts"]):
        return d
    idx = np.sort(np.random.RandomState(seed).permutation(len(d["texts"]))[:k])
    return {"texts": [d["texts"][i] for i in idx], "y": d["y"][idx], "mask": d["mask"][idx],
            "src": d["src"][idx], "policy": [d["policy"][i] for i in idx]}


class SegmentDataset(Dataset):
    def __init__(self, d, tokenizer, max_length):
        self.enc = tokenizer(d["texts"], truncation=True, max_length=max_length)  # padded per batch later
        self.y, self.mask = d["y"], d["mask"]

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = self.y[i].tolist()
        item["label_mask"] = self.mask[i].tolist()
        return item


class MaskedCollator:
    """Pads the text fields per batch (dynamic padding); stacks labels and label_mask as float tensors."""

    def __init__(self, tokenizer):
        self.tok = tokenizer

    def __call__(self, features):
        text = [{k: v for k, v in f.items() if k not in ("labels", "label_mask")} for f in features]
        batch = self.tok.pad(text, padding=True, return_tensors="pt")
        batch["labels"] = torch.tensor([f["labels"] for f in features], dtype=torch.float32)
        batch["label_mask"] = torch.tensor([f["label_mask"] for f in features], dtype=torch.float32)
        return batch


# ----------------------------------------------------------------------------
# Mask-aware metrics
# ----------------------------------------------------------------------------
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def masked_eval(y, pred, mask, label_names):
    """Per-class F1 using only rows where that class's mask == 1; macro = mean over scored classes.
    A class with no valid rows in the subset is skipped, not scored as 0.
    With an all-ones mask this equals f1_score(average='macro', zero_division=0)."""
    per_class, f1s = {}, []
    for j, name in enumerate(label_names):
        valid = mask[:, j] == 1
        if valid.sum() == 0:
            continue
        yt, yp = y[valid, j].astype(int), pred[valid, j].astype(int)
        f = float(f1_score(yt, yp, zero_division=0))
        per_class[name] = {"f1": f, "precision": float(precision_score(yt, yp, zero_division=0)),
                           "recall": float(recall_score(yt, yp, zero_division=0)),
                           "support": int(yt.sum()), "n_valid_rows": int(valid.sum())}
        f1s.append(f)
    return {"macro_f1": float(np.mean(f1s)) if f1s else float("nan"),
            "n_classes_scored": len(f1s), "per_class": per_class}


def evaluate_block(d, probs, thr, label_names):
    pred = (probs >= thr).astype(int)
    opp, app = d["src"] == "opp115", d["src"] == "app350"
    return {"opp115_10class": masked_eval(d["y"][opp], pred[opp], d["mask"][opp], label_names),
            "app350_first_third_only": masked_eval(d["y"][app], pred[app], d["mask"][app], label_names),
            "masked_all": masked_eval(d["y"], pred, d["mask"], label_names)}


def tune_thresholds_masked(y, probs, mask, min_support, grid=np.arange(0.05, 0.951, 0.05)):
    """Per-label threshold from validation only, using only rows where that label is annotated.
    Labels with fewer than min_support valid positives keep 0.5 (tuning would just memorise)."""
    th = np.full(y.shape[1], 0.5)
    for j in range(y.shape[1]):
        valid = mask[:, j] == 1
        yt = y[valid, j]
        if yt.sum() < min_support:
            continue
        best = None
        for t in grid:
            key = (f1_score(yt, probs[valid, j] >= t, zero_division=0), -abs(t - 0.5))
            if best is None or key > best[0]:
                best = (key, t)
        th[j] = best[1]
    return th


def make_pos_weight(y, mask, mode):
    """sqrt(neg/pos) per label, counted over VALID rows only. Returns numpy (n_labels,) or None."""
    if mode == "none":
        return None
    valid_n = mask.sum(0)
    pos = (y * mask).sum(0)
    neg = valid_n - pos
    ratio = neg / np.maximum(pos, 1)
    return (np.sqrt(ratio) if mode == "sqrt" else ratio).astype(np.float32)


# ----------------------------------------------------------------------------
# Trainer with masked BCE
# ----------------------------------------------------------------------------
class MaskedBCETrainer(Trainer):
    def __init__(self, *args, pos_weight=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pos_weight = None if pos_weight is None else torch.tensor(pos_weight, dtype=torch.float32)

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        label_mask = inputs.pop("label_mask")  # must not reach model(**inputs)
        outputs = model(**inputs)
        pw = self._pos_weight.to(outputs.logits.device) if self._pos_weight is not None else None
        loss = masked_bce_with_logits(outputs.logits, labels, label_mask, pw)
        return (loss, outputs) if return_outputs else loss


@torch.no_grad()
def predict_logits(model, dataset, collator, batch_size=64):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    out = []
    for batch in DataLoader(dataset, batch_size=batch_size, shuffle=False, collate_fn=collator):
        batch = {k: v.to(device) for k, v in batch.items() if k not in ("labels", "label_mask")}
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=(device == "cuda")):
            out.append(model(**batch).logits.float().cpu().numpy())
    return np.concatenate(out)


# ----------------------------------------------------------------------------
# One training run
# ----------------------------------------------------------------------------
def run_one(seed, args, raw, ds, label_names, tokenizer, collator, pos_weight, run_dir):
    set_seed(seed)
    n_labels = len(label_names)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name, num_labels=n_labels, problem_type="multi_label_classification")

    val = raw["validation"]
    val_opp = val["src"] == "opp115"

    def val_scores(logits):
        assert logits.shape[0] == len(val["y"]), "eval predictions must be in dataset order"
        pred = (sigmoid(logits) >= 0.5).astype(int)
        all_f1 = masked_eval(val["y"], pred, val["mask"], label_names)["macro_f1"]
        opp_f1 = masked_eval(val["y"][val_opp], pred[val_opp], val["mask"][val_opp], label_names)["macro_f1"]
        return {"macro_f1": all_f1 if args.select_metric == "masked_all" else opp_f1,
                "masked_all_f1": all_f1, "opp115_f1": opp_f1}

    def compute_metrics(eval_pred):
        logits, _ = eval_pred  # same unpacking the OPP-115-only script used
        logits = logits[0] if isinstance(logits, (tuple, list)) else logits
        return val_scores(logits)

    steps_per_epoch = math.ceil(len(ds["train"]) / args.batch_size)
    total_steps = steps_per_epoch * args.epochs
    ta_params = inspect.signature(TrainingArguments.__init__).parameters
    eval_key = "eval_strategy" if "eval_strategy" in ta_params else "evaluation_strategy"
    targs = TrainingArguments(
        output_dir=str(run_dir / "checkpoints"),
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
        remove_unused_columns=False,
        fp16=torch.cuda.is_available(),
        seed=seed,
        data_seed=seed,
        **{eval_key: "epoch"},
    )
    trainer = MaskedBCETrainer(
        model=model, args=targs, train_dataset=ds["train"], eval_dataset=ds["validation"],
        data_collator=collator, compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=args.patience)],
        pos_weight=pos_weight,
    )
    t0 = time.time()
    trainer.train()
    train_secs = time.time() - t0

    # Reload the best checkpoint with from_pretrained (applies the LayerNorm gamma/beta renaming that
    # Trainer's own load_best_model_at_end skips in Transformers 5.x) and predict with THAT model.
    best_ckpt = trainer.state.best_model_checkpoint
    best_model = AutoModelForSequenceClassification.from_pretrained(best_ckpt)
    logits = {s: predict_logits(best_model, ds[s], collator) for s in ["validation", "test"]}
    probs = {s: sigmoid(logits[s]) for s in logits}

    reloaded = val_scores(logits["validation"])["macro_f1"]
    logged = trainer.state.best_metric
    if logged is not None and abs(reloaded - logged) > 2e-3:
        print(f"WARNING seed {seed}: reloaded best-checkpoint val macro F1 {reloaded:.4f} != logged {logged:.4f}")
    else:
        print(f"seed {seed}: best checkpoint reload reproduces logged val macro F1 ({reloaded:.4f})")

    thresholds = tune_thresholds_masked(raw["validation"]["y"], probs["validation"],
                                        raw["validation"]["mask"], args.min_threshold_support)
    result = {"seed": seed, "train_seconds": round(train_secs, 1), "best_checkpoint": str(best_ckpt),
              "best_val_metric_logged": logged, "best_val_metric_reloaded": reloaded,
              "select_metric": args.select_metric,
              "thresholds_val_tuned": dict(zip(label_names, thresholds.round(2).tolist())),
              "epochs_logged": [h for h in trainer.state.log_history if "eval_macro_f1" in h]}
    for s in ["validation", "test"]:
        result[s] = {"fixed_0.5": evaluate_block(raw[s], probs[s], 0.5, label_names),
                     "val_tuned": evaluate_block(raw[s], probs[s], thresholds, label_names)}
        np.save(run_dir / f"{s}_probs.npy", probs[s])
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    if args.save_best_model:
        best_model.save_pretrained(run_dir / "best_model")
        tokenizer.save_pretrained(run_dir / "best_model")
    shutil.rmtree(run_dir / "checkpoints", ignore_errors=True)  # keep Drive/disk small
    del trainer, best_model, model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return result


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="check the masked-loss maths and exit")
    ap.add_argument("--data-dir", type=Path, default=Path("."))
    ap.add_argument("--label-map", type=Path, default=Path("opp115_label_map.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("bert_combined_runs"))
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
    ap.add_argument("--select-metric", choices=["masked_all", "opp115"], default="masked_all")
    ap.add_argument("--min-threshold-support", type=int, default=10)
    ap.add_argument("--save-best-model", action="store_true", help="keep each seed's best model (~440 MB each)")
    ap.add_argument("--no-split-check", action="store_true")
    ap.add_argument("--max-train-samples", type=int, default=None, help="smoke test only")
    ap.add_argument("--max-eval-samples", type=int, default=None, help="smoke test only")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return

    label_map = json.loads(args.label_map.read_text())
    label_names = [label_map[str(i)] for i in range(len(label_map))]
    raw = {s: load_split(args.data_dir / f"combined_{s}.jsonl") for s in ["train", "validation", "test"]}
    subsampled = bool(args.max_train_samples or args.max_eval_samples)
    check_data(raw, label_names, check_sizes=not (args.no_split_check or subsampled))
    if subsampled:
        raw["train"] = subsample(raw["train"], args.max_train_samples)
        raw["validation"] = subsample(raw["validation"], args.max_eval_samples)
        raw["test"] = subsample(raw["test"], args.max_eval_samples)

    pos_weight = make_pos_weight(raw["train"]["y"], raw["train"]["mask"], args.pos_weight)
    if pos_weight is not None:
        print("pos_weight per label (valid rows only):",
              dict(zip(label_names, pos_weight.round(1).tolist())))
    print("valid training entries per label:",
          dict(zip(label_names, raw["train"]["mask"].sum(0).astype(int).tolist())))

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    collator = MaskedCollator(tokenizer)
    ds = {s: SegmentDataset(raw[s], tokenizer, args.max_length) for s in raw}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "config.json").write_text(json.dumps(
        {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}, indent=2))
    with (args.out_dir / "test_meta.jsonl").open("w") as f:  # row order of test_probs.npy, for paired bootstrap
        for pid, src in zip(raw["test"]["policy"], raw["test"]["src"]):
            f.write(json.dumps({"policy_id": pid, "source": str(src)}) + "\n")

    results = []
    for seed in [int(s) for s in args.seeds.split(",")]:
        print(f"\n{'=' * 70}\nSEED {seed}\n{'=' * 70}")
        run_dir = args.out_dir / f"seed_{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        results.append(run_one(seed, args, raw, ds, label_names, tokenizer, collator, pos_weight, run_dir))

    # ---- summary ----
    def get(r, block, thr="fixed_0.5"):  # test-set macro F1 for one seed
        return r["test"][thr][block]["macro_f1"]

    print(f"\n{'=' * 78}\nSUMMARY (macro F1; every class scored only where it is annotated)\n{'=' * 78}")
    print(f"{'run':<14}{'val(select)':>12}{'OPP test@.5':>13}{'OPP tuned':>11}{'APP FP/TP@.5':>14}{'masked-all@.5':>15}")
    for r in results:
        print(f"{'seed ' + str(r['seed']):<14}{r['best_val_metric_reloaded']:>12.4f}"
              f"{get(r, 'opp115_10class'):>13.4f}"
              f"{get(r, 'opp115_10class', 'val_tuned'):>11.4f}"
              f"{get(r, 'app350_first_third_only'):>14.4f}"
              f"{get(r, 'masked_all'):>15.4f}")
    opp = np.array([get(r, "opp115_10class") for r in results])
    app = np.array([get(r, "app350_first_third_only") for r in results])
    oppt = np.array([get(r, "opp115_10class", "val_tuned") for r in results])
    print(f"{'mean':<14}{'':>12}{opp.mean():>13.4f}{oppt.mean():>11.4f}{app.mean():>14.4f}")
    print(f"{'std':<14}{'':>12}{opp.std():>13.4f}{oppt.std():>11.4f}{app.std():>14.4f}")
    print("\nReference (OPP-115 test rows, 10-class macro F1):")
    for k, v in REFERENCE.items():
        print(f"  {k:<34}{v:.4f}   -> this run {opp.mean() - v:+.4f}")

    print("\nPer-class test F1, mean over seeds, threshold 0.5")
    for block, title in [("opp115_10class", "OPP-115 test rows"), ("app350_first_third_only", "APP-350 test rows (annotated labels only)")]:
        print(f"  [{title}]")
        for n in label_names:
            if n not in results[0]["test"]["fixed_0.5"][block]["per_class"]:
                continue
            f1 = np.mean([r["test"]["fixed_0.5"][block]["per_class"][n]["f1"] for r in results])
            sup = results[0]["test"]["fixed_0.5"][block]["per_class"][n]["support"]
            print(f"    {n:<40} F1 {f1:.2f}   (support {sup})")
    print("\nCaution: 18 OPP-115 test policies and tiny classes (Do Not Track support=5) make gaps under ~0.02 "
          "macro F1 indistinguishable from seed noise. Judge by the mean over seeds; use paired_bootstrap.py "
          "with test_meta.jsonl + seed_*/test_probs.npy for a confidence interval.")

    (args.out_dir / "summary.json").write_text(json.dumps({
        "reference": REFERENCE,
        "opp115_test_macro_f1_fixed_0.5": {"mean": float(opp.mean()), "std": float(opp.std()), "per_seed": opp.tolist()},
        "opp115_test_macro_f1_val_tuned": {"mean": float(oppt.mean()), "std": float(oppt.std()), "per_seed": oppt.tolist()},
        "app350_first_third_macro_f1_fixed_0.5": {"mean": float(app.mean()), "std": float(app.std()), "per_seed": app.tolist()},
    }, indent=2))


if __name__ == "__main__":
    main()
