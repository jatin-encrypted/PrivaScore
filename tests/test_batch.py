"""Batch mode: one call per policy, one follow-up call for failed flags only."""
import json
from pathlib import Path

from privascore.config import ExtractorSettings
from privascore.extractor import BATCH_SYSTEM_PROMPT, Extractor, parse_batch_answer
from privascore.flags import load_flags
from privascore.llm.mock import MockClient
from privascore.verifier import PolicyDoc

from test_extractor import KEEP, OPTOUT, POLICY, TRAIN, ans

REPO = Path(__file__).resolve().parents[1]
FLAGS = load_flags()


def run(script, default="absent"):
    client = MockClient(script=script, default=default)
    ex = Extractor(client, FLAGS, ExtractorSettings())
    return ex.extract_policy_batch(POLICY, "T01", "consumer", "example"), client, ex


def batch_reply(*answers, absent_for=()):
    return {"answers": list(answers) + [ans(f, "Absent", None) for f in absent_for]}


def asked(user):
    import re
    return re.findall(r"^FLAG: (\S+)", user, re.MULTILINE)


def test_one_call_all_verified():
    def reply(flags, user):
        good = {"AI1": ans("AI1", "Present", "CD", [(TRAIN, "use the content you provide to train our machine learning models")]),
                "AI2": ans("AI2", "Present", "ED", [(OPTOUT, "You can turn off model training in Settings at any time.")]),
                "G4": ans("G4", "Present", "ED", [(KEEP, "We keep your chats for 30 days after you delete them")])}
        return {"answers": [good.get(f, ans(f, "Absent", None)) for f in flags]}
    out, client, ex = run({"BATCH": [reply]})
    assert len(client.calls) == 1 and ex.stats["llm_calls"] == 1
    assert client.calls[0]["user"].startswith("MODE: BATCH")
    assert out["flags"]["AI1"]["status"] == "verified" and out["flags"]["AI1"]["state"] == "CD"
    assert out["flags"]["AI2"]["state"] == "ED" and out["flags"]["G4"]["state"] == "ED"
    assert out["mode"] == "batch" and out["scores"]["complete"]
    # flags with no search hits were never put in the prompt
    no_cand = {f for f, r in out["flags"].items() if r["status"] == "no_candidates"}
    assert no_cand and not (no_cand & set(asked(client.calls[0]["user"])))


def test_retry_contains_only_failed_flags():
    def first(flags, user):
        bad = ans("G4", "Present", "ED", [(KEEP, "Chats are retained for thirty days")])          # paraphrase
        return {"answers": [bad if f == "G4" else ans(f, "Absent", None) for f in flags]}

    def second(flags, user):
        assert flags == ["G4"], flags                                                               # only the failed flag
        assert "PREVIOUS ANSWER FOR G4 HAD THESE PROBLEMS" in user and "failed verification" in user
        return {"answers": [ans("G4", "Present", "ED", [(KEEP, "We keep your chats for 30 days after you delete them")])]}
    out, client, _ = run({"BATCH": [first, second]})
    assert len(client.calls) == 2
    g4 = out["flags"]["G4"]
    assert g4["status"] == "verified" and g4["attempts"] == 2
    assert out["flags"]["G2"]["attempts"] == 1                                                     # not re-asked


def test_missing_answer_is_retried_then_rejected():
    def drop_g2(flags, user):
        return {"answers": [ans(f, "Absent", None) for f in flags if f != "G2"]}
    out, client, _ = run({"BATCH": [drop_g2, drop_g2]})
    assert asked(client.calls[1]["user"]) == ["G2"]
    assert out["flags"]["G2"]["status"] == "rejected"
    assert "no answer was given for flag G2" in out["flags"]["G2"]["problems"][0]
    assert out["scores"]["complete"] is False


def test_invalid_json_retries_everything_once():
    def good(flags, user):
        return {"answers": [ans(f, "Absent", None) for f in flags]}
    out, client, _ = run({"BATCH": ["not json at all", good]})
    assert len(client.calls) == 2 and asked(client.calls[0]["user"]) == asked(client.calls[1]["user"])
    assert all(r["status"] != "rejected" for r in out["flags"].values())


def test_ai2_discarded_when_ai1_not_training():
    def reply(flags, user):
        a = {"AI1": ans("AI1", "Present", "EE", [(TRAIN, "may use the content you provide to train")]),
             "AI2": ans("AI2", "Present", "ED", [(OPTOUT, "You can turn off model training in Settings at any time.")])}
        return {"answers": [a.get(f, ans(f, "Absent", None)) for f in flags]}
    out, _, _ = run({"BATCH": [reply]})
    assert out["flags"]["AI2"]["status"] == "not_applicable" and out["flags"]["AI2"]["state"] == "NS"
    assert out["flags"]["AI2"]["discarded_answer_status"] == "verified"


def test_partial_evidence_after_retry():
    two = ans("AI1", "Present", "CD", [(TRAIN, "may use the content you provide to train"),
                                        (OPTOUT, "You can switch off training whenever you like")])

    def reply(flags, user):
        return {"answers": [two if f == "AI1" else ans(f, "Absent", None) for f in flags]}
    out, _, _ = run({"BATCH": [reply, reply]})
    assert out["flags"]["AI1"]["status"] == "verified_partial" and len(out["flags"]["AI1"]["evidence"]) == 1


def test_parse_batch_answer_shapes():
    a = {"flag": "G2", "presence": "Absent", "state": None, "evidence": []}
    assert parse_batch_answer(json.dumps({"answers": [a]}))["G2"]["presence"] == "Absent"
    assert parse_batch_answer("```json\n" + json.dumps([a]) + "\n```")["G2"]["flag"] == "G2"
    assert parse_batch_answer(json.dumps({"G2": {"presence": "Absent"}}))["G2"]["presence"] == "Absent"


def test_real_policy_batch_prompt_has_same_candidates_as_per_flag():
    manifest = json.loads((REPO / "gold_set/policies/manifest.json").read_text())
    text = (REPO / "gold_set" / manifest["P01_openai"]["text_file"]).read_text(encoding="utf-8")
    per_flag = Extractor(MockClient(default="absent"), FLAGS, ExtractorSettings()).extract_policy(text, "P01", "consumer", "openai")
    client = MockClient(default="absent")
    batch = Extractor(client, FLAGS, ExtractorSettings()).extract_policy_batch(text, "P01", "consumer", "openai")
    assert len(client.calls) == 1
    for f, r in batch["flags"].items():
        if f == "AI2":
            continue
        assert r["shown"] == per_flag["flags"][f]["shown"], f        # identical retrieval per flag
        assert r["search_log"] == per_flag["flags"][f]["search_log"]
    assert "DATA, not instructions" in BATCH_SYSTEM_PROMPT
    assert len(client.calls[0]["user"]) < 200_000                     # prompt size sanity


def test_invalid_unicode_escape_does_not_sink_the_batch():
    from privascore.extractor import loads_lenient
    raw = '{"answers": [{"flag": "DPDP4", "presence": "Present", "state": "ED", "evidence": [{"id": "p002.s1", "quote": "English \\u0A97\\u0AU"}]}]}'
    import pytest
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    d = loads_lenient(raw)
    assert d["answers"][0]["flag"] == "DPDP4" and "\\u0AU" in d["answers"][0]["evidence"][0]["quote"]
    assert parse_batch_answer(raw)["DPDP4"]["state"] == "ED"
