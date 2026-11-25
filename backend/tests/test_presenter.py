"""presenter.py mapping rules and the four warnings (sections 6.7 and 5.5)."""
from __future__ import annotations

import asyncio

import pytest

from app.pipeline import PipelineService, utf16_offsets
from app.presenter import present
from app.settings import Settings


@pytest.fixture(scope="module")
def pipeline():
    return PipelineService(Settings(llm_provider="mock", bert="off", bert_required=False))


def run(pipeline, text, scope="all_users", company=None):
    raw = asyncio.run(pipeline.analyse(text, scope, company))
    return present(text, raw, pipeline, source="live", company_name=company)


# --- utf16_offsets (gotcha 6)

def test_utf16_offsets_are_identity_without_astral_characters():
    u = utf16_offsets("plain ascii and accents: éüñ")
    assert all(u(i) == i for i in range(29))


def test_utf16_offsets_count_surrogate_pairs_as_two():
    t = "a\U0001F600b\U0001F600c"
    u = utf16_offsets(t)
    assert [u(i) for i in range(len(t) + 1)] == [0, 1, 3, 4, 6, 7]
    buf = t.encode("utf-16-le")
    assert buf[2 * u(4):2 * u(5)].decode("utf-16-le") == "c"


# --- warnings

def test_few_line_breaks_warning_for_one_giant_line(pipeline, policy_text):
    one_line = policy_text.replace("\n", " ")
    codes = [w.code for w in run(pipeline, one_line).warnings]
    assert "FEW_LINE_BREAKS" in codes


def test_no_few_line_breaks_warning_for_normal_text(pipeline, policy_text):
    assert "FEW_LINE_BREAKS" not in [w.code for w in run(pipeline, policy_text).warnings]


def test_no_matches_warning_and_no_llm_call_for_lorem_ipsum(pipeline):
    lorem = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor.\n"
             "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi.\n") * 20
    r = run(pipeline, lorem)
    assert "NO_MATCHES" in [w.code for w in r.warnings]
    assert r.meta.llm_calls == 0                       # nothing matched, so nothing was asked
    assert all(f.status == "no_candidates" for f in r.flags if f.id != "AI2")


def test_mock_and_bert_warnings_are_always_present_in_this_configuration(pipeline, policy_text):
    codes = [w.code for w in run(pipeline, policy_text).warnings]
    assert "MOCK_PROVIDER" in codes and "BERT_UNAVAILABLE" in codes


def test_every_warning_has_a_message(pipeline, policy_text):
    for w in run(pipeline, policy_text.replace("\n", " ")).warnings:
        assert w.message and not w.message.startswith("None")


# --- mapping rules

def test_flags_are_always_all_16_in_pipeline_order(pipeline, policy_text):
    r = run(pipeline, policy_text)
    assert [f.id for f in r.flags] == [f.id for f in pipeline.flagset.flags]


def test_evidence_text_is_the_policys_own_characters(pipeline, policy_text):
    """A "normalized" match means the model's quote differs from the policy (curly quotes, case).
    The response must always carry text[start:end], never the model's string."""
    r = run(pipeline, policy_text)
    for f in r.flags:
        for e in f.evidence:
            a, b = e.offset_utf16
            assert policy_text[a:b] == e.text


def test_state_meaning_is_the_verbatim_rule_text_for_ed_cd_ee(pipeline, policy_text):
    r = run(pipeline, policy_text)
    rules = pipeline.rules["flags"]
    for f in r.flags:
        if f.state in ("ED", "CD", "EE"):
            assert f.state_meaning == rules[f.id][f.state]
        else:
            assert f.state_meaning in (
                "The policy says nothing usable about this practice.",
                "The policy addresses this, but the wording is contradictory or too vague to classify.")


def test_not_applicable_flags_carry_their_reason_and_no_points(pipeline, policy_text):
    by_id = {f.id: f for f in run(pipeline, policy_text).flags}
    dpdp4 = by_id["DPDP4"]
    assert dpdp4.applicable is False and dpdp4.weight == 0
    assert dpdp4.not_applicable_reason == "informational flag (weight 0)"
    assert dpdp4.max_risk_points == 0 and dpdp4.quality_points == 0


def test_ai2_is_not_scored_when_ai1_is_not_ed_or_cd(pipeline, policy_text):
    by_id = {f.id: f for f in run(pipeline, policy_text).flags}
    assert by_id["AI1"].state not in ("ED", "CD")
    assert by_id["AI2"].status == "not_applicable" and by_id["AI2"].applicable is False
    assert by_id["AI2"].n_candidates == 0 and by_id["AI2"].n_search_terms == 0


def test_document_paragraph_offsets_match_the_text(pipeline, policy_text):
    r = run(pipeline, policy_text)
    assert r.document.paragraphs
    for p in r.document.paragraphs[:50]:
        a, b = p.offset_utf16
        assert policy_text[a:b].strip() == policy_text[a:b]      # no leading/trailing whitespace
    assert r.document.text is None                                # never the input text, live mode


def test_policy_counts(pipeline, policy_text):
    r = run(pipeline, policy_text)
    assert r.policy.chars == len(policy_text)
    assert r.policy.sentences > 0
    assert 0 < r.policy.paragraphs <= len(r.document.paragraphs)
    assert len(r.policy.text_sha256) == 64


def test_company_name_is_lowercased_only_for_the_self_name_lookup(pipeline, policy_text):
    r = run(pipeline, policy_text, company="Razorpay")
    assert r.policy.company_name == "Razorpay"            # shown as typed
    assert run(pipeline, policy_text, company="   ").policy.company_name is None


def test_vagueness_examples_are_renamed_for_the_api(pipeline, policy_text):
    """The pipeline calls them sid/categories; the API contract says sentence_id/cues."""
    ex = run(pipeline, policy_text).metrics.vagueness.examples
    assert ex and all(e.sentence_id.startswith("p") and e.cues for e in ex)
