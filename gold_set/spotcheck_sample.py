"""Draw the reproducible spot-check sample of high-confidence (non-borderline) reference rows.

  .venv/bin/python -I gold_set/spotcheck_sample.py            # draw (only if no sample file exists)

Population: rows of labels_A1 with no `borderline` value that were still `pending` when the sample
was drawn. They are ordered by (policy_id, flag order in flag_definitions.json) and sampled with
random.Random(SEED). No extractor output is read, so the sample cannot be steered towards (or away
from) rows where an LLM disagrees. The population and sample are saved to
annotations/spotcheck_A1.json; re-running never redraws.
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED, N = 42, 25
OUT = HERE / "annotations" / "spotcheck_A1.json"


def main() -> int:
    if OUT.exists():
        print(f"{OUT.relative_to(HERE.parent)} already exists; not redrawing")
        return 0
    labels = json.loads((HERE / "annotations" / "labels_A1_resolved.json").read_text(encoding="utf-8"))["labels"]
    order = [f["id"] for f in json.loads((HERE / "flag_definitions.json").read_text())["flags"]]
    pop = sorted([x for x in labels if not x.get("borderline") and (x.get("review_status") or "pending") == "pending"],
                 key=lambda x: (x["policy_id"], order.index(x["flag"])))
    sample = sorted(random.Random(SEED).sample(pop, N), key=lambda x: (x["policy_id"], order.index(x["flag"])))
    OUT.write_text(json.dumps({"seed": SEED, "n": N, "population_size": len(pop),
                               "population": [[x["policy_id"], x["flag"]] for x in pop],
                               "sample": [[x["policy_id"], x["flag"]] for x in sample]}, indent=1))
    print(f"population {len(pop)} -> sample {N} (seed {SEED}); wrote {OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
