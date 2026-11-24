"""Combined per-policy metrics (no model needed)."""
import json

import numpy as np
import pytest

from privascore import metrics
from privascore.bert import CATEGORIES
from privascore.textstats import analyse

TEXT = ("Privacy Policy\n"
        "We may share certain information with partners as necessary to provide the service.\n"
        "We delete your chats 30 days after you close your account.\n")


class FakeBert:
    def predict(self, texts):
        p = np.zeros((len(texts), 10), dtype=np.float32)
        p[:, 0] = 0.9                       # every paragraph: First Party
        p[0, 9] = 0.7                       # first paragraph also: Other
        return p


def test_policy_metrics_reuses_textstats():
    m = metrics.policy_metrics(TEXT)
    s = analyse(TEXT)
    assert m["readability"]["fk_grade"] == s.fk_grade
    assert m["vagueness"]["vague_sentence_fraction"] == 0.5
    assert "bert_profile" not in m


def test_bert_profile_shares():
    m = metrics.policy_metrics(TEXT, FakeBert())
    b = m["bert_profile"]
    assert b["paragraphs"] == 3 and list(b["share"]) == CATEGORIES
    assert b["share"]["First Party Collection/Use"] == 1.0
    assert b["share"]["Other"] == round(1 / 3, 3) and b["share"]["Data Retention"] == 0.0


def test_load_refuses_stale_file(tmp_path):
    manifest = json.loads(metrics.MANIFEST.read_text())
    e = next(iter(manifest.values()))
    good = {"policies": {e["id"]: {"name": e["name"], "text_sha256": e["text_sha256"]}}}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(good))
    assert metrics.load_metrics(p)[e["id"]]["name"] == e["name"]
    good["policies"][e["id"]]["text_sha256"] = "0" * 64
    p.write_text(json.dumps(good))
    with pytest.raises(ValueError, match="stale"):
        metrics.load_metrics(p)
