"""
verify_best_checkpoint.py - investigate the "missing LayerNorm.weight/bias,
unexpected LayerNorm.gamma/beta" warning printed after each BERT run.

HYPOTHESIS (from reading the Transformers 5.21.0 source)
-----------------------------------------------------------
  save:  Trainer._save -> model.save_pretrained(save_original_format=True by
         default) reverts the loader's renaming, so checkpoint files store
         LayerNorm.gamma / LayerNorm.beta (the original BERT naming).
  load:  Trainer._load_best_model reads that file with safetensors and calls
         model.load_state_dict(state_dict, strict=False). No renaming is
         applied, so gamma/beta are "unexpected", the model's weight/bias are
         "missing", and strict=False skips them silently.
  result: after trainer.train(), every parameter comes from the BEST epoch
         EXCEPT the LayerNorm weights/biases, which keep their LAST-epoch
         values. Everything evaluated afterwards (val@0.5, test@0.5, saved
         probs) used that mixed model.
  from_pretrained() DOES apply the renaming, so it loads a checkpoint correctly.

WHAT THIS SCRIPT CHECKS (no retraining; reads the saved checkpoints)
-----------------------------------------------------------------------
 1. Library versions.
 2. Which LayerNorm key names are physically in each checkpoint file.
 3. Whether from_pretrained maps gamma->weight / beta->bias exactly
    (loaded param == raw tensor stored under the gamma/beta name).
 4. How far LayerNorm params moved between the best and the last checkpoint.
 5. Scores for three models per seed, on validation and test at threshold 0.5:
      correct_best : from_pretrained(best checkpoint)            <- what you meant
      as_reported  : best weights + LAST-epoch LayerNorm params   <- what the run used
      last         : from_pretrained(last checkpoint)
    and whether `as_reported` reproduces the numbers in seed_X/result.json.

CAVEAT: this needs both the best AND the last checkpoint on disk. Trainer keeps
both when save_total_limit=1 and they differ. If the Colab session was reset
and bert_runs/ is gone, use train_bert_opp115.py (patched) to re-run instead.

USAGE (Colab, same folder layout as the training run)
  python verify_best_checkpoint.py --runs-dir bert_runs --data-dir . --seeds 42,43,44
  python verify_best_checkpoint.py --runs-dir bert_runs --keys-only      # no torch needed
"""
import argparse
import json
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
from safetensors import safe_open

LN_KEY = re.compile(r"^bert\..*LayerNorm\.(gamma|beta|weight|bias)$")  # encoder body only; excludes cls.* head


def pkg_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"


def checkpoints(seed_dir: Path):
    cks = sorted((p for p in (seed_dir / "checkpoints").glob("checkpoint-*") if p.is_dir()),
                 key=lambda p: int(p.name.split("-")[-1]))
    if not cks:
        raise SystemExit(f"No checkpoints under {seed_dir / 'checkpoints'} - rerun with the patched training script.")
    return cks


def best_and_last(cks):
    last = cks[-1]
    state = json.loads((last / "trainer_state.json").read_text())
    best_name = Path(state["best_model_checkpoint"]).name  # recorded path may be an old absolute path
    best = next((c for c in cks if c.name == best_name), None)
    if best is None:
        raise SystemExit(f"Best checkpoint {best_name} not on disk (have {[c.name for c in cks]}).")
    return best, last, state


def ln_key_report(ckpt: Path):
    with safe_open(str(ckpt / "model.safetensors"), framework="numpy") as f:
        keys = [k for k in f.keys() if LN_KEY.match(k)]
    kinds = {k: sum(1 for x in keys if x.endswith("." + k)) for k in ("gamma", "beta", "weight", "bias")}
    return keys, kinds


def raw_ln_tensors(ckpt: Path, keys):
    with safe_open(str(ckpt / "model.safetensors"), framework="numpy") as f:
        return {k: f.get_tensor(k) for k in keys}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", type=Path, default=Path("bert_runs"))
    ap.add_argument("--data-dir", type=Path, default=Path("."))
    ap.add_argument("--label-map", type=Path, default=Path("opp115_label_map.json"))
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--keys-only", action="store_true", help="only inspect checkpoint files (no torch/transformers)")
    ap.add_argument("--out", type=Path, default=Path("verify_report.json"))
    args = ap.parse_args()

    print("== 1. versions ==")
    for p in ("transformers", "torch", "safetensors", "accelerate"):
        print(f"  {p}: {pkg_version(p)}")

    report = {"versions": {p: pkg_version(p) for p in ("transformers", "torch", "safetensors")}, "seeds": {}}
    plan = {}
    for seed in [int(s) for s in args.seeds.split(",")]:
        sd = args.runs_dir / f"seed_{seed}"
        best, last, state = best_and_last(checkpoints(sd))
        plan[seed] = (best, last)
        keys_b, kinds_b = ln_key_report(best)
        print(f"\n== seed {seed} ==\n  best={best.name} (metric {state['best_metric']:.4f})  last={last.name}")
        print(f"== 2. LayerNorm key names stored in {best.name}/model.safetensors (encoder body) ==")
        print(f"  gamma={kinds_b['gamma']} beta={kinds_b['beta']} weight={kinds_b['weight']} bias={kinds_b['bias']}"
              f"   -> {'LEGACY gamma/beta naming on disk' if kinds_b['gamma'] else 'weight/bias naming on disk'}")
        entry = {"best": best.name, "last": last.name, "ln_key_kinds": kinds_b}
        if best != last:
            rb, rl = raw_ln_tensors(best, keys_b), raw_ln_tensors(last, ln_key_report(last)[0])
            num = np.sqrt(sum(float(((rb[k] - rl[k]) ** 2).sum()) for k in rb))
            den = np.sqrt(sum(float((rb[k] ** 2).sum()) for k in rb))
            mx = max(float(np.abs(rb[k] - rl[k]).max()) for k in rb)
            print(f"== 4. LayerNorm drift best->last: relative L2 = {num / den:.2e}, max |delta| = {mx:.2e}")
            entry["ln_drift"] = {"rel_l2": num / den, "max_abs": mx}
        else:
            print("== 4. best == last checkpoint: nothing differs, the reload quirk cannot matter for this seed")
        report["seeds"][seed] = entry

    if args.keys_only:
        args.out.write_text(json.dumps(report, indent=2))
        print(f"\n(keys-only) wrote {args.out}")
        return

    # ---------------- model-level checks (need torch + transformers) ----------------
    import torch
    from sklearn.metrics import f1_score
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    texts, labels = {}, {}
    for s in ("validation", "test"):
        rows = [json.loads(l) for l in (args.data_dir / f"opp115_{s}.jsonl").read_text().splitlines() if l.strip()]
        texts[s] = [r["text"] for r in rows]
        labels[s] = np.array([r["labels"] for r in rows], dtype=int)

    @torch.no_grad()
    def macro_f1(model, tok, split):
        model.eval().to(dev)
        probs = []
        for i in range(0, len(texts[split]), 64):
            enc = tok(texts[split][i:i + 64], truncation=True, max_length=args.max_length,
                      padding=True, return_tensors="pt").to(dev)
            # match Trainer.predict: fp16 autocast on GPU
            with torch.autocast(dev, dtype=torch.float16, enabled=(dev == "cuda")):
                logits = model(**enc).logits
            probs.append(torch.sigmoid(logits.float()).cpu().numpy())
        pred = (np.concatenate(probs) >= 0.5).astype(int)
        return float(f1_score(labels[split], pred, average="macro", zero_division=0))

    def ln_names(model):
        return [n for n, _ in model.named_parameters() if "LayerNorm" in n and n.startswith("bert.")]

    for seed, (best, last) in plan.items():
        print(f"\n== seed {seed}: model-level checks ==")
        tok = AutoTokenizer.from_pretrained(str(best))
        m_best = AutoModelForSequenceClassification.from_pretrained(str(best))
        m_last = AutoModelForSequenceClassification.from_pretrained(str(last))

        # 3. does from_pretrained map gamma->weight / beta->bias exactly?
        keys_b, _ = ln_key_report(best)
        raw = raw_ln_tensors(best, keys_b)
        sd = dict(m_best.named_parameters())
        bad = 0
        for k, arr in raw.items():
            name = k.replace("LayerNorm.gamma", "LayerNorm.weight").replace("LayerNorm.beta", "LayerNorm.bias")
            if not np.array_equal(sd[name].detach().cpu().numpy(), arr):
                bad += 1
        print(f"== 3. from_pretrained: {len(raw) - bad}/{len(raw)} LayerNorm tensors equal the stored gamma/beta "
              f"-> mapping {'OK' if bad == 0 else 'FAILED'}")

        # as_reported = best weights + last-epoch LayerNorm params
        m_mix = AutoModelForSequenceClassification.from_pretrained(str(best))
        last_params = dict(m_last.named_parameters())
        with torch.no_grad():
            for n, p in m_mix.named_parameters():
                if n in ln_names(m_mix):
                    p.copy_(last_params[n])

        res = {name: {s: macro_f1(m, tok, s) for s in ("validation", "test")}
               for name, m in (("correct_best", m_best), ("as_reported", m_mix), ("last", m_last))}
        stored = json.loads((args.runs_dir / f"seed_{seed}" / "result.json").read_text())
        rep = {s: stored[s]["fixed_0.5"]["macro_f1"] for s in ("validation", "test")}
        print(f"== 5. macro F1 @0.5 (validation / test)")
        print(f"   stored in result.json   : {rep['validation']:.4f} / {rep['test']:.4f}")
        for name in ("as_reported", "correct_best", "last"):
            print(f"   {name:<24}: {res[name]['validation']:.4f} / {res[name]['test']:.4f}")
        d_test = res["correct_best"]["test"] - rep["test"]
        match = abs(res["as_reported"]["test"] - rep["test"]) <= 2e-3
        print(f"   as_reported reproduces stored numbers (|diff|<=0.002): {match}")
        print(f"   effect of the reload quirk on test macro F1 (correct_best - stored): {d_test:+.4f}")
        report["seeds"][seed].update({"stored": rep, "rescored": res, "mapping_ok": bad == 0,
                                      "as_reported_matches_stored": match, "delta_test": d_test})
        del m_best, m_last, m_mix

    deltas = [v["delta_test"] for v in report["seeds"].values()]
    ctest = [v["rescored"]["correct_best"]["test"] for v in report["seeds"].values()]
    print(f"\nTest macro F1 with correctly restored best checkpoints: mean {np.mean(ctest):.4f} "
          f"(std {np.std(ctest):.4f}); change vs stored per seed: {[round(d, 4) for d in deltas]}")
    args.out.write_text(json.dumps(report, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
