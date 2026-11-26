"""Switching to a second model when the main one hits its usage limit or is overloaded.

Gemini counts usage limits per model, so when gemini-3.6-flash is used up, gemini-3.5-flash-lite
still has its own allowance. Every result names the model that actually produced it.
"""
from __future__ import annotations

import re

from privascore.llm import LLMResponse, ProviderOverloaded, QuotaExhausted

FALLBACK = "lite-model"
MAIN = "mock"                     # the model name the mock provider reports


class Limited:
    """Stands in for a model whose limit has been reached: every call is refused."""

    def __init__(self, exc=QuotaExhausted):
        self.exc, self.calls = exc, 0

    def __call__(self, system, user):
        self.calls += 1
        raise self.exc("mock: limit reached")


class BilledThenLimited:
    """The first call is answered (and so billed) but its reply is unusable, which makes the
    extractor ask again; the second call hits the limit."""

    def __init__(self):
        self.calls, self.first_flags = 0, None

    def __call__(self, system, user):
        self.calls += 1
        if self.calls == 1:
            self.first_flags = re.findall(r"^FLAG: (\S+)", user, re.MULTILINE)
            return LLMResponse("not json", "mock", MAIN, {}, {})
        raise QuotaExhausted("mock: limit reached on the retry")


def _analyse(c, text):
    return c.post("/api/v1/evaluate", json={"text": text})


def test_without_a_fallback_a_limit_is_still_an_error(client_factory, policy_text):
    with client_factory(llm_fallback_model="") as c:
        p = c.app.state.pipeline
        assert len(p.models) == 1 and p.fallback_model is None
        p.client.complete_json = Limited()

        r = _analyse(c, policy_text)
        assert r.status_code == 429 and r.json()["error"]["code"] == "LLM_QUOTA"


def test_a_limit_on_the_main_model_switches_to_the_fallback(client_factory, policy_text):
    with client_factory(llm_fallback_model=FALLBACK) as c:
        main, lite = c.app.state.pipeline.models
        main.client.complete_json = Limited()

        r = _analyse(c, policy_text)
        assert r.status_code == 200
        assert r.json()["meta"]["model"] == FALLBACK, "the result must name the model that produced it"
        assert len(lite.client.calls) >= 1


def test_an_overloaded_main_model_also_switches(client_factory, policy_text):
    with client_factory(llm_fallback_model=FALLBACK) as c:
        main, _ = c.app.state.pipeline.models
        main.client.complete_json = Limited(ProviderOverloaded)

        r = _analyse(c, policy_text)
        assert r.status_code == 200 and r.json()["meta"]["model"] == FALLBACK


def test_later_requests_skip_the_limited_model(client_factory, policy_text):
    """Once the main model is known to be limited, asking it again on every request would only
    add a refusal before each analysis."""
    with client_factory(llm_fallback_model=FALLBACK, llm_fallback_cooldown_s=600) as c:
        main, _ = c.app.state.pipeline.models
        limited = main.client.complete_json = Limited()

        assert _analyse(c, policy_text).json()["meta"]["model"] == FALLBACK
        assert limited.calls == 1
        assert _analyse(c, policy_text).json()["meta"]["model"] == FALLBACK
        assert limited.calls == 1, "the limited model must not be asked again during the cooldown"


def test_the_main_model_is_used_again_after_the_cooldown(client_factory, policy_text):
    with client_factory(llm_fallback_model=FALLBACK, llm_fallback_cooldown_s=0) as c:
        main, _ = c.app.state.pipeline.models
        main.client.complete_json = Limited()
        assert _analyse(c, policy_text).json()["meta"]["model"] == FALLBACK

        del main.client.complete_json             # its limit has reset
        assert _analyse(c, policy_text).json()["meta"]["model"] == MAIN


def test_when_both_models_are_limited_the_user_gets_the_limit_error(client_factory, policy_text):
    with client_factory(llm_fallback_model=FALLBACK, rate_limit_per_client=0,
                        rate_limit_daily_budget=5) as c:
        main, lite = c.app.state.pipeline.models
        main.client.complete_json, lite.client.complete_json = Limited(), Limited()

        r = _analyse(c, policy_text)
        assert r.status_code == 429 and r.json()["error"]["code"] == "LLM_QUOTA"
        assert main.client.complete_json.calls == 1 and lite.client.complete_json.calls == 1
        assert c.app.state.rate_limiter._day_count == 0, "neither model answered, so nothing is charged"


def test_a_call_billed_before_both_limits_stays_charged(client_factory, policy_text):
    """The refund rule from the rate limiter still holds across two models: only an attempt
    that no model answered is refunded."""
    with client_factory(llm_fallback_model=FALLBACK, rate_limit_per_client=0,
                        rate_limit_daily_budget=5) as c:
        main, lite = c.app.state.pipeline.models
        main.client.complete_json, lite.client.complete_json = BilledThenLimited(), Limited()

        assert _analyse(c, policy_text).status_code == 429
        assert c.app.state.rate_limiter._day_count == 1


def test_the_fallback_reruns_the_whole_analysis(client_factory, policy_text):
    """One result never mixes two models' answers: the fallback is asked about every flag, not
    only the ones the main model had not finished."""
    with client_factory(llm_fallback_model=FALLBACK) as c:
        main, lite = c.app.state.pipeline.models
        billed = main.client.complete_json = BilledThenLimited()

        r = _analyse(c, policy_text)
        assert r.status_code == 200 and r.json()["meta"]["model"] == FALLBACK
        assert lite.client.calls[0]["flags"] == billed.first_flags
        assert r.json()["meta"]["llm_calls"] == 1 + len(lite.client.calls), \
            "the main model's answered call still counts"


def test_health_reports_which_model_is_in_use(client_factory, policy_text):
    with client_factory(llm_fallback_model=FALLBACK) as c:
        h = c.get("/api/v1/health").json()
        assert h["model"] == MAIN and h["fallback_model"] == FALLBACK and h["active_model"] == MAIN

        c.app.state.pipeline.models[0].client.complete_json = Limited()
        _analyse(c, policy_text)
        assert c.get("/api/v1/health").json()["active_model"] == FALLBACK


def test_a_fallback_equal_to_the_main_model_is_ignored(client_factory):
    with client_factory(llm_fallback_model=MAIN) as c:
        p = c.app.state.pipeline
        assert len(p.models) == 1 and p.fallback_model is None


def test_a_saved_example_names_the_model_of_its_stored_run(client):
    """The server here runs the mock provider, but the saved analyses were produced by the
    stored run, and that is the model the result has to name."""
    meta = client.get("/api/v1/examples/P06").json()["meta"]
    assert meta["model"] == "gemini-3.6-flash" and meta["provider"] == "gemini"
