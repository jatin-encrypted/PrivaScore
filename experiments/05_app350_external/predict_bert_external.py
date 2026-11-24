"""
predict_bert_external.py - score the APP-350 external evaluation set with the
THREE EXISTING best BERT checkpoints (seeds 42, 43, 44). No training happens.

RUN ON THE GPU MACHINE (Colab), then upload only the small output files.

What it does
  1. For each seed: finds the best checkpoint recorded in seed_X/result.json
     (only the corrected run writes that field) and loads it with
     from_pretrained (this applies the LayerNorm gamma/beta renaming correctly).
  2. SANITY GATE: re-scores the OPP-115 test split with the same code path and
     checks the 10-class macro F1 @0.5 against the value stored in result.json
     (0.7591 / 0.7620 / 0.7785). If it differs by > 0.003 the script stops, so a
     wrongly-loaded checkpoint can never produce APP-350 numbers.
  3. Writes sigmoid probabilities (n x 10) for the APP-350 eval set. The
     evaluation script only reads columns 0 (First Party) and 1 (Third Party);
     the other 8 outputs are ignored and no 10-class APP-350 score exists.
  4. Records the eval-set sha256, so the evaluation script can refuse mismatched
     row order.

Colab usage
  from google.colab import drive; drive.mount('/content/drive')
  # upload to /content: app350_external_eval.jsonl, opp115_test.jsonl, this script
  !pip -q install "transformers>=4.40" accelerate scikit-learn
  !python predict_bert_external.py \
      --eval-set app350_external_eval.jsonl --opp115-test opp115_test.jsonl \
      --runs-dir /content/drive/MyDrive/PrivaScore/bert_runs --out-dir bert_external
  # then download the bert_external/ folder (7 small files, well under 1 MB total)
"""
import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score
from torch.utils.data import Dataset
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          DataCollatorWithPadding, Trainer, TrainingArguments)


class TextDataset(Dataset):
    def __init__(self, texts, tokenizer, max_length):
        self.enc = tokenizer(texts, truncation=True, max_length=max_length)  # dynamic padding happens in the collator

    def __len__(self):
        return len(self.enc["input_ids"])

    def __getitem__(self, i):
        return {k: v[i] for k, v in self.enc.items()}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def resolve_checkpoint(runs_dir: Path, seed: int):
    sd = runs_dir / f"seed_{seed}"
    info = json.loads((sd / "result.json").read_text())
    if "best_checkpoint" not in info:
        raise SystemExit(f"seed_{seed}/result.json has no 'best_checkpoint': this is not the corrected run.")
    ck = sd / "checkpoints" / Path(info["best_checkpoint"]).name
    if not ck.exists():
        raise SystemExit(f"best checkpoint folder not found: {ck}")
    return ck, info


def predict_probs(ckpt: Path, texts, tokenizer, max_length, tmp_dir):
    model = AutoModelForSequenceClassification.from_pretrained(str(ckpt))
    args = TrainingArguments(output_dir=str(tmp_dir), per_device_eval_batch_size=64,
                             fp16=torch.cuda.is_available(), report_to="none")
    trainer = Trainer(model=model, args=args, data_collator=DataCollatorWithPadding(tokenizer))
    probs = sigmoid(trainer.predict(TextDataset(texts, tokenizer, max_length)).predictions)
    del trainer, model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return probs.astype("float32")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-set", type=Path, required=True)
    ap.add_argument("--opp115-test", type=Path, required=True)
    ap.add_argument("--runs-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("bert_external"))
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--tokenizer", default="bert-base-uncased")
    ap.add_argument("--sanity-tol", type=float, default=0.003)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(args.tokenizer)
    eval_rows = [json.loads(l) for l in args.eval_set.read_text().splitlines() if l.strip()]
    eval_texts = [r["text"] for r in eval_rows]
    sha = hashlib.sha256(args.eval_set.read_bytes()).hexdigest()
    opp = [json.loads(l) for l in args.opp115_test.read_text().splitlines() if l.strip()]
    opp_texts = [r["text"] for r in opp]
    opp_y = np.array([r["labels"] for r in opp], dtype=int)
    print(f"eval set: {len(eval_rows)} segments, sha256 {sha[:16]}...; OPP-115 test: {len(opp)} segments")

    meta = {"eval_set_sha256": sha, "n_rows": len(eval_rows), "max_length": args.max_length,
            "tokenizer": args.tokenizer, "opp115_sanity": {}, "checkpoints": {},
            "versions": {p: version(p) for p in ("torch", "transformers")}}
    for seed in [int(s) for s in args.seeds.split(",")]:
        ckpt, info = resolve_checkpoint(args.runs_dir, seed)
        print(f"\n=== seed {seed}: {ckpt}")

        # sanity gate: same code path must reproduce the stored OPP-115 test macro F1
        opp_probs = predict_probs(ckpt, opp_texts, tok, args.max_length, args.out_dir / "tmp")
        rescored = float(f1_score(opp_y, (opp_probs >= 0.5).astype(int), average="macro", zero_division=0))
        stored = float(info["test"]["fixed_0.5"]["macro_f1"])
        print(f"    OPP-115 test macro F1 @0.5: stored {stored:.4f}  rescored {rescored:.4f}")
        meta["opp115_sanity"][str(seed)] = {"stored": stored, "rescored": rescored}
        if abs(rescored - stored) > args.sanity_tol:
            raise SystemExit(f"SANITY GATE FAILED for seed {seed}: |{rescored:.4f} - {stored:.4f}| > {args.sanity_tol}. "
                             "Checkpoint or preprocessing differs from the training run; not producing APP-350 numbers.")

        probs = predict_probs(ckpt, eval_texts, tok, args.max_length, args.out_dir / "tmp")
        assert probs.shape == (len(eval_rows), 10), probs.shape
        np.save(args.out_dir / f"bert_external_probs_seed_{seed}.npy", probs)
        meta["checkpoints"][str(seed)] = str(ckpt)
        print(f"    wrote bert_external_probs_seed_{seed}.npy {probs.shape}")

    (args.out_dir / "bert_external_meta.json").write_text(json.dumps(meta, indent=2))
    print("\nDONE. Download the bert_external/ folder (the tmp/ subfolder is not needed) and upload it.")


if __name__ == "__main__":
    main()
