"""
build_app350_eval_set.py - build the APP-350 EXTERNAL evaluation set for the
OPP-115-trained classifiers (TF-IDF + BERT), First Party / Third Party only.

OPERATIONAL MAPPING (documented approach; NOT a claim the schemes are equal)
  APP-350 practice ending _1stParty -> evaluated as "First Party Collection/Use"
  APP-350 practice ending _3rdParty -> evaluated as "Third Party Sharing/Collection"
  PERFORMED and NOT_PERFORMED both count as positive (topic classification);
  the modality is kept as metadata, never dropped.

  Known scope differences (why this is an operational mapping):
   * APP-350 "third party" = ad-network / analytics SDKs only (annotator
     instructions); OPP-115 Third Party also covers affiliates, partners, etc.
     A model that correctly flags a partner-sharing sentence as Third Party is
     marked WRONG here. Third Party precision is therefore a LOWER BOUND.
   * APP-350 only annotates 58 specific data-type practices. First-party
     collection of other data types is simply not annotated.

WHICH SEGMENTS ARE EVALUATED
  * Only the 52 held-out APP-350 test policies from our combined split
    (non-synthetic pool, seed 42). Re-derived here from the raw YAML, then
    cross-checked against combined_test.jsonl.
  * Unannotated segments: EXCLUDED (not treated as negatives).
  * SSO / Facebook_SSO-only segments: EXCLUDED (ambiguous party; as documented).
  * Remaining segments carry >= 1 annotated 1st/3rd-party practice. Within these,
    a category is positive iff a practice of that party is annotated; otherwise
    it is scored negative (closed world WITHIN annotated segments only).
    RECALL needs no negatives at all, so it is assumption-free; PRECISION / F1
    depend on this within-segment closed-world assumption.

USAGE
  python build_app350_eval_set.py --app350-dir APP-350_v1.1 --outputs-dir outputs --out-dir .
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

TAG_RE = re.compile(r"<[^>]+>")
ENTITY_RE = re.compile(r"&(?:[a-zA-Z]+|#\d+);")


def clean_text(raw: str) -> str:
    """Identical to parse_app350_to_opp115.clean_text (the documented preprocessing)."""
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", raw)).strip()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app350-dir", type=Path, required=True)
    ap.add_argument("--outputs-dir", type=Path, default=Path("outputs"),
                    help="folder with split_combined.py, combined_*.jsonl, opp115_*.jsonl")
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    sys.path.insert(0, str(args.outputs_dir))
    from split_combined import split_app350  # the exact split function used for the combined dataset

    docs = {}
    for fn in sorted(glob.glob(os.path.join(args.app350_dir, "annotations", "*.yml"))):
        d = yaml.safe_load(open(fn, encoding="utf-8"))
        docs[f"app350_{d['policy_id']}"] = d
    meta = {pid: {"contains_synthetic": bool(d.get("contains_synthetic", False))} for pid, d in docs.items()}
    split = split_app350(meta, seed=args.seed)
    test_pols, train_pols, val_pols = split["test"], split["train"], split["validation"]

    checks = {}
    checks["n_test_policies"] = len(test_pols)
    checks["test_policies_synthetic_flagged"] = sum(meta[p]["contains_synthetic"] for p in test_pols)
    checks["test_disjoint_from_train_val"] = not (test_pols & (train_pols | val_pols))
    assert len(test_pols) == 52, len(test_pols)
    assert checks["test_policies_synthetic_flagged"] == 0
    assert checks["test_disjoint_from_train_val"]

    # ---- independent re-derivation of labels from raw annotations
    rows, c = [], Counter()
    seen_policy_with_rows = set()
    for pid in sorted(test_pols):
        for seg in docs[pid]["segments"]:
            c["segments_total"] += 1
            annos = seg["annotations"]
            if not annos:
                c["excluded_unannotated"] += 1
                continue
            mods = {"first": set(), "third": set()}
            other = 0
            for a in annos:
                p = a["practice"]
                if p.endswith("_1stParty"):
                    mods["first"].add(a["modality"])
                elif p.endswith("_3rdParty"):
                    mods["third"].add(a["modality"])
                else:
                    other += 1
            if not mods["first"] and not mods["third"]:
                c["excluded_sso_only"] += 1
                continue
            text = clean_text(seg["segment_text"])
            if not text:
                c["excluded_empty_text"] += 1
                continue
            rows.append({
                "policy_id": pid, "segment_id": seg["segment_id"], "text": text,
                "y_first": int(bool(mods["first"])), "y_third": int(bool(mods["third"])),
                "modality_first": sorted(mods["first"]), "modality_third": sorted(mods["third"]),
                "also_has_sso_annotation": bool(other),
            })
            seen_policy_with_rows.add(pid)
    c["segments_evaluated"] = len(rows)

    # ---- cross-check against the documented artifact (combined_test.jsonl, source=app350)
    art = [json.loads(l) for l in (args.outputs_dir / "combined_test.jsonl").read_text().splitlines() if l.strip()]
    art = [r for r in art if r["source"] == "app350"]
    key = lambda pid, t, a, b: (pid, t, int(a), int(b))
    mine = Counter(key(r["policy_id"], r["text"], r["y_first"], r["y_third"]) for r in rows)
    theirs = Counter(key(r["policy_id"], r["text"], r["labels"][0], r["labels"][1]) for r in art)
    checks["rows_match_combined_test_artifact"] = (mine == theirs)
    checks["n_rows_mine_vs_artifact"] = [sum(mine.values()), sum(theirs.values())]
    checks["artifact_rows_with_other_labels_set"] = sum(any(r["labels"][2:]) for r in art)
    checks["artifact_policies_subset_of_test_split"] = {r["policy_id"] for r in art} <= test_pols
    assert checks["rows_match_combined_test_artifact"], "re-derived eval set != combined_test.jsonl app350 rows"

    # ---- preprocessing consistency: HTML entities / tags that clean_text does not touch
    raw_entities = sum(bool(ENTITY_RE.search(seg["segment_text"])) for pid in test_pols for seg in docs[pid]["segments"])
    raw_tags = sum(bool(TAG_RE.search(seg["segment_text"])) for pid in test_pols for seg in docs[pid]["segments"])
    checks["raw_segments_with_html_entities"] = raw_entities
    checks["raw_segments_with_html_tags"] = raw_tags
    checks["note_preprocessing"] = ("APP-350 text uses the documented clean_text (tag strip + whitespace). "
                                    "OPP-115 training text additionally went through html.unescape; "
                                    "only matters if entities are present (count above).")

    # ---- leakage vs OPP-115 (the only data the models were trained on)
    opp = {s: [json.loads(l) for l in (args.outputs_dir / f"opp115_{s}.jsonl").read_text().splitlines() if l.strip()]
           for s in ("train", "validation", "test")}
    opp_all_norm = {norm(r["text"]) for s in opp for r in opp[s]}
    opp_train_norm = {norm(r["text"]) for r in opp["train"]}
    dup_any = [r for r in rows if norm(r["text"]) in opp_all_norm]
    dup_train = [r for r in rows if norm(r["text"]) in opp_train_norm]
    checks["eval_segments_exact_duplicate_of_any_opp115_segment"] = len(dup_any)
    checks["eval_segments_exact_duplicate_of_opp115_TRAIN_segment"] = len(dup_train)
    opp_sites = {re.sub(r"[^a-z0-9]", "", pid.split("_", 1)[-1].split(".")[0].lower()) for pid in {r["policy_id"] for s in opp for r in opp[s]}}
    app_names = {pid: re.sub(r"[^a-z0-9]", "", str(docs[pid]["policy_name"]).lower()) for pid in test_pols}
    overlap = sorted((pid, docs[pid]["policy_name"]) for pid, n in app_names.items() if n and n in opp_sites)
    checks["test_policy_names_matching_an_opp115_site_name"] = [f"{p} ({n})" for p, n in overlap]

    # ---- stats for the report
    pols_eval = sorted({r["policy_id"] for r in rows})
    seg_per_pol = Counter(r["policy_id"] for r in rows)
    stats = {
        "test_policies_in_split": len(test_pols),
        "policies_with_>=1_evaluable_segment": len(pols_eval),
        "segments": dict(c),
        "positives": {
            "first_party": sum(r["y_first"] for r in rows),
            "third_party": sum(r["y_third"] for r in rows),
            "both": sum(r["y_first"] and r["y_third"] for r in rows),
            "first_only": sum(r["y_first"] and not r["y_third"] for r in rows),
            "third_only": sum(r["y_third"] and not r["y_first"] for r in rows),
        },
        "negatives_within_annotated_segments": {
            "first_party": sum(1 - r["y_first"] for r in rows),
            "third_party": sum(1 - r["y_third"] for r in rows),
        },
        "positives_by_modality": {
            cat: dict(Counter("+".join(r[f"modality_{cat}"]) for r in rows if r[f"y_{cat}"]))
            for cat in ("first", "third")
        },
        "segments_per_policy": {"min": min(seg_per_pol.values()), "median": sorted(seg_per_pol.values())[len(seg_per_pol) // 2],
                                "max": max(seg_per_pol.values())},
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "app350_external_eval.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    manifest = {"eval_set_file": out.name, "eval_set_sha256": sha, "n_rows": len(rows),
                "stats": stats, "checks": checks, "seed": args.seed}
    (args.out_dir / "app350_external_eval_manifest.json").write_text(json.dumps(manifest, indent=2))

    print(json.dumps({"stats": stats, "checks": checks}, indent=2))
    print(f"\nwrote {out} ({len(rows)} rows, sha256 {sha[:16]}...)")


if __name__ == "__main__":
    main()
