"""
split_combined.py — Build the combined OPP-115 + APP-350 train/validation/test
splits, deliberately (not by merging each corpus's own official split).

SPLIT DESIGN (read this before running)
-----------------------------------------
1. OPP-115: reuse the EXACT SAME policy-level split already used for the
   OPP-115-only baseline (same seed=42, same 70/15/15 policy split -> 80
   train / 17 val / 18 test policies). This is deliberate: it means the
   OPP-115-only baseline (test macro F1 = 0.7273) and this combined
   experiment are evaluated on the IDENTICAL OPP-115 test policies. Any
   difference in the OPP-115 portion of the result is attributable to
   adding APP-350 training data, not to a different test set.

2. APP-350: split independently from OPP-115 (they're different corpora,
   different document IDs — no cross-source leakage is possible regardless
   of how each is split). But APP-350 needs a decision OPP-115 doesn't:
   142 of its 350 policies contain synthetically-generated segments
   (hand-edited negations of real segments, per APP-350's own README).
   APP-350's original creators put synthetic data ONLY in train/validation,
   never test - we follow the same principle and go further: our test
   split is drawn ONLY from the pool of policies with contains_synthetic
   = False (208 policies), so the combined test set never contains any
   artificially-edited text. Concretely:
     - test  (53 policies, ~15%): sampled only from the 208 non-synthetic policies
     - remaining 297 policies (142 synthetic-flagged + 155 non-synthetic)
       are split into train (245, ~70%) and validation (52, ~15%)

3. Both sources' splits are then concatenated: combined_train = OPP-115
   train segments + APP-350 train segments, and likewise for val/test.

WHY THIS AVOIDS LEAKAGE
-------------------------
- No policy ever appears in two splits (checked per source).
- OPP-115 and APP-350 policies cannot collide with each other - OPP-115
  policy_ids are website domains (e.g. "1017_sci-news.com"), APP-350's are
  numeric app-policy IDs from a completely different corpus of mobile app
  policies - there's no realistic mechanism for the same document to
  appear in both.
- No synthetic (artificially hand-edited) text reaches the test set from
  either source.

IS THE FINAL TEST SET A FAIR EVALUATION?
-------------------------------------------
Yes, with one caveat worth stating plainly: the test set's document mix
(OPP-115 websites vs APP-350 mobile-app policies) will not be 50/50 - it
reflects each corpus's own segment yield after mapping/consolidation, not
a deliberately balanced blend. This script reports the test set's source
breakdown explicitly so you can see exactly what's being evaluated, and
the baseline script below reports test macro F1 BOTH combined and split
by source, so a real regression in one source can't hide behind a good
score in the other.

USAGE
-----
  python split_combined.py \
      --opp115-clean opp115_clean.jsonl \
      --app350-mapped app350_mapped.jsonl \
      --app350-policy-meta app350_policy_meta.json \
      --label-map opp115_label_map.json \
      --out-dir /path/to/outputs
"""
import argparse
import json
import random
from pathlib import Path


def split_opp115(records, seed=42):
    """Identical logic to the original split_and_encode.py - same seed,
    same proportions - so the OPP-115 portion of every split is unchanged."""
    policies = sorted({r["policy_id"] for r in records})
    rng = random.Random(seed)
    rng.shuffle(policies)
    n = len(policies)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    return {
        "train": set(policies[:n_train]),
        "validation": set(policies[n_train:n_train + n_val]),
        "test": set(policies[n_train + n_val:]),
    }


def split_app350(policy_meta, seed=42):
    """Test drawn only from non-synthetic policies; synthetic-flagged
    policies can only land in train/validation."""
    all_policies = sorted(policy_meta.keys())
    non_synthetic = [p for p in all_policies if not policy_meta[p]["contains_synthetic"]]
    synthetic = [p for p in all_policies if policy_meta[p]["contains_synthetic"]]

    rng = random.Random(seed)
    rng.shuffle(non_synthetic)
    rng.shuffle(synthetic)

    n_total = len(all_policies)
    n_test = round(n_total * 0.15)
    if n_test > len(non_synthetic):
        raise SystemExit(f"Not enough non-synthetic APP-350 policies ({len(non_synthetic)}) "
                          f"for a synthetic-free test set of {n_test}.")

    test_policies = set(non_synthetic[:n_test])
    remaining_non_synth = non_synthetic[n_test:]
    remaining_pool = remaining_non_synth + synthetic
    rng.shuffle(remaining_pool)

    n_train = round(n_total * 0.70)
    train_policies = set(remaining_pool[:n_train])
    val_policies = set(remaining_pool[n_train:])

    return {"train": train_policies, "validation": val_policies, "test": test_policies}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opp115-clean", type=Path, required=True)
    ap.add_argument("--app350-mapped", type=Path, required=True)
    ap.add_argument("--app350-policy-meta", type=Path, required=True)
    ap.add_argument("--label-map", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    label_map = json.loads(args.label_map.read_text())
    label_to_id = {v: int(k) for k, v in label_map.items()}
    n_labels = len(label_to_id)

    opp_records = [json.loads(l) for l in args.opp115_clean.read_text().splitlines() if l.strip()]
    app_records = [json.loads(l) for l in args.app350_mapped.read_text().splitlines() if l.strip()]
    app_policy_meta = json.loads(args.app350_policy_meta.read_text())

    opp_split = split_opp115(opp_records, seed=args.seed)
    app_split = split_app350(app_policy_meta, seed=args.seed)

    print("=== OPP-115 policy split ===")
    for name in ["train", "validation", "test"]:
        print(f"  {name}: {len(opp_split[name])} policies")

    print("\n=== APP-350 policy split ===")
    for name in ["train", "validation", "test"]:
        n_synth_in_split = sum(1 for p in app_split[name] if app_policy_meta[p]["contains_synthetic"])
        print(f"  {name}: {len(app_split[name])} policies ({n_synth_in_split} contain synthetic segments)")

    splits = {"train": [], "validation": [], "test": []}
    for name in ["train", "validation", "test"]:
        fp_idx = label_to_id["First Party Collection/Use"]
        tp_idx = label_to_id["Third Party Sharing/Collection"]
        for r in opp_records:
            if r["policy_id"] in opp_split[name]:
                multi_hot = [0] * n_labels
                for lab in r["labels"]:
                    multi_hot[label_to_id[lab]] = 1
                splits[name].append({
                    "text": r["text"], "labels": multi_hot, "policy_id": r["policy_id"],
                    "source": "opp115", "contains_synthetic": False, "modality_detail": None,
                    # OPP-115 was annotated for all 10 categories - every label is a
                    # confirmed positive or negative, so all 10 are valid training targets.
                    "label_mask": [1] * n_labels,
                })
        for r in app_records:
            if r["policy_id"] in app_split[name]:
                # APP-350 was only ever annotated for First/Third Party. Its 0s on the
                # other 8 categories are "not annotated", not "confirmed absent" - so
                # only First/Third Party are valid training targets for these rows.
                # This is what makes the per-label-split fix (0.7243 macro F1) work,
                # and it generalizes directly to masked BCE loss for BERT fine-tuning.
                mask = [0] * n_labels
                mask[fp_idx] = 1
                mask[tp_idx] = 1
                splits[name].append({
                    "text": r["text"], "labels": r["labels"], "policy_id": r["policy_id"],
                    "source": "app350", "contains_synthetic": r["contains_synthetic"],
                    "modality_detail": r["modality_detail"],
                    "label_mask": mask,
                })

    print("\n=== Combined split composition (segments) ===")
    for name in ["train", "validation", "test"]:
        n_opp = sum(1 for r in splits[name] if r["source"] == "opp115")
        n_app = sum(1 for r in splits[name] if r["source"] == "app350")
        total = n_opp + n_app
        print(f"  {name:12s} total={total:5d}   opp115={n_opp:5d} ({100*n_opp/total:.1f}%)   "
              f"app350={n_app:5d} ({100*n_app/total:.1f}%)")

    for name in ["train", "validation", "test"]:
        out_path = args.out_dir / f"combined_{name}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for row in splits[name]:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Wrote {out_path}")

    # Leakage check: no policy_id in more than one split
    seen = {}
    leaks = []
    for name in ["train", "validation", "test"]:
        for r in splits[name]:
            pid = r["policy_id"]
            if pid in seen and seen[pid] != name:
                leaks.append((pid, seen[pid], name))
            seen[pid] = name
    print(f"\nLeakage check: {len(leaks)} policies found in multiple splits (should be 0)")
    if leaks:
        for l in leaks[:10]:
            print("  LEAK:", l)


if __name__ == "__main__":
    main()
