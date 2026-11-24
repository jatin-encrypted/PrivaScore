"""Step 3a of the gold set: evidence packets for manual labelling.

For each policy snapshot this script:
  1. Splits the saved text into numbered paragraphs (one non-empty line = one paragraph)
     and sentences. Every sentence gets a stable ID such as p042.s2 plus its character
     offsets in the snapshot file, so all evidence is traceable to the source.
  2. Runs every flag's search terms (flag_definitions.json) over every sentence.
  3. Writes, per policy:
       evidence/<key>_numbered.md   the WHOLE policy with sentence IDs. Use it to cite
                                    passages the search did not surface.
       evidence/<key>_evidence.md   per flag: the question, every search term with its hit
                                    count (including zero), and the candidate sentences
                                    with their heading and neighbouring sentences.
       evidence/<key>_evidence.json the same, machine-readable, with ALL candidates and the
                                    full search log; validate_labels.py reads it.

It shows no labels and nothing from the Gemini draft, so labelling stays blind.
Retrieval is a reading aid only: a flag with no hits is not evidence of absence.

Usage:
  .venv/bin/python -I gold_set/build_evidence.py --only P01,P07     # some policies
  .venv/bin/python -I gold_set/build_evidence.py                    # all 15
  .venv/bin/python -I gold_set/build_evidence.py --init-sheet A1    # also create the
                                                                    # labelling sheet for annotator A1
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from privascore.flags import search_flag
from privascore.text import SEGMENTER_VERSION, segment

HERE = Path(__file__).resolve().parent
POLICY_DIR = HERE / "policies"
EVIDENCE_DIR = HERE / "evidence"
ANNOT_DIR = HERE / "annotations"
FLAGS_FILE = HERE / "flag_definitions.json"

MAX_SHOWN = 20          # candidates shown per flag in the .md packet (all are in the .json)

SHEET_COLS = ["policy_id", "policy_key", "flag", "flag_key", "presence", "state", "evidence_ids",
              "related_ids", "refers_elsewhere", "absence_check", "notes", "annotator", "labelled_on"]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# Segmentation and search live in the privascore package so the LLM extractor uses the
# exact same sentence IDs and search terms as these human evidence packets.


def context_of(flat, idx):
    prev_s = flat[idx - 1][1]["text"] if idx > 0 else ""
    next_s = flat[idx + 1][1]["text"] if idx + 1 < len(flat) else ""
    return prev_s, next_s


# ------------------------------------------------------------------ outputs

def write_numbered(path, entry, paragraphs, text_sha):
    out = [f"# {entry['id']} {entry['name']}: full text with sentence IDs", "",
           f"- Source: {entry['url']}", f"- Fetched (UTC): {entry['fetched_at_utc']}",
           f"- Snapshot: `{entry['text_file']}` sha256 `{text_sha}`", "",
           "Cite evidence by sentence ID (e.g. `p042.s2`). IDs are stable as long as the snapshot is unchanged.", ""]
    for p in paragraphs:
        if p["is_heading"]:
            out += ["", f"### {p['pid']} {p['sentences'][0]['text'] if p['sentences'] else ''}", ""]
            continue
        out.append(f"**{p['pid']}** " + " ".join(f"`{s['sid'].split('.')[1]}` {s['text']}" for s in p["sentences"]))
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8")


def build_policy(key, entry, flags, flags_sha, self_names):
    text_path = HERE / entry["text_file"]
    raw = text_path.read_bytes()
    text_sha = sha256_bytes(raw)
    if text_sha != entry["text_sha256"]:
        sys.exit(f"ERROR: {text_path.name} does not match its manifest hash; refusing to build evidence.")
    text = raw.decode("utf-8")
    paragraphs = segment(text)
    flat = [(p, s) for p in paragraphs for s in p["sentences"]]
    # traceability self-check: every sentence's offsets must reproduce its text exactly
    for _, s in flat:
        assert text[s["start"]:s["end"]] == s["text"], s["sid"]

    data = {"policy_id": entry["id"], "policy_key": key, "policy_name": entry["name"], "url": entry["url"],
            "scope": entry["scope"], "cohort": entry["cohort"], "fetched_at_utc": entry["fetched_at_utc"],
            "text_file": entry["text_file"], "text_sha256": text_sha, "flag_definitions_sha256": flags_sha,
            "segmenter_version": SEGMENTER_VERSION, "n_paragraphs": len(paragraphs), "n_sentences": len(flat),
            "sentences": {s["sid"]: {"start": s["start"], "end": s["end"], "heading": p["heading"]} for p, s in flat},
            "flags": {}}

    md = [f"# Evidence packet: {entry['id']} {entry['name']}", "",
          f"- Source: {entry['url']}  ",
          f"- Fetched (UTC): {entry['fetched_at_utc']}; evaluated scope: `{entry['scope']}`  ",
          f"- Snapshot: `{entry['text_file']}` sha256 `{text_sha[:16]}…`; {len(paragraphs)} paragraphs, {len(flat)} sentences  ",
          f"- Full numbered text: `{key}_numbered.md`", "",
          "Read with `ANNOTATION_GUIDELINES.md` open. Candidates are ranked by how many different search terms match "
          "(core terms count 3, support terms 1) and shown in document order. **A missing hit is not proof of absence**: "
          "check the headings in the numbered text before labelling a flag Absent.", ""]

    for f in flags:
        log, cands = search_flag(f, flat, self_names)
        top = sorted(sorted(cands, key=lambda c: (-c["score"], c["idx"]))[:MAX_SHOWN], key=lambda c: c["idx"])
        data["flags"][f["id"]] = {
            "question": f["question"], "search_log": log, "n_candidates": len(cands),
            "candidates": [{k: c[k] for k in ("sid", "heading", "core", "support", "score")} for c in
                           sorted(cands, key=lambda c: (-c["score"], c["idx"]))],
        }
        md += ["---", "", f"## {f['id']} `{f['key']}` ({f['type']}, weight {f['weight']})", "",
               f"**Question:** {f['question']}", "",
               "**Searches run** (sentences matched):  "]
        md.append("; ".join(f"{lbl} [{v['tier']}]: **{v['sentences_matched']}**" for lbl, v in log.items()))
        zero = [lbl for lbl, v in log.items() if v["sentences_matched"] == 0]
        md += ["", f"Terms with no hits: {', '.join(zero) if zero else 'none'}", "",
               f"**Candidates:** {len(cands)} found, {len(top)} shown"
               + (f" (the rest are in `{key}_evidence.json`)" if len(cands) > len(top) else ""), ""]
        if not cands:
            md += ["_No candidate sentences. Before labelling Absent, scan the headings in the numbered text._", ""]
        for c in top:
            _, s = flat[c["idx"]]
            prev_s, next_s = context_of(flat, c["idx"])
            md.append(f"- **`{s['sid']}`** · _{c['heading'][:70] or 'no heading'}_ · matched: "
                      + ", ".join(c["core"] + [x + " (s)" for x in c["support"]]))
            if prev_s:
                md.append(f"  > ‹prev› {prev_s}")
            md.append(f"  > **{s['text']}**")
            if next_s:
                md.append(f"  > ‹next› {next_s}")
            md.append("")
    EVIDENCE_DIR.mkdir(exist_ok=True)
    (EVIDENCE_DIR / f"{key}_evidence.md").write_text("\n".join(md), encoding="utf-8")
    (EVIDENCE_DIR / f"{key}_evidence.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    write_numbered(EVIDENCE_DIR / f"{key}_numbered.md", entry, paragraphs, text_sha)
    return data


def init_sheet(annotator, keys_entries, flags):
    """Create (or extend) annotations/labels_<annotator>.csv with one blank row per (policy, flag).
    Existing rows are never overwritten."""
    ANNOT_DIR.mkdir(exist_ok=True)
    path = ANNOT_DIR / f"labels_{annotator}.csv"
    existing = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))
    have = {(r["policy_id"], r["flag"]) for r in existing}
    added = 0
    for key, entry in keys_entries:
        for f in flags:
            if (entry["id"], f["id"]) not in have:
                existing.append({**{c: "" for c in SHEET_COLS}, "policy_id": entry["id"], "policy_key": key,
                                 "flag": f["id"], "flag_key": f["key"], "annotator": annotator})
                added += 1
    order = {f["id"]: i for i, f in enumerate(flags)}
    existing.sort(key=lambda r: (r["policy_id"], order.get(r["flag"], 99)))
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SHEET_COLS)
        w.writeheader()
        w.writerows(existing)
    print(f"labelling sheet {path.relative_to(HERE.parent)}: {added} new blank rows, {len(existing)} total")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated policy ids, e.g. P01,P07")
    ap.add_argument("--init-sheet", metavar="ANNOTATOR", help="create/extend annotations/labels_<ANNOTATOR>.csv")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None

    flags_raw = FLAGS_FILE.read_bytes()
    flag_doc = json.loads(flags_raw)
    flags = flag_doc["flags"]
    flags_sha = sha256_bytes(flags_raw)
    self_map = {k: frozenset(n.lower() for n in v) for k, v in flag_doc.get("self_names", {}).items()}
    manifest = json.loads((POLICY_DIR / "manifest.json").read_text())

    done = []
    for key, entry in sorted(manifest.items()):
        if only and entry["id"] not in only:
            continue
        d = build_policy(key, entry, flags, flags_sha, self_map.get(entry["name"], frozenset()))
        counts = " ".join(f"{fid}:{v['n_candidates']}" for fid, v in d["flags"].items())
        print(f"{key:15} {d['n_paragraphs']:4} paras {d['n_sentences']:4} sents | candidates {counts}")
        done.append((key, entry))
    if args.init_sheet:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.init_sheet):
            sys.exit("annotator id: letters, digits, _ or - only")
        init_sheet(args.init_sheet, done, flags)
    return 0


if __name__ == "__main__":
    sys.exit(main())
