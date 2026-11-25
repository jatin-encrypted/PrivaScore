"""The saved-example endpoints: integrity of the three hashes, and the shape of what is served.

These run against the real files in gold_set/ and runs/, because the point of the feature is that
those files are consistent. A hash drifting is exactly the failure these tests exist to catch.
"""
from __future__ import annotations

import json

import pytest

from app.examples import ExampleLibrary

RUN = "gemini36_batch_v1.1"


@pytest.fixture(scope="module")
def library():
    return ExampleLibrary(RUN)


def test_every_policy_in_the_manifest_loads(library):
    """If a hash drifts, the example is dropped rather than served with wrong offsets, so a
    short library is the symptom. All 15 should be present."""
    assert len(library.examples) == 15
    assert library.run_meta["model"] == "gemini-3.6-flash"


def test_a_text_file_that_does_not_match_its_hash_is_dropped(tmp_path, monkeypatch):
    """The guard that matters: serving a saved analysis against changed text would highlight the
    wrong words. Point the loader at a mutated text file and the example must disappear."""
    import app.examples as mod

    gold = tmp_path / "gold_set" / "policies"
    gold.mkdir(parents=True)
    manifest = json.loads((mod.GOLD_DIR / "policies" / "manifest.json").read_text())
    one = {"P06_zoom": manifest["P06_zoom"]}
    (gold / "manifest.json").write_text(json.dumps(one))

    original = (mod.GOLD_DIR / one["P06_zoom"]["text_file"]).read_text(encoding="utf-8")
    text_file = tmp_path / "gold_set" / one["P06_zoom"]["text_file"]
    text_file.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(mod, "GOLD_DIR", tmp_path / "gold_set")

    text_file.write_text(original, encoding="utf-8")
    assert len(ExampleLibrary(RUN).examples) == 1, "unmodified text should still load"

    text_file.write_text("x" + original, encoding="utf-8")
    assert ExampleLibrary(RUN).examples == {}, "mutated text must be dropped, not served"


def test_list_endpoint(client):
    r = client.get("/api/v1/examples")
    assert r.status_code == 200
    body = r.json()
    assert body["run"] == RUN
    assert len(body["examples"]) == 15
    first = body["examples"][0]
    assert first["policy_id"] == "P01"
    assert first["company_name"] == "OpenAI"      # not the "openai" slug
    assert 0 <= first["risk_index"] <= 100
    # A summary must not carry the analysis itself.
    assert "flags" not in first and "document" not in first


def test_detail_matches_the_live_contract(client):
    """An example is rendered through the same presenter as /evaluate, so it must satisfy the
    same response model. source is the only field that differs."""
    from app.schemas import EvaluateResponse

    r = client.get("/api/v1/examples/P06")
    assert r.status_code == 200
    parsed = EvaluateResponse.model_validate(r.json())
    assert parsed.source == "example"
    assert parsed.policy.company_name == "Zoom"
    assert parsed.document.text is not None, 'an example must carry its own text'
    assert parsed.policy.chars == len(parsed.document.text)
    assert len(parsed.flags) == 16
    assert parsed.meta.llm_calls == 0, "a saved example must not call the provider"


def test_evidence_quotes_are_the_policys_own_characters(client):
    """The presenter slices the quote out of the text by offset. If the saved offsets were stale
    this is where it would show, so assert it on real saved data rather than trusting the hash."""
    r = client.get("/api/v1/examples/P06")
    doc_text = r.json()["document"]["text"]
    quotes = [e for f in r.json()["flags"] for e in f["evidence"]]
    assert quotes, "Zoom has verified evidence"
    for e in quotes:
        assert e["text"] in doc_text, f"{e['sentence_id']} does not appear in the document"


def test_unknown_id_is_404(client):
    assert client.get("/api/v1/examples/P99").status_code == 404
    assert client.get("/api/v1/examples/P99").json()["error"]["code"] == "EXAMPLE_NOT_FOUND"


def test_examples_can_be_turned_off(client_factory):
    """A deployment without gold_set/ or runs/ must still serve /evaluate."""
    with client_factory(examples="off") as c:
        assert c.get("/api/v1/examples").status_code == 404
        assert c.get("/api/v1/examples").json()["error"]["code"] == "EXAMPLES_UNAVAILABLE"
        assert c.get("/api/v1/health").status_code == 200
