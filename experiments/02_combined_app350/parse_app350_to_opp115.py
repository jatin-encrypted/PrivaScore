"""
parse_app350_to_opp115.py — Convert the RAW APP-350 YAML annotations into
OPP-115-compatible canonical records, using only the semantically-justified
mapping approved for this project:

    *_1stParty  ->  First Party Collection/Use
    *_3rdParty  ->  Third Party Sharing/Collection

PERFORMED and NOT_PERFORMED are treated as the SAME topic label (this is a
topic classifier, not a stance classifier) — but the original modality is
never discarded. It's preserved per-practice in a `modality_detail` field on
every record, so nothing about the raw annotation is lost, only re-labeled.

EXCLUDED (documented, not silently dropped):
  - Segments with no annotation at all (nothing to map)
  - Segments whose ONLY practices are SSO / Facebook_SSO (no party suffix —
    genuinely ambiguous whether this is 1st-party receipt or 3rd-party
    sharing; forcing a side would be an invented mapping)
  - The other 8 OPP-115 categories (Data Retention, Data Security, User
    Choice/Control, Policy Change, Do Not Track, International Audiences,
    Other): APP-350's annotation scheme has no field that speaks to these
    at all, confirmed against the full 58-practice list, so no segment can
    ever carry these labels regardless of how it's parsed.

OUTPUT SCHEMA (one JSON object per line):
{
  "policy_id": "app350_101",
  "segment_id": 38,
  "text": "...",
  "labels": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],          # 10-dim multi-hot, OPP-115 order
  "label_names": ["First Party Collection/Use"],
  "source": "app350",
  "contains_synthetic": false,                        # policy-level flag from APP-350
  "modality_detail": [
    {"practice": "Contact_Phone_Number_1stParty",
     "opp115_category": "First Party Collection/Use",
     "modality": "NOT_PERFORMED"}
  ]
}

USAGE
-----
  python parse_app350_to_opp115.py --corpus-dir /path/to/APP-350_v1.1 \
      --label-map opp115_label_map.json --out app350_mapped.jsonl
"""
import argparse
import glob
import json
import os
import re
from pathlib import Path

import yaml

TAG_RE = re.compile(r"<[^>]+>")


def clean_text(raw: str) -> str:
    text = TAG_RE.sub(" ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def practice_to_category(practice: str):
    """Return the OPP-115 category for a practice string, or None if excluded."""
    if practice.endswith("_1stParty"):
        return "First Party Collection/Use"
    if practice.endswith("_3rdParty"):
        return "Third Party Sharing/Collection"
    return None  # SSO / Facebook_SSO — excluded, ambiguous


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", required=True, type=Path,
                     help="Path to extracted APP-350_v1.1/ folder (must contain annotations/)")
    ap.add_argument("--label-map", required=True, type=Path)
    ap.add_argument("--out", default="app350_mapped.jsonl", type=Path)
    ap.add_argument("--policy-meta-out", default="app350_policy_meta.json", type=Path,
                     help="Per-policy metadata (policy_type, contains_synthetic) for later split design")
    args = ap.parse_args()

    label_map = json.loads(args.label_map.read_text())
    label_to_id = {v: int(k) for k, v in label_map.items()}
    n_labels = len(label_to_id)

    annotation_dir = args.corpus_dir / "annotations"
    files = sorted(glob.glob(os.path.join(annotation_dir, "*.yml")))
    print(f"Found {len(files)} APP-350 policy files.")

    n_total_segments = 0
    n_unannotated = 0
    n_sso_only_excluded = 0
    n_mapped = 0
    policy_meta = {}

    with args.out.open("w", encoding="utf-8") as out_f:
        for fn in files:
            doc = yaml.safe_load(open(fn, encoding="utf-8"))
            policy_id = f"app350_{doc['policy_id']}"
            policy_meta[policy_id] = {
                "policy_name": doc.get("policy_name"),
                "official_policy_type": doc.get("policy_type"),
                "contains_synthetic": bool(doc.get("contains_synthetic", False)),
            }

            for seg in doc["segments"]:
                n_total_segments += 1
                annos = seg["annotations"]
                if not annos:
                    n_unannotated += 1
                    continue

                modality_detail = []
                categories_hit = set()
                for ann in annos:
                    cat = practice_to_category(ann["practice"])
                    if cat is None:
                        continue  # SSO/Facebook_SSO practice within this annotation — skip this one label
                    modality_detail.append({
                        "practice": ann["practice"],
                        "opp115_category": cat,
                        "modality": ann["modality"],
                    })
                    categories_hit.add(cat)

                if not categories_hit:
                    # Every annotation on this segment was SSO/Facebook_SSO
                    n_sso_only_excluded += 1
                    continue

                text = clean_text(seg["segment_text"])
                if not text:
                    continue

                multi_hot = [0] * n_labels
                for cat in categories_hit:
                    multi_hot[label_to_id[cat]] = 1

                record = {
                    "policy_id": policy_id,
                    "segment_id": seg["segment_id"],
                    "text": text,
                    "labels": multi_hot,
                    "label_names": sorted(categories_hit),
                    "source": "app350",
                    "contains_synthetic": policy_meta[policy_id]["contains_synthetic"],
                    "modality_detail": modality_detail,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                n_mapped += 1

    args.policy_meta_out.write_text(json.dumps(policy_meta, indent=2))

    print(f"\nTotal segments scanned: {n_total_segments}")
    print(f"Unannotated (excluded): {n_unannotated}")
    print(f"SSO/Facebook_SSO-only (excluded): {n_sso_only_excluded}")
    print(f"Mapped and written: {n_mapped} -> {args.out}")
    print(f"Policy metadata -> {args.policy_meta_out}")


if __name__ == "__main__":
    main()
