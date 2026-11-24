"""
split_and_encode.py — Turn opp115_clean.jsonl into train/val/test splits with
multi-hot label vectors, ready for `datasets.Dataset` + HF Trainer.

Splits by POLICY, not by segment. If you split by segment, segments from the
same privacy policy leak into both train and test (they share vocabulary,
company name, boilerplate structure) and your F1 will look better than the
model actually is. Splitting by policy is what makes the eval trustworthy.

Usage:
  python split_and_encode.py --in opp115_clean.jsonl --label-map opp115_label_map.json
"""
import argparse
import json
import random
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="opp115_clean.jsonl", type=Path)
    ap.add_argument("--label-map", default="opp115_label_map.json", type=Path)
    ap.add_argument("--out-dir", default=".", type=Path)
    ap.add_argument("--seed", default=42, type=int)
    args = ap.parse_args()

    label_map = json.loads(args.label_map.read_text())
    label_to_id = {v: int(k) for k, v in label_map.items()}
    n_labels = len(label_to_id)

    records = [json.loads(l) for l in args.inp.read_text().splitlines() if l.strip()]

    policies = sorted({r["policy_id"] for r in records})
    rng = random.Random(args.seed)
    rng.shuffle(policies)

    n = len(policies)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    train_policies = set(policies[:n_train])
    val_policies = set(policies[n_train:n_train + n_val])
    test_policies = set(policies[n_train + n_val:])

    splits = {"train": [], "validation": [], "test": []}
    for r in records:
        multi_hot = [0] * n_labels
        for lab in r["labels"]:
            multi_hot[label_to_id[lab]] = 1
        out_rec = {"text": r["text"], "labels": multi_hot, "policy_id": r["policy_id"]}
        if r["policy_id"] in train_policies:
            splits["train"].append(out_rec)
        elif r["policy_id"] in val_policies:
            splits["validation"].append(out_rec)
        else:
            splits["test"].append(out_rec)

    for name, rows in splits.items():
        out_path = args.out_dir / f"opp115_{name}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{name:12s} {len(rows):5d} segments  -> {out_path}")

    print(f"\nPolicy split -> train {len(train_policies)} / val {len(val_policies)} / test {len(test_policies)}")
    print("\nLoad in HF Trainer with:")
    print("""
from datasets import load_dataset
ds = load_dataset("json", data_files={
    "train": "opp115_train.jsonl",
    "validation": "opp115_validation.jsonl",
    "test": "opp115_test.jsonl",
})
# ds["train"][0] -> {"text": "...", "labels": [0,1,0,...,0], "policy_id": "..."}
# Cast labels to float for BCEWithLogitsLoss:
#   ds = ds.map(lambda x: {"labels": [float(v) for v in x["labels"]]})
""")


if __name__ == "__main__":
    main()
