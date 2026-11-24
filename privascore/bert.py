"""Fine-tuned OPP-115 BERT (multi-label, 10 categories) used as a local paragraph classifier.

Loads an EXISTING checkpoint only; nothing is trained here. Before any output is trusted,
`sanity_gate` re-scores the OPP-115 test split and must reproduce the macro F1 stored in the
seed's result.json (threshold 0.5) and the stored test probabilities.

    .venv/bin/python -I -m privascore.bert --sanity        # run the gate only
"""
import json
from pathlib import Path

import numpy as np

from .flags import REPO_ROOT

DEFAULT_RUN_DIR = REPO_ROOT / "models" / "Bert_seed_44"
OPP115_DIR = REPO_ROOT / "data" / "opp115"
LABELS = json.loads((OPP115_DIR / "opp115_label_map.json").read_text())
CATEGORIES = [LABELS[str(i)] for i in range(10)]
THRESHOLD = 0.5          # fixed, never tuned on the gold set
MAX_LENGTH = 256         # same as training / predict_bert_external.py


def _device():
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class OPP115Bert:
    def __init__(self, run_dir: Path = DEFAULT_RUN_DIR, device: str | None = None):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.run_dir = Path(run_dir)
        self.result = json.loads((self.run_dir / "result.json").read_text())
        self.checkpoint = self.run_dir / "checkpoints" / Path(self.result["best_checkpoint"]).name
        self.device = device or _device()
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.checkpoint))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(self.checkpoint)).to(self.device).eval()
        assert self.model.config.problem_type == "multi_label_classification"
        assert self.model.config.num_labels == 10
        self._torch = torch

    def predict(self, texts, batch_size: int = 32) -> np.ndarray:
        """Sigmoid probabilities, shape (n, 10), in CATEGORIES order."""
        torch = self._torch
        # sort by length so batches pad less; restore order at the end
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = np.zeros((len(texts), 10), dtype=np.float32)
        with torch.no_grad():
            for k in range(0, len(order), batch_size):
                idx = order[k:k + batch_size]
                enc = self.tokenizer([texts[i] for i in idx], truncation=True, max_length=MAX_LENGTH,
                                     padding=True, return_tensors="pt").to(self.device)
                logits = self.model(**enc).logits.float().cpu().numpy()
                out[idx] = 1.0 / (1.0 + np.exp(-logits))
        return out


def sanity_gate(bert: OPP115Bert, tol: float = 0.003) -> dict:
    from sklearn.metrics import f1_score
    rows = [json.loads(l) for l in (OPP115_DIR / "opp115_test.jsonl").read_text().splitlines() if l.strip()]
    y = np.array([r["labels"] for r in rows], dtype=int)
    probs = bert.predict([r["text"] for r in rows])
    rescored = float(f1_score(y, (probs >= THRESHOLD).astype(int), average="macro", zero_division=0))
    stored = float(bert.result["test"]["fixed_0.5"]["macro_f1"])
    res = {"n": len(rows), "stored_macro_f1": round(stored, 4), "rescored_macro_f1": round(rescored, 4),
           "device": bert.device, "checkpoint": bert.checkpoint.name}
    stored_probs_path = bert.run_dir / "test_probs.npy"
    if stored_probs_path.exists():
        sp = np.load(stored_probs_path)
        if sp.shape == probs.shape:
            res["max_abs_prob_diff_vs_stored"] = float(np.abs(sp - probs).max())
            res["label_flips_vs_stored"] = int(((sp >= THRESHOLD) != (probs >= THRESHOLD)).sum())
    res["passed"] = abs(rescored - stored) <= tol
    return res


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    ap.add_argument("--sanity", action="store_true")
    ap.add_argument("--device")
    a = ap.parse_args(argv)
    bert = OPP115Bert(a.run_dir, a.device)
    res = sanity_gate(bert)
    print(json.dumps(res, indent=1))
    return 0 if res["passed"] else 3


if __name__ == "__main__":
    import sys
    sys.exit(main())
