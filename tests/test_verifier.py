"""Quote verifier tests: synthetic policy + one real snapshot (OpenAI) to check sentence IDs."""
import json
from pathlib import Path

import pytest

from privascore.verifier import PolicyDoc, verify_quote

REPO = Path(__file__).resolve().parents[1]

POLICY = """Privacy Policy
1. What we collect
We collect the prompts you submit and information about your device. We also receive data from partners.
2. Retention
We keep chats for 30 days after you delete them. Logs are kept “as long as necessary”.
"""


@pytest.fixture(scope="module")
def doc():
    return PolicyDoc(POLICY, "TEST")


def test_sentence_ids(doc):
    # line 3 is the first non-heading paragraph: p003 with two sentences
    assert doc.sentences["p003.s1"]["text"].startswith("We collect the prompts")
    assert doc.sentences["p003.s2"]["text"] == "We also receive data from partners."
    assert doc.heading_of["p005.s1"] == "2. Retention"


def test_exact(doc):
    r = verify_quote(doc, "We keep chats for 30 days after you delete them", ["p005.s1"])
    assert r.ok and r.status == "exact" and r.sids == ["p005.s1"]
    assert POLICY[r.start:r.end] == "We keep chats for 30 days after you delete them"


def test_normalized_quotes_case_and_spaces(doc):
    r = verify_quote(doc, 'logs are   kept "as long as necessary"', ["p005.s2"])
    assert r.ok and r.status == "normalized" and r.sids == ["p005.s2"]


def test_compact_ignores_punctuation(doc):
    r = verify_quote(doc, "Logs are kept as long as necessary", ["p005.s2"])
    assert r.ok and r.status == "normalized"


def test_paraphrase_rejected_with_diagnostic(doc):
    r = verify_quote(doc, "We retain conversations for thirty days after deletion", ["p005.s1"])
    assert not r.ok and r.status == "not_found"
    assert r.closest_score is not None and r.closest_text      # shown to the LLM on retry


def test_fuzzy_near_miss_still_rejected(doc):
    # one word changed: high similarity, but evidence must be verbatim
    r = verify_quote(doc, "We keep chats for 30 days after you remove them", ["p005.s1"])
    assert not r.ok and r.closest_score > 80


def test_quote_in_wrong_sentence(doc):
    r = verify_quote(doc, "We also receive data from partners", ["p005.s1"])
    assert not r.ok and r.status == "outside_cited" and r.sids == ["p003.s2"]


def test_without_cited_sids_searches_whole_text(doc):
    r = verify_quote(doc, "We also receive data from partners")
    assert r.ok and r.sids == ["p003.s2"]


def test_too_short_and_empty(doc):
    assert verify_quote(doc, "partners").status == "too_short"
    assert verify_quote(doc, "data from partners", ["p003.s2"]).status == "too_short"   # fragment
    assert verify_quote(doc, "  ").status == "empty"


def test_short_whole_sentence_allowed():
    # e.g. a grievance-officer contact line; 2 words but the entire sentence
    d = PolicyDoc("Contact\nGrievance Officer\nEmail: dpo@example.in\n", "T")
    sid = next(s for s, v in d.sentences.items() if v["text"] == "Email: dpo@example.in")
    r = verify_quote(d, "Email: dpo@example.in", [sid])
    assert r.ok and r.sids == [sid]


def test_ellipsis_parts_each_verified(doc):
    ok = verify_quote(doc, "We collect the prompts you submit ... We also receive data from partners",
                      ["p003.s1", "p003.s2"])
    assert ok.ok and ok.sids == ["p003.s1", "p003.s2"]
    bad = verify_quote(doc, "We collect the prompts you submit ... and sell them to advertisers", ["p003.s1"])
    assert not bad.ok


def test_unknown_cited_id_does_not_crash(doc):
    r = verify_quote(doc, "We also receive data from partners", ["p999.s9"])
    assert not r.ok and r.status == "outside_cited"


def test_real_snapshot_ids_match_gold_packet():
    """The verifier's sentence IDs must be identical to the human evidence packets."""
    manifest = json.loads((REPO / "gold_set/policies/manifest.json").read_text())
    e = manifest["P01_openai"]
    text = (REPO / "gold_set" / e["text_file"]).read_text(encoding="utf-8")
    packet = json.loads((REPO / "gold_set/evidence/P01_openai_evidence.json").read_text(encoding="utf-8"))
    doc = PolicyDoc(text, "P01")
    assert set(doc.sentences) == set(packet["sentences"])
    for sid, s in packet["sentences"].items():
        assert (doc.sentences[sid]["start"], doc.sentences[sid]["end"]) == (s["start"], s["end"])
    r = verify_quote(doc, "we may use Content you provide us to improve our Services", ["p036.s1"])
    assert r.ok and r.sids == ["p036.s1"]
