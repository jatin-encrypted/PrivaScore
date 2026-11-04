"""
smoke_test_bert_pipeline.py - verify train_bert_opp115.py end-to-end WITHOUT
downloading bert-base-uncased (no network / no GPU needed).

It builds a tiny randomly-initialised BERT (2 layers, 64 hidden) and a
WordPiece vocab from the OPP-115 training text, saves both to a local
folder, then runs the real training script against that folder on a small
subset. Scores will be near-meaningless (random tiny model, 1 CPU); the point
is to confirm: data loading, split checks, tokenisation, weighted-BCE loss,
early stopping, checkpoint reload, threshold tuning, metric/JSON/npy output.
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
SCRIPT = Path(__file__).parent / "train_bert_opp115.py"
WORK = Path("smoke_tmp")
model_dir = WORK / "tiny_bert"
model_dir.mkdir(parents=True, exist_ok=True)

words = Counter()
for line in (DATA / "opp115_train.jsonl").read_text().splitlines():
    words.update(re.findall(r"[a-z0-9]+", json.loads(line)["text"].lower()))
vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"] + [w for w, _ in words.most_common(1500)]
(model_dir / "vocab.txt").write_text("\n".join(vocab))

tok = BertTokenizerFast(vocab_file=str(model_dir / "vocab.txt"), do_lower_case=True)
tok.save_pretrained(model_dir)
cfg = BertConfig(vocab_size=len(vocab), hidden_size=64, num_hidden_layers=2, num_attention_heads=2,
                 intermediate_size=128, max_position_embeddings=512, num_labels=10,
                 problem_type="multi_label_classification")
BertForSequenceClassification(cfg).save_pretrained(model_dir)

cmd = [sys.executable, str(SCRIPT), "--data-dir", str(DATA),
       "--label-map", str(DATA / "opp115_label_map.json"),
       "--out-dir", str(WORK / "runs"), "--model-name", str(model_dir),
       "--seeds", "42,43", "--epochs", "3", "--patience", "2", "--lr", "1e-3",
       "--batch-size", "16", "--max-length", "128",
       "--max-train-samples", "320", "--max-eval-samples", "160"]
print("RUN:", " ".join(cmd))
sys.exit(subprocess.call(cmd))
