"""Command line: run the extractor on gold-set policy snapshots.

  .venv/bin/python -m privascore.extract --policies P01,P07            # config from privascore.toml
  .venv/bin/python -m privascore.extract --all --run-name gemini_v1
  .venv/bin/python -m privascore.extract --policies P01 --provider mock  # dry run, no key

Writes runs/<run-name>/<policy_key>.json and runs/<run-name>/run.json.
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

from .config import load_config
from .extractor import Extractor
from .flags import REPO_ROOT, load_flags, repo_relative
from .llm import LLMError, QuotaExhausted, make_client

MANIFEST = REPO_ROOT / "gold_set" / "policies" / "manifest.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--policies", help="comma-separated ids, e.g. P01,P07")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--config")
    ap.add_argument("--provider", choices=["mock", "gemini", "groq"], help="override [llm] provider")
    ap.add_argument("--run-name")
    ap.add_argument("--model", help="override the configured model, e.g. gemini-3.5-flash-lite")
    ap.add_argument("--batch", action="store_true", help="one LLM call per policy (plus one retry call for failed flags)")
    ap.add_argument("--cache-dir", help="LLM reply cache folder (default from config). A fresh folder forces new "
                    "calls, e.g. to measure run-to-run stability")
    ap.add_argument("--rules", help="prompt rules file (default privascore/flag_rules.json; v1.0 kept as flag_rules_v1.0.json)")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(args.config, args.provider, args.model)
        if args.batch:
            cfg.llm.max_output_tokens = max(cfg.llm.max_output_tokens, cfg.extractor.batch_max_output_tokens)
        client = make_client(cfg.llm)
    except (LLMError, ValueError) as e:
        sys.exit(str(e))
    flagset = load_flags()
    ex = Extractor(client, flagset, cfg.extractor, rules_path=args.rules,
                   cache_dir=(REPO_ROOT / args.cache_dir) if args.cache_dir else None)

    manifest = json.loads(MANIFEST.read_text())
    wanted = None if args.all else set(args.policies.split(","))
    run_name = args.run_name or f"{cfg.llm.model}{'_batch' if args.batch else ''}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = REPO_ROOT / "runs" / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    done, stopped = [], None
    for key, e in sorted(manifest.items()):
        if wanted and e["id"] not in wanted:
            continue
        raw = (REPO_ROOT / "gold_set" / e["text_file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != e["text_sha256"]:
            sys.exit(f"snapshot {e['text_file']} does not match manifest.json")
        try:
            run = ex.extract_policy_batch if args.batch else ex.extract_policy
            res = run(raw.decode("utf-8"), e["id"], e["scope"], e["name"])
        except QuotaExhausted as q:
            stopped = f"{key}: {q}"
            print(f"\nSTOPPED at {key}: {q}\nFinished policies are saved and every answer so far is cached. "
                  "Run the same command later to continue; cached answers cost nothing.")
            break
        res["policy_key"] = key
        res["cohort"] = e["cohort"]
        (out_dir / f"{key}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        st = {}
        for r in res["flags"].values():
            st[r["status"]] = st.get(r["status"], 0) + 1
        sc = res["scores"]
        print(f"{key:15} risk {sc['risk_index_display']:3}  quality {sc['disclosure_quality_display']:3}  "
              f"{'complete' if sc['complete'] else 'INCOMPLETE'}  " + ", ".join(f"{k} {v}" for k, v in sorted(st.items())))
        done.append(key)

    meta = {"run_name": run_name, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "config_file": repo_relative(cfg.source), "mode": "batch" if args.batch else "per_flag", "policies": done,
            "stopped": stopped, **ex.run_metadata()}
    (out_dir / "run.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"\n{len(done)} policies | LLM calls {ex.stats['llm_calls']} | cache hits {ex.stats['cache_hits']} | "
          f"wrote {out_dir.relative_to(REPO_ROOT)}")
    return 2 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
