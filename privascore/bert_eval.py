"""Tests A-C: the fine-tuned OPP-115 BERT on the 15-policy reference set.

    .venv/bin/python -I -m privascore.bert_eval      -> runs/bert_eval/bert_eval.{json,md}

PRE-REGISTERED (approved 18 Nov 2026, fixed before any result was seen)
  Mapping (frozen): see FLAG_TO_CATEGORY / FIT. AI1, AI3, AI4, DPDP4 have no OPP-115 category
  and are not evaluated. Strong = G1, G2, G4, G5.
  Model: seed-44 checkpoint-1134, sigmoid >= 0.5 (never tuned here), max 256 tokens.
  Unit: one policy paragraph (pXXX, one non-empty line of the snapshot), raw text, no heading added.
  Sanity gate: OPP-115 test macro F1 must reproduce result.json within 0.003, else nothing runs.
  Decision rule: integrate BERT as a retrieval booster iff, pooled over G1, G2, G4, G5 x 15 policies,
    evidence-sentence recall of (keywords + BERT) exceeds keywords alone by >= 5 percentage points
    while adding <= 25% more sentences than keywords alone show. Otherwise BERT stays a standalone
    10-category policy profiler and A-C are reported as a retrieval / domain-shift study.

Operational details (fixed in this file before running; not covered by the approved wording)
  Gold presence: Present or Unclear = "addressed"; Absent = "not addressed".
  A. Presence: BERT says addressed iff >= 1 paragraph has p(category) >= 0.5.
     Compared with keywords (>= 1 candidate sentence) and gemini-3.5-flash-lite v1.1 (its presence
     answer; a rejected answer counts as wrong). All 15 x 11 mapped rows.
  B. Evidence location: gold rows that are addressed and cite evidence. A gold evidence sentence is
     found if it is in a BERT-positive paragraph (BERT) / among the sentences the LLM is shown
     (keywords). Recall is pooled over sentences; also "row has >= 1 found". Size = sentences selected.
  C. Booster: keyword-shown sentences plus sentences of BERT-positive paragraphs not already shown,
     ranked by paragraph probability (then document order), added up to floor(25% x keyword-shown)
     per row ("budgeted", the integrable form). The uncapped union is reported as a diagnostic.
     The decision uses the budgeted form; its size condition is checked pooled, not assumed.
  Caveat to report: the reference evidence was drafted from the keyword packets, so keyword recall is
  optimistic and BERT recall is a lower bound.
"""
import hashlib
import json
import math
from collections import defaultdict

from .bert import CATEGORIES, THRESHOLD, OPP115Bert, sanity_gate
from .config import ExtractorSettings
from .extractor import select_sentences
from .flags import REPO_ROOT, load_flags, search_flag
from .verifier import PolicyDoc

FLAG_TO_CATEGORY = {
    "G1": "First Party Collection/Use", "G2": "Third Party Sharing/Collection", "G3": "First Party Collection/Use",
    "G4": "Data Retention", "G5": "User Access, Edit and Deletion",
    "G6": "International and Specific Audiences", "G7": "International and Specific Audiences",
    "AI2": "User Choice/Control", "DPDP2": "User Choice/Control", "AI5": "Third Party Sharing/Collection",
    "DPDP1": "User Choice/Control", "DPDP3": "Other",
}
FIT = {"G1": "strong", "G2": "strong", "G4": "strong", "G5": "strong",
       "G6": "medium", "G7": "medium", "AI2": "medium", "DPDP2": "medium", "AI5": "medium",
       "G3": "weak", "DPDP1": "weak", "DPDP3": "weak"}
STRONG = ["G1", "G2", "G4", "G5"]
UNMAPPED = ["AI1", "AI3", "AI4", "DPDP4"]
LLM_RUN = REPO_ROOT / "runs" / "gemini35lite_batch_v1.1"
SHORT = {"First Party Collection/Use": "1st party", "Third Party Sharing/Collection": "3rd party",
         "User Choice/Control": "Choice", "User Access, Edit and Deletion": "Access", "Data Retention": "Retention",
         "Data Security": "Security", "Policy Change": "Change", "Do Not Track": "DNT",
         "International and Specific Audiences": "Intl/Audiences", "Other": "Other"}
RULE_MIN_GAIN_PP = 5.0
RULE_MAX_EXTRA = 0.25


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def addressed(presence):
    return presence in ("Present", "Unclear")


def main(argv=None) -> int:
    out_dir = REPO_ROOT / "runs" / "bert_eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    bert = OPP115Bert()
    gate = sanity_gate(bert)
    print("sanity gate:", gate)
    if not gate["passed"]:
        print("SANITY GATE FAILED: no results produced.")
        return 3

    gold_file = REPO_ROOT / "gold_set/annotations/labels_A1_resolved.json"
    gold_doc = json.loads(gold_file.read_text())
    csv_sha = hashlib.sha256((REPO_ROOT / "gold_set/annotations/labels_A1.csv").read_bytes()).hexdigest()
    assert gold_doc["labels_sha256"] == csv_sha and gold_doc["n_errors"] == 0, "resolved gold is stale"
    gold = {(r["policy_id"], r["flag"]): r for r in gold_doc["labels"]}

    manifest = json.loads((REPO_ROOT / "gold_set/policies/manifest.json").read_text())
    flags = load_flags()
    cfg = ExtractorSettings()          # keyword retrieval exactly as the extractor shows it to the LLM

    rows, profiles, para_counts = [], {}, {}
    for key, e in sorted(manifest.items(), key=lambda kv: kv[1]["id"]):
        pid = e["id"]
        raw = (REPO_ROOT / "gold_set" / e["text_file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == e["text_sha256"], key
        text = raw.decode("utf-8")
        doc = PolicyDoc(text, pid)
        paras = [p for p in doc.paragraphs if p["sentences"]]
        probs = bert.predict([text[p["start"]:p["end"]] for p in paras])
        para_counts[pid] = len(paras)
        profiles[pid] = {"name": e["name"], "paragraphs": len(paras),
                         **{c: round(float((probs[:, j] >= THRESHOLD).mean()), 3) for j, c in enumerate(CATEGORIES)}}
        sent_para = {s["sid"]: i for i, p in enumerate(paras) for s in p["sentences"]}

        self_names = flags.self_names.get(e["name"], frozenset())
        kw_res = {}
        for fl in flags.flags:
            _, cands = search_flag(fl, doc.flat, self_names)
            kw_res[fl.id] = {"n_candidates": len(cands), "shown": select_sentences(doc, cands, cfg) if cands else []}
        llm_path = LLM_RUN / f"{key}.json"
        llm = json.loads(llm_path.read_text())["flags"] if llm_path.exists() else {}

        for f, cat in FLAG_TO_CATEGORY.items():
            j = CATEGORIES.index(cat)
            pos_paras = [i for i in range(len(paras)) if probs[i, j] >= THRESHOLD]
            bert_sids = [s["sid"] for i in pos_paras for s in paras[i]["sentences"]]
            shown = list(kw_res[f]["shown"])
            g = gold[(pid, f)]
            gold_sids = [ev["id"] for ev in g["evidence"]]
            # booster: rank BERT-only sentences by paragraph probability, then document order
            extra = [sid for sid in sorted(set(bert_sids) - set(shown),
                                           key=lambda s: (-probs[sent_para[s], j], doc.order[s]))]
            budget = math.floor(RULE_MAX_EXTRA * len(shown))
            boost = set(shown) | set(extra[:budget])
            lp = llm.get(f, {})
            rows.append({
                "policy_id": pid, "flag": f, "fit": FIT[f], "category": cat,
                "gold_presence": g["presence"], "gold_state": g.get("state"),
                "bert_addressed": bool(pos_paras), "kw_addressed": kw_res[f]["n_candidates"] > 0,
                "llm_presence": lp.get("presence") if lp.get("status") != "rejected" else "REJ",
                "n_policy_sentences": len(doc.flat), "n_bert": len(bert_sids), "n_kw": len(shown),
                "n_boost_added": len(boost) - len(shown), "n_union_added": len(set(bert_sids) - set(shown)),
                "gold_evidence": gold_sids,
                "found_bert": [s for s in gold_sids if s in set(bert_sids)],
                "found_kw": [s for s in gold_sids if s in set(shown)],
                "found_boost": [s for s in gold_sids if s in boost],
                "found_union": [s for s in gold_sids if s in set(shown) | set(bert_sids)],
                "max_prob": round(float(probs[:, j].max()), 3) if len(paras) else 0.0,
            })
        print(f"{pid} {e['name']}: {len(paras)} paragraphs scored")

    res = summarise(rows)
    res.update({"sanity_gate": gate, "category_profiles": profiles,
                "gold_labels_sha256": csv_sha, "llm_run": LLM_RUN.name,
                "mapping": {f: {"category": c, "fit": FIT[f]} for f, c in FLAG_TO_CATEGORY.items()},
                "unmapped": UNMAPPED, "rows": rows})
    (out_dir / "bert_eval.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    md = render(res)
    (out_dir / "bert_eval.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def summarise(rows):
    def presence_acc(rs, who):
        def pred(r):
            if who == "bert":
                return r["bert_addressed"]
            if who == "kw":
                return r["kw_addressed"]
            return None if r["llm_presence"] == "REJ" else addressed(r["llm_presence"])
        k = sum(pred(r) == addressed(r["gold_presence"]) for r in rs)
        tp = sum(pred(r) is True and addressed(r["gold_presence"]) for r in rs)
        fp = sum(pred(r) is True and not addressed(r["gold_presence"]) for r in rs)
        fn = sum(pred(r) is not True and addressed(r["gold_presence"]) for r in rs)
        tn = sum(pred(r) is False and not addressed(r["gold_presence"]) for r in rs)
        return {"n": len(rs), "correct": k, "accuracy": round(k / len(rs), 3) if rs else None,
                "ci95": wilson(k, len(rs)), "tp": tp, "fp": fp, "fn": fn, "tn": tn}

    def retrieval(rs):
        ev = [r for r in rs if addressed(r["gold_presence"]) and r["gold_evidence"]]
        n = sum(len(r["gold_evidence"]) for r in ev)
        out = {"rows": len(ev), "gold_sentences": n}
        for k in ("bert", "kw", "boost", "union"):
            f = sum(len(r[f"found_{k}"]) for r in ev)
            out[f"recall_{k}"] = round(f / n, 3) if n else None
            out[f"rows_any_{k}"] = round(sum(bool(r[f"found_{k}"]) for r in ev) / len(ev), 3) if ev else None
        sz = rs
        kw_tot = sum(r["n_kw"] for r in sz)
        out.update({
            "sentences_kw": kw_tot, "sentences_bert": sum(r["n_bert"] for r in sz),
            "added_boost": sum(r["n_boost_added"] for r in sz), "added_union": sum(r["n_union_added"] for r in sz),
            "bert_share_of_policy": round(sum(r["n_bert"] for r in sz) / sum(r["n_policy_sentences"] for r in sz), 3),
        })
        out["extra_boost_pct"] = round(100 * out["added_boost"] / kw_tot, 1) if kw_tot else None
        out["extra_union_pct"] = round(100 * out["added_union"] / kw_tot, 1) if kw_tot else None
        if n:
            out["gain_boost_pp"] = round(100 * (out["recall_boost"] - out["recall_kw"]), 1)
            out["gain_union_pp"] = round(100 * (out["recall_union"] - out["recall_kw"]), 1)
        return out

    groups = {"strong": [r for r in rows if r["fit"] == "strong"],
              "medium": [r for r in rows if r["fit"] == "medium"],
              "weak": [r for r in rows if r["fit"] == "weak"], "all_mapped": rows}
    by_flag = defaultdict(list)
    for r in rows:
        by_flag[r["flag"]].append(r)
    res = {
        "A_presence": {g: {w: presence_acc(rs, w) for w in ("bert", "kw", "llm")} for g, rs in groups.items()},
        "A_presence_by_flag": {f: {w: presence_acc(rs, w) for w in ("bert", "kw", "llm")} for f, rs in by_flag.items()},
        "BC_retrieval": {g: retrieval(rs) for g, rs in groups.items()},
        "BC_retrieval_by_flag": {f: retrieval(rs) for f, rs in by_flag.items()},
    }
    s = res["BC_retrieval"]["strong"]
    gain_ok = s["gain_boost_pp"] >= RULE_MIN_GAIN_PP
    size_ok = s["extra_boost_pct"] <= 100 * RULE_MAX_EXTRA
    res["decision"] = {
        "rule": f">= {RULE_MIN_GAIN_PP} pp recall gain on G1,G2,G4,G5 with <= {int(100 * RULE_MAX_EXTRA)}% extra sentences",
        "gain_pp": s["gain_boost_pp"], "extra_pct": s["extra_boost_pct"], "gain_ok": gain_ok, "size_ok": size_ok,
        "outcome": "INTEGRATE as retrieval booster" if gain_ok and size_ok
                   else "STANDALONE profiler (do not integrate as booster)",
    }
    return res


def render(res):
    L = ["# Fine-tuned OPP-115 BERT on the 15-policy reference set (Tests A-C)", "",
         f"Sanity gate: OPP-115 test macro F1 stored {res['sanity_gate']['stored_macro_f1']} / "
         f"rescored {res['sanity_gate']['rescored_macro_f1']} ({'passed' if res['sanity_gate']['passed'] else 'FAILED'}; "
         f"{res['sanity_gate'].get('label_flips_vs_stored', '?')} label flips vs stored test predictions).", "",
         f"Reference labels sha256 {res['gold_labels_sha256'][:12]}. LLM comparison: {res['llm_run']}. "
         f"Unmapped (not evaluated): {', '.join(res['unmapped'])}.", "",
         "## Decision (pre-registered)", "",
         f"- Rule: {res['decision']['rule']}",
         f"- Measured (budgeted booster): **{res['decision']['gain_pp']:+} pp** recall, "
         f"**{res['decision']['extra_pct']}%** extra sentences",
         f"- Outcome: **{res['decision']['outcome']}**", "",
         "## A. Presence (addressed vs not addressed)", "",
         "| Group | Rows | BERT acc | Keywords acc | Gemini 3.5-lite v1.1 acc | BERT FP / FN |",
         "|---|---|---|---|---|---|"]
    for g, d in res["A_presence"].items():
        b, k, l = d["bert"], d["kw"], d["llm"]
        L.append(f"| {g} | {b['n']} | {b['accuracy']} {b['ci95']} | {k['accuracy']} {k['ci95']} | "
                 f"{l['accuracy']} {l['ci95']} | {b['fp']} / {b['fn']} |")
    L += ["", "| Flag | Fit | Gold addressed | BERT acc | Keywords acc | LLM acc |", "|---|---|---|---|---|---|"]
    for f, d in res["A_presence_by_flag"].items():
        b = d["bert"]
        L.append(f"| {f} | {FIT[f]} | {b['tp'] + b['fn']}/{b['n']} | {b['accuracy']} | {d['kw']['accuracy']} | "
                 f"{d['llm']['accuracy']} |")
    L += ["", "## B / C. Evidence location and booster", "",
          "Recall = share of reference evidence sentences reachable. Sizes are sentence totals over the group.", "",
          "| Group | Evid. sent. | BERT recall | Keyword recall | Kw+BERT (budget) | Kw+BERT (uncapped) | "
          "BERT size / kw size | Budget extra | Uncapped extra |",
          "|---|---|---|---|---|---|---|---|---|"]
    for g, d in list(res["BC_retrieval"].items()) + [(f, d) for f, d in res["BC_retrieval_by_flag"].items()]:
        if not d["gold_sentences"]:
            continue
        L.append(f"| {g} | {d['gold_sentences']} | {d['recall_bert']} | {d['recall_kw']} | {d['recall_boost']} "
                 f"({d['gain_boost_pp']:+} pp) | {d['recall_union']} ({d['gain_union_pp']:+} pp) | "
                 f"{d['sentences_bert']} / {d['sentences_kw']} | {d['extra_boost_pct']}% | {d['extra_union_pct']}% |")
    L += ["", "## BERT category profile (share of paragraphs with p >= 0.5)", "",
          "| Policy | Paras | " + " | ".join(SHORT[c] for c in CATEGORIES) + " |",
          "|---|---|" + "---|" * len(CATEGORIES)]
    for pid, p in res["category_profiles"].items():
        L.append(f"| {pid} {p['name']} | {p['paragraphs']} | " + " | ".join(f"{p[c]:.0%}" for c in CATEGORIES) + " |")
    L += ["", "Caveat: reference evidence was drafted starting from the keyword packets, so keyword recall is "
          "optimistic and BERT recall is a lower bound."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    import sys
    sys.exit(main())
