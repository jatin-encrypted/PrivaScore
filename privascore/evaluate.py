"""Compare an extraction run with the human gold labels.

  .venv/bin/python -m privascore.evaluate --run runs/<run-name>
        [--gold gold_set/annotations/labels_A1_resolved.json]

Gold = validate_labels.py output (only rows that passed validation). Metrics, all with the
number of items (n) because the gold set is small (15 policies x 16 flags):
  - state accuracy (5 states: ED CD EE NS UN) and presence accuracy (Present/Absent/Unclear),
    with Wilson 95% intervals; headline excludes G1 (approved decision 7) and DPDP4 (weight 0)
  - per-flag and per-cohort accuracy, confusion matrix, per-state precision/recall/F1, macro F1
  - false "Not stated": gold Present/Unclear but predicted Absent (the failure mode that hides
    risk), and false "Present": gold Absent but predicted Present
  - evidence agreement: when both say Present, did the extractor cite at least one sentence the
    annotator cited (evidence or related IDs)?
  - coverage: rejected flags (no verified answer) are reported separately and count as wrong
  - scores: Risk Index and Disclosure Quality from gold states vs predicted states per policy
    (mean absolute difference, Kendall tau of the policy ranking)
Writes <run>/evaluation.json and <run>/evaluation.md.
"""
import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .flags import REPO_ROOT, load_flags, repo_relative
from .scoring import kendall_tau, score

STATES = ["ED", "CD", "EE", "NS", "UN"]
HEADLINE_EXCLUDE = {"G1", "DPDP4"}
DEFAULT_GOLD = REPO_ROOT / "gold_set" / "annotations" / "labels_A1_resolved.json"


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def acc(pairs):
    k = sum(g == p for g, p in pairs)
    lo, hi = wilson(k, len(pairs))
    return {"n": len(pairs), "correct": k, "accuracy": k / len(pairs) if pairs else None, "ci95": [lo, hi]}


def presence_of(state):
    return {"NS": "Absent", "UN": "Unclear"}.get(state, "Present" if state else None)


def per_state_f1(pairs):
    out = {}
    for s in STATES:
        tp = sum(g == s and p == s for g, p in pairs)
        fp = sum(g != s and p == s for g, p in pairs)
        fn = sum(g == s and p != s for g, p in pairs)
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if (tp + fp) and (tp + fn) else None)
        out[s] = {"support": tp + fn, "precision": prec, "recall": rec, "f1": f1}
    f1s = [v["f1"] for v in out.values() if v["f1"] is not None and v["support"]]
    return out, (sum(f1s) / len(f1s) if f1s else None)


def evaluate(run_dir: Path, gold_path: Path):
    flags = load_flags().flags
    gold_doc = json.loads(gold_path.read_text(encoding="utf-8"))
    gold = {(g["policy_id"], g["flag"]): g for g in gold_doc["labels"]}
    preds, cohorts, sha_mismatch = {}, {}, []
    for f in sorted(run_dir.glob("P*_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        cohorts[d["policy_id"]] = d.get("cohort", "")
        for fid, r in d["flags"].items():
            preds[(d["policy_id"], fid)] = r
        gsha = {g["snapshot_text_sha256"] for g in gold_doc["labels"] if g["policy_id"] == d["policy_id"]}
        if gsha and d["text_sha256"] not in gsha:
            sha_mismatch.append(d["policy_id"])
    if sha_mismatch:
        raise SystemExit(f"run and gold were made on different snapshots for {sha_mismatch}")

    keys = sorted(set(gold) & set(preds))
    rows = []
    for k in keys:
        g, p = gold[k], preds[k]
        rows.append({"policy_id": k[0], "flag": k[1], "cohort": cohorts.get(k[0], ""), "gold": g["state"],
                     "pred": p["state"] if p["status"] != "rejected" else "REJ", "status": p["status"],
                     "gold_ids": {e["id"] for e in g["evidence"]} | {e["id"] for e in g.get("related", [])},
                     "pred_ids": {e["id"] for e in p.get("evidence", [])}})
    head = [r for r in rows if r["flag"] not in HEADLINE_EXCLUDE]

    def pairs(rs, presence=False):
        if presence:
            return [(presence_of(r["gold"]), presence_of(r["pred"]) if r["pred"] != "REJ" else "REJ") for r in rs]
        return [(r["gold"], r["pred"]) for r in rs]

    per_state, macro = per_state_f1(pairs(head))
    conf = defaultdict(Counter)
    for r in head:
        conf[r["gold"]][r["pred"]] += 1
    both_present = [r for r in rows if presence_of(r["gold"]) == "Present" and presence_of(r["pred"]) == "Present"
                    and r["pred"] != "REJ"]
    ev_hits = sum(bool(r["gold_ids"] & r["pred_ids"]) for r in both_present)

    # policy-level scores from gold vs predicted states (only policies with all 16 flags labelled)
    score_rows = []
    for pid in sorted({r["policy_id"] for r in rows}):
        rs = {r["flag"]: r for r in rows if r["policy_id"] == pid}
        if len(rs) < len(flags):
            continue
        g = score({f: rs[f]["gold"] for f in rs}, flags)
        p = score({f: (rs[f]["pred"] if rs[f]["pred"] != "REJ" else "UN") for f in rs}, flags)
        score_rows.append({"policy_id": pid, "gold_risk": g.risk_index, "pred_risk": p.risk_index,
                           "gold_quality": g.disclosure_quality, "pred_quality": p.disclosure_quality})

    def mad(a, b):
        return sum(abs(r[a] - r[b]) for r in score_rows) / len(score_rows) if score_rows else None

    res = {
        "run": repo_relative(run_dir), "gold": repo_relative(gold_path), "gold_labels": len(gold), "pred_labels": len(preds),
        "evaluated_pairs": len(rows), "headline_pairs": len(head),
        "headline_excludes": sorted(HEADLINE_EXCLUDE),
        "state_accuracy": acc(pairs(head)), "presence_accuracy": acc(pairs(head, True)),
        "state_accuracy_all_flags": acc(pairs(rows)),
        "macro_f1_states": macro, "per_state": per_state,
        "confusion": {g: dict(c) for g, c in conf.items()},
        "per_flag": {f.id: acc(pairs([r for r in rows if r["flag"] == f.id])) for f in flags},
        "per_cohort": {c: acc(pairs([r for r in head if r["cohort"] == c])) for c in sorted({r["cohort"] for r in head})},
        "false_not_stated": {"n_gold_present_or_unclear": sum(r["gold"] not in ("NS",) for r in head),
                             "predicted_absent": sum(r["gold"] != "NS" and r["pred"] == "NS" for r in head)},
        "false_present": {"n_gold_absent": sum(r["gold"] == "NS" for r in head),
                          "predicted_present": sum(r["gold"] == "NS" and presence_of(r["pred"]) == "Present" for r in head)},
        "rejected": sum(r["pred"] == "REJ" for r in rows),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "evidence_agreement": {"both_present": len(both_present), "overlap": ev_hits,
                               "rate": ev_hits / len(both_present) if both_present else None},
        "scores": {"policies": score_rows, "risk_mad": mad("gold_risk", "pred_risk"),
                   "quality_mad": mad("gold_quality", "pred_quality"),
                   "risk_rank_tau": kendall_tau([r["gold_risk"] for r in score_rows], [r["pred_risk"] for r in score_rows])
                   if len(score_rows) >= 2 else None},
        "disagreements": [{k: (sorted(v) if isinstance(v, set) else v) for k, v in r.items()}
                          for r in rows if r["gold"] != r["pred"]],
    }
    return res


def fmt_acc(a):
    if not a["n"]:
        return "n=0"
    lo, hi = a["ci95"]
    return f"{a['accuracy']:.2f} ({a['correct']}/{a['n']}; 95% CI {lo:.2f}-{hi:.2f})"


def to_markdown(res):
    L = ["# Extractor vs gold labels", "",
         f"- Run: `{res['run']}`  ", f"- Gold: `{res['gold']}` ({res['gold_labels']} validated labels)  ",
         f"- Evaluated (policy, flag) pairs: {res['evaluated_pairs']}; headline excludes {', '.join(res['headline_excludes'])}",
         "", "| Metric | Value |", "|---|---|",
         f"| State accuracy (5 states, headline) | {fmt_acc(res['state_accuracy'])} |",
         f"| Presence accuracy (headline) | {fmt_acc(res['presence_accuracy'])} |",
         f"| State accuracy, all 16 flags | {fmt_acc(res['state_accuracy_all_flags'])} |",
         f"| Macro F1 over states | {res['macro_f1_states']:.2f} |" if res["macro_f1_states"] is not None else "| Macro F1 | n/a |",
         f"| False 'Not stated' (gold addressed, predicted Absent) | {res['false_not_stated']['predicted_absent']} of {res['false_not_stated']['n_gold_present_or_unclear']} |",
         f"| False 'Present' (gold Absent, predicted Present) | {res['false_present']['predicted_present']} of {res['false_present']['n_gold_absent']} |",
         f"| Rejected (no verified answer) | {res['rejected']} |",
         f"| Evidence overlap when both Present | {res['evidence_agreement']['overlap']} of {res['evidence_agreement']['both_present']} |"]
    s = res["scores"]
    if s["policies"]:
        L += [f"| Risk Index mean abs. difference | {s['risk_mad']:.1f} points |",
              f"| Disclosure Quality mean abs. difference | {s['quality_mad']:.1f} points |"]
        if s["risk_rank_tau"] is not None:
            L.append(f"| Kendall tau of policy risk ranking | {s['risk_rank_tau']:.2f} |")
    L += ["", "## Per flag", "", "| Flag | Accuracy |", "|---|---|"]
    L += [f"| {f} | {fmt_acc(a)} |" for f, a in res["per_flag"].items()]
    L += ["", "## Per cohort (headline flags)", "", "| Cohort | Accuracy |", "|---|---|"]
    L += [f"| {c} | {fmt_acc(a)} |" for c, a in res["per_cohort"].items()]
    L += ["", "## Confusion (rows gold, columns predicted)", "",
          "| gold \\ pred | " + " | ".join(STATES + ["REJ"]) + " |", "|---" * 7 + "|"]
    for g in STATES:
        L.append(f"| {g} | " + " | ".join(str(res["confusion"].get(g, {}).get(p, 0)) for p in STATES + ["REJ"]) + " |")
    L += ["", f"Small-sample warning: {res['headline_pairs']} headline pairs from at most 15 policies; "
              "intervals are wide and per-flag numbers rest on 15 items each."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    args = ap.parse_args(argv)
    res = evaluate(args.run, args.gold)
    if not res["evaluated_pairs"]:
        print("no overlapping (policy, flag) pairs between the run and the gold labels yet")
        return 1
    (args.run / "evaluation.json").write_text(json.dumps(res, indent=1, default=list), encoding="utf-8")
    md = to_markdown(res)
    (args.run / "evaluation.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
