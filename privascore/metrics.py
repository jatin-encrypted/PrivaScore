"""Descriptive per-policy metrics, stored together in one file:

  - readability      Flesch-Kincaid grade, Flesch Reading Ease, reading time   (privascore.textstats)
  - vagueness        share of prose sentences with >= 1 vague-wording cue      (privascore.textstats)
  - bert_profile     share of paragraphs per OPP-115 category, p >= 0.5        (privascore.bert, seed 44)

None of these enter the Risk Index or Disclosure Quality; they are shown next to them.

    .venv/bin/python -I -m privascore.metrics            -> runs/policy_metrics/policy_metrics.{json,md}
    .venv/bin/python -I -m privascore.metrics --no-bert  -> readability + vagueness only (no torch needed)

    from privascore.metrics import load_metrics
    m = load_metrics()            # {"P01": {"name": ..., "readability": {...}, "vagueness": {...}, "bert_profile": {...}}}

Every record carries the snapshot's sha256; load_metrics() refuses a file whose hashes no longer
match gold_set/policies/manifest.json, so stale metrics are never shown for a changed snapshot.
"""
import hashlib
import json
from datetime import datetime, timezone

from .flags import REPO_ROOT
from .text import segment
from .textstats import LEXICON_SOURCE, LEXICON_VERSION, analyse

OUT_DIR = REPO_ROOT / "runs" / "policy_metrics"
OUT_JSON = OUT_DIR / "policy_metrics.json"
MANIFEST = REPO_ROOT / "gold_set" / "policies" / "manifest.json"


def policy_metrics(text: str, bert=None) -> dict:
    """Metrics for one policy text. `bert` is an OPP115Bert or None (profile skipped)."""
    s = analyse(text)
    out = {
        "readability": {"fk_grade": s.fk_grade, "flesch_reading_ease": s.flesch_reading_ease,
                        "reading_minutes": s.reading_minutes, "words": s.words, "prose_sentences": s.sentences,
                        "avg_words_per_sentence": s.avg_words_per_sentence},
        "vagueness": {"vague_sentence_fraction": s.vague_sentence_fraction,
                      "multi_category_fraction": s.multi_category_fraction,
                      "cues_per_1000_words": s.cues_per_1000_words,
                      "examples": [vars(v) for v in s.top_vague[:5]]},
    }
    if bert is not None:
        from .bert import CATEGORIES, THRESHOLD
        paras = [p for p in segment(text) if p["sentences"]]
        probs = bert.predict([text[p["start"]:p["end"]] for p in paras])
        out["bert_profile"] = {"paragraphs": len(paras),
                               "share": {c: round(float((probs[:, j] >= THRESHOLD).mean()), 3)
                                         for j, c in enumerate(CATEGORIES)}}
    return out


def build(with_bert: bool = True) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    bert, gate = None, None
    if with_bert:
        from .bert import OPP115Bert, sanity_gate
        bert = OPP115Bert()
        gate = sanity_gate(bert)
        if not gate["passed"]:
            raise SystemExit(f"BERT sanity gate failed, profile not produced: {gate}")
    policies = {}
    for key, e in sorted(manifest.items(), key=lambda kv: kv[1]["id"]):
        raw = (REPO_ROOT / "gold_set" / e["text_file"]).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        assert sha == e["text_sha256"], f"{key}: snapshot does not match manifest"
        policies[e["id"]] = {"key": key, "name": e["name"], "cohort": e.get("cohort"), "text_sha256": sha,
                             **policy_metrics(raw.decode("utf-8"), bert)}
        print(f"{e['id']} {e['name']} done")
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Descriptive indicators only; not part of the Risk Index or Disclosure Quality.",
        "readability_method": "Flesch 1948 / Kincaid et al. 1975; vowel-group syllable heuristic; 238 wpm",
        "vagueness_lexicon": {"version": LEXICON_VERSION, "source": LEXICON_SOURCE},
        "bert": None if gate is None else {"checkpoint": gate["checkpoint"], "threshold": 0.5,
                                           "sanity_gate": gate, "unit": "paragraph (one snapshot line)"},
        "policies": policies,
    }


def load_metrics(path=OUT_JSON) -> dict:
    """Per-policy metrics keyed by policy id; raises if any snapshot changed since they were computed."""
    data = json.loads(path.read_text(encoding="utf-8"))
    manifest = {e["id"]: e for e in json.loads(MANIFEST.read_text()).values()}
    stale = [pid for pid, r in data["policies"].items() if manifest.get(pid, {}).get("text_sha256") != r["text_sha256"]]
    if stale:
        raise ValueError(f"policy_metrics.json is stale for {stale}; re-run python -m privascore.metrics")
    return data["policies"]


SHORT = {"First Party Collection/Use": "1st party", "Third Party Sharing/Collection": "3rd party",
         "User Choice/Control": "Choice", "User Access, Edit and Deletion": "Access", "Data Retention": "Retention",
         "Data Security": "Security", "Policy Change": "Change", "Do Not Track": "DNT",
         "International and Specific Audiences": "Intl/Aud.", "Other": "Other"}


def render(data: dict) -> str:
    P = data["policies"]
    L = ["# Policy metrics (descriptive, not part of the Risk Index)", "",
         f"Readability: {data['readability_method']}. Vagueness lexicon: {data['vagueness_lexicon']['source']}", "",
         "| Policy | Words | Read min | FK grade | FRE | Words/sent | Vague sentences | ≥2 cue categories "
         "| Cond/1k | Gen/1k | Mod/1k | Num/1k |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for pid, r in P.items():
        rd, vg = r["readability"], r["vagueness"]
        c = vg["cues_per_1000_words"]
        L.append(f"| {pid} {r['name']} | {rd['words']} | {rd['reading_minutes']} | {rd['fk_grade']} | "
                 f"{rd['flesch_reading_ease']} | {rd['avg_words_per_sentence']} | {vg['vague_sentence_fraction']:.0%} | "
                 f"{vg['multi_category_fraction']:.0%} | {c['conditionality']} | {c['generalization']} | "
                 f"{c['modality']} | {c['numeric_quantifier']} |")
    if data["bert"]:
        cats = list(next(iter(P.values()))["bert_profile"]["share"])
        L += ["", f"## BERT category profile (share of paragraphs, {data['bert']['checkpoint']}, p ≥ 0.5)", "",
              "| Policy | Paragraphs | " + " | ".join(SHORT[c] for c in cats) + " |",
              "|---|---|" + "---|" * len(cats)]
        for pid, r in P.items():
            b = r["bert_profile"]
            L.append(f"| {pid} {r['name']} | {b['paragraphs']} | " + " | ".join(f"{b['share'][c]:.0%}" for c in cats) + " |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-bert", action="store_true", help="skip the BERT profile (no torch needed)")
    a = ap.parse_args(argv)
    data = build(with_bert=not a.no_bert)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    md = render(data)
    (OUT_DIR / "policy_metrics.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
