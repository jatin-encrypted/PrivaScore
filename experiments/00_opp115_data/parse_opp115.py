"""
parse_opp115.py — Convert the raw OPP-115 corpus into a clean, multi-label
JSONL dataset ready for HuggingFace Trainer ingestion.

WHY THIS SCRIPT EXISTS
-----------------------
The OPP-115 corpus is NOT distributed as JSON. It's distributed as:

  annotations/<policy>.csv        - one row per practice, 3 annotators overlaid
  consolidation/threshold-*.csv   - same rows, de-duplicated across annotators
  sanitized_policies/<policy>.html - segment text, "|||"-delimited

Each row's category (column F) is one of the 10 OPP-115 categories.
A single policy *segment* (roughly a paragraph) can have MULTIPLE practices
attached to it — from one or more annotators — which is exactly what makes
this a multi-label classification problem: one text segment -> a set of
category labels.

This script:
  1. Reads segment text from sanitized_policies/<policy>.html (split on "|||")
  2. Reads consolidated annotations (default: threshold-0.75 — this is the
     convergence threshold the original OPP-115 paper reports results at,
     and it balances removing annotator noise vs. losing real disagreement)
  3. Groups practices by (policy_id, segment_id) -> unique set of categories
  4. Strips leftover HTML tags/entities from segment text
  5. Writes one JSON object per line: {policy_id, segment_id, text, labels}
  6. Also writes label_map.json (id <-> category name) for the Trainer config

USAGE
-----
  python parse_opp115.py --corpus-dir /path/to/OPP-115 --out opp115_clean.jsonl

  # use a different consolidation threshold
  python parse_opp115.py --corpus-dir /path/to/OPP-115 --threshold 0.5

NOTE ON GETTING THE CORPUS
---------------------------
Official source (cite it in any report that uses it):
  https://www.usableprivacy.org/static/data/OPP-115_v1_0.zip  (94.5 MB)
Unzip it and point --corpus-dir at the extracted OPP-115/ folder. Run on that
zip and followed by split_and_encode.py, this reproduces data/opp115/ exactly.
"""

import argparse
import csv
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

CATEGORIES = [
    "First Party Collection/Use",
    "Third Party Sharing/Collection",
    "User Choice/Control",
    "User Access, Edit and Deletion",
    "Data Retention",
    "Data Security",
    "Policy Change",
    "Do Not Track",
    "International and Specific Audiences",
    "Other",
]
# The corpus itself uses slightly inconsistent naming for a couple of
# categories across releases/mirrors — normalize on ingest.
CATEGORY_ALIASES = {
    "User Access": "User Access, Edit and Deletion",
    "User Access, Edit, and Deletion": "User Access, Edit and Deletion",
    "International and Specific Audiences": "International and Specific Audiences",
    "International & Specific Audiences": "International and Specific Audiences",
}

TAG_RE = re.compile(r"<[^>]+>")


def clean_text(raw: str) -> str:
    text = html.unescape(raw)
    text = TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_segments(sanitized_dir: Path, base_name: str) -> list[str]:
    path = sanitized_dir / f"{base_name}.html"
    raw = path.read_text(encoding="utf-8", errors="replace")
    return [clean_text(seg) for seg in raw.split("|||")]


def load_labels(csv_path: Path) -> dict[int, set[str]]:
    """segment_id -> set of category names for one policy's annotation file."""
    labels_by_segment: dict[int, set[str]] = defaultdict(set)
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 6:
                continue
            try:
                segment_id = int(row[4])
            except ValueError:
                continue
            category = row[5].strip()
            category = CATEGORY_ALIASES.get(category, category)
            if category not in CATEGORIES:
                # Unrecognized category string (rare malformed row) — skip.
                continue
            labels_by_segment[segment_id].add(category)
    return labels_by_segment


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-dir", required=True, type=Path, help="Path to extracted OPP-115/ folder")
    ap.add_argument("--threshold", default="0.75", choices=["0.5", "0.75", "1.0"],
                     help="Consolidation convergence threshold to use (default: 0.75, matches the paper)")
    ap.add_argument("--out", default="opp115_clean.jsonl", type=Path)
    ap.add_argument("--label-map-out", default="opp115_label_map.json", type=Path)
    args = ap.parse_args()

    consolidation_dir = args.corpus_dir / "consolidation" / f"threshold-{args.threshold}-overlap-similarity"
    sanitized_dir = args.corpus_dir / "sanitized_policies"

    if not consolidation_dir.exists():
        sys.exit(f"Not found: {consolidation_dir}")
    if not sanitized_dir.exists():
        sys.exit(f"Not found: {sanitized_dir}")

    csv_files = sorted(consolidation_dir.glob("*.csv"))
    print(f"Found {len(csv_files)} policy annotation files.")

    n_segments_written = 0
    n_segments_no_label = 0
    label_counts = defaultdict(int)

    with args.out.open("w", encoding="utf-8") as out_f:
        for csv_path in csv_files:
            base_name = csv_path.stem
            try:
                segments = load_segments(sanitized_dir, base_name)
            except FileNotFoundError:
                print(f"  WARN: no sanitized text for {base_name}, skipping")
                continue

            labels_by_segment = load_labels(csv_path)

            for seg_id, text in enumerate(segments):
                if not text:
                    continue
                labels = sorted(labels_by_segment.get(seg_id, []))
                if not labels:
                    # Segment with no annotated practice at all (rare, but
                    # real — usually boilerplate/whitespace). Skip rather
                    # than force an "Other" label that wasn't actually chosen.
                    n_segments_no_label += 1
                    continue
                for lab in labels:
                    label_counts[lab] += 1
                record = {
                    "policy_id": base_name,
                    "segment_id": seg_id,
                    "text": text,
                    "labels": labels,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                n_segments_written += 1

    label_map = {i: cat for i, cat in enumerate(CATEGORIES)}
    args.label_map_out.write_text(json.dumps(label_map, indent=2))

    print(f"\nWrote {n_segments_written} labeled segments -> {args.out}")
    print(f"Skipped {n_segments_no_label} segments with no annotated practice.")
    print(f"Label map -> {args.label_map_out}")
    print("\nPer-category segment counts (a segment can count toward multiple categories):")
    for cat in CATEGORIES:
        print(f"  {cat:45s} {label_counts.get(cat, 0)}")


if __name__ == "__main__":
    main()
