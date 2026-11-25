"""The happy path, the offsets, and the length limits."""
from __future__ import annotations

import json

from privascore.flags import load_flags

INTERNAL_KEYS = {"history", "batch_calls", "shown", "search_log", "problems", "error", "raw",
                 "dropped_evidence", "attempts", "presence", "discarded_answer_status"}


def _keys(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        out |= set(obj)
        for v in obj.values():
            _keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, out)
    return out


def _post(client, text, **kw):
    return client.post("/api/v1/evaluate", json={"text": text, **kw})


def test_happy_path(client, policy_text):
    r = _post(client, policy_text, company_name="Razorpay")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["api_version"] == "1" and d["source"] == "live"
    assert d["policy"]["company_name"] == "Razorpay"
    assert d["policy"]["chars"] == len(policy_text)
    assert [f["id"] for f in d["flags"]] == [f.id for f in load_flags().flags]
    assert r.headers["cache-control"] == "no-store"


def test_scores_present_and_in_range(client, policy_text):
    sc = _post(client, policy_text).json()["scores"]
    assert 0 <= sc["risk_index"] <= 100 and 0 <= sc["disclosure_quality"] <= 100
    assert sc["risk_index_display"] == int(sc["risk_index"] + 0.5)      # half-up, not banker's
    assert isinstance(sc["complete"], bool)
    assert sc["scoring_version"] == "1.0"
    assert sc["n_not_stated"] <= sc["n_applicable"]


def test_every_offset_slices_the_text_back_to_the_quote(client, policy_text):
    text = policy_text.replace("\r\n", "\n").replace("\r", "\n")
    d = _post(client, policy_text).json()
    n = 0
    for f in d["flags"]:
        for e in f["evidence"]:
            a, b = e["offset_utf16"]
            assert text[a:b] == e["text"], (f["id"], e["sentence_id"])
            n += 1
    assert n > 0, "the fixture should produce at least one verified quote"


def test_utf16_offsets_with_an_emoji_before_the_quotes(client, policy_text):
    text = "\U0001F600 emoji first line\n" + policy_text
    d = _post(client, text).json()
    buf = text.encode("utf-16-le")
    n = 0
    for f in d["flags"]:
        for e in f["evidence"]:
            a, b = e["offset_utf16"]
            assert buf[2 * a:2 * b].decode("utf-16-le") == e["text"], (f["id"], e["sentence_id"])
            n += 1
    assert n > 0


def test_paragraph_offsets_are_utf16_too(client, policy_text):
    text = "\U0001F600 emoji first line\n" + policy_text
    d = _post(client, text).json()
    buf = text.encode("utf-16-le")
    first = d["document"]["paragraphs"][0]
    a, b = first["offset_utf16"]
    assert buf[2 * a:2 * b].decode("utf-16-le") == "\U0001F600 emoji first line"


def test_no_internal_keys_anywhere_in_the_response(client, policy_text):
    d = _post(client, policy_text).json()
    assert not (_keys(d) & INTERNAL_KEYS), sorted(_keys(d) & INTERNAL_KEYS)
    assert "text" not in d["document"] or d["document"]["text"] is None


def test_the_input_text_is_not_echoed_back(client, policy_text):
    body = _post(client, policy_text).text
    # Verified quotes ARE returned (that is the product), but not the whole document.
    assert policy_text[:2000] not in body


def test_flag_fields(client, policy_text):
    d = _post(client, policy_text).json()
    for f in d["flags"]:
        assert f["state"] in ("ED", "CD", "EE", "NS", "UN")
        assert f["state_meaning"]
        assert f["status"] in ("verified", "verified_partial", "absent_unverifiable",
                              "no_candidates", "not_applicable", "rejected")
        assert f["dropped_evidence_count"] >= 0
        assert f["max_risk_points"] >= f["risk_points"] >= 0
    by_id = {f["id"]: f for f in d["flags"]}
    # DPDP4 is informational (weight 0) and never scored.
    assert by_id["DPDP4"]["weight"] == 0 and by_id["DPDP4"]["applicable"] is False
    assert by_id["DPDP4"]["not_applicable_reason"]
    # Rationale is the model's own; the pipeline's internal boilerplate is suppressed.
    assert by_id["AI2"]["status"] == "not_applicable" and by_id["AI2"]["rationale"] is None


def test_metrics_shape(client, policy_text):
    m = _post(client, policy_text).json()["metrics"]
    assert m["readability"]["words"] > 0 and m["readability"]["fk_grade"] > 0
    assert 0 <= m["vagueness"]["vague_sentence_fraction"] <= 1
    assert set(m["vagueness"]["cues_per_1000_words"]) == {
        "conditionality", "generalization", "modality", "numeric_quantifier"}
    for e in m["vagueness"]["examples"]:
        assert e["sentence_id"] and e["text"] and e["cues"]
    assert len(m["vagueness"]["examples"]) <= 5


def test_bert_off_reports_unavailable_with_a_warning(client, policy_text):
    d = _post(client, policy_text).json()
    assert d["metrics"]["bert_profile"] == {"available": False, "reason": "disabled",
                                            "paragraphs": None, "threshold": None, "categories": None}
    assert "BERT_UNAVAILABLE" in [w["code"] for w in d["warnings"]]


def test_mock_provider_is_always_announced(client, policy_text):
    d = _post(client, policy_text).json()
    assert "MOCK_PROVIDER" in [w["code"] for w in d["warnings"]]
    assert d["meta"]["provider"] == "mock"


def test_meta_versions(client, policy_text):
    meta = _post(client, policy_text).json()["meta"]
    assert meta["prompt_version"] == "1.0" and meta["rules_version"] == "1.1"
    assert meta["llm_calls"] == 1                      # batch mode: ONE call for all 16 flags
    assert set(meta["timings_ms"]) == {"metrics", "extraction", "total"}
    assert meta["analysed_at"].endswith("Z")


def test_scope_consumer_is_accepted(client, policy_text):
    assert _post(client, policy_text, scope="consumer").json()["policy"]["scope"] == "consumer"


def test_too_short(client):
    r = _post(client, "short policy. " * 10)
    assert r.status_code == 422 and r.json()["error"]["code"] == "TEXT_TOO_SHORT"


def test_too_long(client, policy_text):
    r = _post(client, "a" * 200_001)
    assert r.status_code == 422 and r.json()["error"]["code"] == "TEXT_TOO_LONG"


def test_body_too_large(client):
    r = client.post("/api/v1/evaluate", content=json.dumps({"text": "x" * 2_000_000}),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "BODY_TOO_LARGE"
