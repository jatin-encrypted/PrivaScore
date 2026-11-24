"""Step 3b of the gold set: check a human labelling sheet and resolve it into traceable gold labels.

Input : annotations/labels_<annotator>.csv   (filled in by a person; see ANNOTATION_GUIDELINES.md)
Output: annotations/labels_<annotator>_resolved.json

For every labelled row it checks the guideline rules (below) and then RESOLVES each evidence
sentence ID into the exact sentence text, heading and character offsets taken from the
snapshot. Quotes are never typed by hand, so they cannot be invented or mis-copied.

Rules enforced (errors block the row; warnings are printed but the row is kept):
  presence  Present  -> state ED, CD or EE; at least one evidence ID
            Unclear  -> state UN (or blank); at least one evidence ID; notes required
            Absent   -> state NS (or blank); no evidence IDs; absence_check required
            blank    -> row not yet labelled (reported as pending)
  every evidence/related ID must exist in that policy's snapshot
  the snapshot text must still match the manifest hash, and the evidence packet must have
  been built from that same hash
  AI2 is only applicable when AI1 is ED or CD (warning otherwise)
  refers_elsewhere must be yes, no or blank

For Absent rows the resolved output carries the full search log (every term and its hit
count) from the evidence packet, as a record of what was searched. It is not proof of absence.

The labelling sheet and the Gemini draft are never modified.
Usage: .venv/bin/python -I gold_set/validate_labels.py --annotator A1
       .venv/bin/python -I gold_set/validate_labels.py --labels some/other.csv
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
POLICY_DIR = HERE / "policies"
EVIDENCE_DIR = HERE / "evidence"
ANNOT_DIR = HERE / "annotations"
FLAGS_FILE = HERE / "flag_definitions.json"
GUIDELINES = HERE / "ANNOTATION_GUIDELINES.md"

PRESENCE = {"present": "Present", "absent": "Absent", "unclear": "Unclear"}
ID_RE = re.compile(r"^p\d{3}\.s\d+$")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def repo_relative(path: Path) -> str:
    """Path relative to the repo root (no local home directory in the output), else unchanged."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def split_ids(cell: str):
    return [x.strip() for x in re.split(r"[;,\s]+", cell or "") if x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--annotator")
    g.add_argument("--labels", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    labels_path = args.labels or ANNOT_DIR / f"labels_{args.annotator}.csv"
    out_path = args.out or labels_path.with_name(labels_path.stem + "_resolved.json")

    manifest = {e["id"]: e for e in json.loads((POLICY_DIR / "manifest.json").read_text()).values()}
    flags_raw = FLAGS_FILE.read_bytes()
    flags = {f["id"]: f for f in json.loads(flags_raw)["flags"]}
    with labels_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    cache, errors, warnings, resolved, pending = {}, [], [], [], 0

    def policy(pid):
        if pid not in cache:
            e = manifest[pid]
            key = Path(e["text_file"]).stem
            raw = (HERE / e["text_file"]).read_bytes()
            if sha256_bytes(raw) != e["text_sha256"]:
                sys.exit(f"ERROR: snapshot {e['text_file']} changed since it was recorded in manifest.json")
            ev_path = EVIDENCE_DIR / f"{key}_evidence.json"
            if not ev_path.exists():
                sys.exit(f"ERROR: no evidence packet for {pid}; run build_evidence.py --only {pid}")
            ev = json.loads(ev_path.read_text(encoding="utf-8"))
            if ev["text_sha256"] != e["text_sha256"]:
                sys.exit(f"ERROR: evidence packet for {pid} was built from a different snapshot; rebuild it")
            cache[pid] = (raw.decode("utf-8"), ev, e)
        return cache[pid]

    for n, r in enumerate(rows, 2):  # line 1 is the header
        where = f"line {n} {r.get('policy_id')} {r.get('flag')}"
        pid, flag = r.get("policy_id", "").strip(), r.get("flag", "").strip()
        if pid not in manifest or flag not in flags:
            errors.append(f"{where}: unknown policy_id or flag")
            continue
        pres_raw = (r.get("presence") or "").strip().lower()
        if not pres_raw:
            pending += 1
            continue
        presence = PRESENCE.get(pres_raw)
        state = (r.get("state") or "").strip().upper()
        ev_ids, rel_ids = split_ids(r.get("evidence_ids")), split_ids(r.get("related_ids"))
        row_err = []
        if presence is None:
            row_err.append(f"presence must be Present, Absent or Unclear, got {r['presence']!r}")
        elif presence == "Present":
            if state not in {"ED", "CD", "EE"}:
                row_err.append("Present needs state ED, CD or EE")
            if not ev_ids:
                row_err.append("Present needs at least one evidence ID")
        elif presence == "Unclear":
            if state not in {"", "UN"}:
                row_err.append("Unclear must have state UN or blank")
            state = "UN"
            if not ev_ids:
                row_err.append("Unclear needs at least one evidence ID")
            if not (r.get("notes") or "").strip():
                row_err.append("Unclear needs a note saying what is unclear")
        else:  # Absent
            if state not in {"", "NS"}:
                row_err.append("Absent must have state NS or blank")
            state = "NS"
            if ev_ids:
                row_err.append("Absent cannot have evidence IDs (put nearby text in related_ids)")
            if not (r.get("absence_check") or "").strip():
                row_err.append("Absent needs absence_check (what you searched/read)")
        bl = (r.get("borderline") or "").strip()
        if bl and not re.fullmatch(r"(ED|CD|EE|NS|UN)\|(ED|CD|EE|NS|UN)", bl):
            row_err.append("borderline must look like CD|ED (two states)")
        rs = (r.get("review_status") or "").strip().lower()
        if rs not in {"", "pending", "verified", "edited", "accepted"}:
            row_err.append("review_status must be pending, verified, edited or accepted (accepted = after spot-check)")
        ref = (r.get("refers_elsewhere") or "").strip().lower()
        if ref not in {"", "yes", "no"}:
            row_err.append("refers_elsewhere must be yes, no or blank")

        text, ev, entry = policy(pid)
        sentences = ev["sentences"]
        for sid in ev_ids + rel_ids:
            if not ID_RE.match(sid):
                row_err.append(f"bad ID format {sid!r} (expected like p042.s2)")
            elif sid not in sentences:
                row_err.append(f"ID {sid} does not exist in {pid}'s snapshot")
        if row_err:
            errors += [f"{where}: {m}" for m in row_err]
            continue

        def resolve(sid):
            s = sentences[sid]
            return {"id": sid, "heading": s["heading"], "start": s["start"], "end": s["end"],
                    "text": text[s["start"]:s["end"]]}

        item = {
            "policy_id": pid, "policy_key": Path(entry["text_file"]).stem, "flag": flag,
            "flag_key": flags[flag]["key"], "presence": presence, "state": state,
            "evidence": [resolve(s) for s in ev_ids], "related": [resolve(s) for s in rel_ids],
            "refers_elsewhere": ref or None, "absence_check": (r.get("absence_check") or "").strip() or None,
            "notes": (r.get("notes") or "").strip() or None, "annotator": (r.get("annotator") or "").strip(),
            "labelled_on": (r.get("labelled_on") or "").strip() or None,
            "snapshot_text_sha256": entry["text_sha256"],
            "reason": (r.get("reason") or "").strip() or None,
            "borderline": (r.get("borderline") or "").strip() or None,
            "drafted_by": (r.get("drafted_by") or "").strip() or None,
            "review_status": (r.get("review_status") or "").strip() or None,
        }
        if presence == "Absent":
            item["search_log"] = {k: v["sentences_matched"] for k, v in ev["flags"][flag]["search_log"].items()}
            item["search_note"] = "Terms searched by build_evidence.py and sentences matched. Not proof of absence."
        resolved.append(item)

    # cross-row rule: AI2 only applies when AI1 is ED or CD
    by = {(x["policy_id"], x["flag"]): x for x in resolved}
    for (pid, flag), x in by.items():
        if flag == "AI2":
            ai1 = by.get((pid, "AI1"))
            if ai1 and ai1["state"] not in {"ED", "CD"} and x["state"] != "NS":
                warnings.append(f"{pid} AI2: AI1 is {ai1['state']}, so AI2 should be Absent (not applicable)")

    out = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "labels_file": repo_relative(labels_path), "labels_sha256": sha256_bytes(labels_path.read_bytes()),
        "flag_definitions_sha256": sha256_bytes(flags_raw),
        "guidelines_sha256": sha256_bytes(GUIDELINES.read_bytes()) if GUIDELINES.exists() else None,
        "n_rows": len(rows), "n_resolved": len(resolved), "n_pending": pending, "n_errors": len(errors),
        "labels": resolved,
    }
    out_path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{labels_path.name}: {len(rows)} rows | resolved {len(resolved)} | pending {pending} | "
          f"errors {len(errors)} | warnings {len(warnings)}")
    for m in errors:
        print("  ERROR  ", m)
    for m in warnings:
        print("  WARNING", m)
    print(f"wrote {out_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
