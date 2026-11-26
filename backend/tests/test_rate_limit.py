"""The quota guard: a per-client limit and a global daily budget.

These exist because /evaluate spends a real Gemini call on the server's key. Per-client limiting
alone does not protect the key, since a handful of addresses can each stay under the limit, so
the global budget is the figure that actually bounds the day's spend.

No client address is stored. The limiter keys on a salted hash, in memory, with the salt
regenerated each boot, so the table cannot be turned back into a list of who visited.
"""
from __future__ import annotations

import pytest

from privascore.flags import REPO_ROOT

from app.limits import RateLimiter


def test_a_client_can_make_its_allowance_then_is_refused():
    clock = [1000.0]
    rl = RateLimiter(per_client=3, window_s=3600, daily_budget=100, now=lambda: clock[0])

    for _ in range(3):
        assert rl.check("1.2.3.4") is None
    refused = rl.check("1.2.3.4")
    assert refused is not None and refused > 0, "the fourth call is refused with a wait"


def test_one_client_running_out_does_not_block_another():
    clock = [1000.0]
    rl = RateLimiter(per_client=2, window_s=3600, daily_budget=100, now=lambda: clock[0])
    for _ in range(2):
        rl.check("1.1.1.1")
    assert rl.check("1.1.1.1") is not None
    assert rl.check("2.2.2.2") is None, "a different client still has its own allowance"


def test_the_allowance_comes_back_after_the_window():
    clock = [1000.0]
    rl = RateLimiter(per_client=1, window_s=60, daily_budget=100, now=lambda: clock[0])
    assert rl.check("1.2.3.4") is None
    assert rl.check("1.2.3.4") is not None
    clock[0] += 61
    assert rl.check("1.2.3.4") is None, "the window has passed, so the allowance is back"


def test_the_daily_budget_stops_a_crowd_that_each_stay_under_the_per_client_limit():
    """The point of the global cap. Twenty clients, each well inside its own allowance, must
    still not be able to spend more than the day's budget of provider calls."""
    clock = [1000.0]
    rl = RateLimiter(per_client=5, window_s=3600, daily_budget=10, now=lambda: clock[0])

    allowed = sum(rl.check(f"10.0.0.{i}") is None for i in range(20))
    assert allowed == 10, f"the daily budget must cap total calls, got {allowed}"


def test_the_daily_budget_resets_the_next_day():
    clock = [1000.0]
    rl = RateLimiter(per_client=5, window_s=3600, daily_budget=2, now=lambda: clock[0])
    assert rl.check("1.1.1.1") is None
    assert rl.check("2.2.2.2") is None
    assert rl.check("3.3.3.3") is not None, "budget spent"
    clock[0] += 86_401
    assert rl.check("3.3.3.3") is None, "a new day, a new budget"


def test_no_client_address_is_kept_anywhere_in_the_limiter():
    """Section 6.8 is privacy-first. Rate limiting needs to tell clients apart, which it can do
    from a salted hash; it never needs to be able to name them."""
    rl = RateLimiter(per_client=5, window_s=3600, daily_budget=100)
    rl.check("203.0.113.77")
    blob = repr(rl.__dict__)
    assert "203.0.113.77" not in blob, "the raw address must not be retained"


def test_two_boots_do_not_produce_the_same_key_for_an_address():
    """The salt is per-process, so even the hashes cannot be correlated across restarts or
    compared against a precomputed table of every IPv4 address."""
    a = RateLimiter(per_client=5, window_s=3600, daily_budget=100)
    b = RateLimiter(per_client=5, window_s=3600, daily_budget=100)
    assert a._key("203.0.113.77") != b._key("203.0.113.77")


def test_old_entries_are_dropped_so_the_table_cannot_grow_without_bound():
    clock = [1000.0]
    rl = RateLimiter(per_client=1, window_s=60, daily_budget=100_000, now=lambda: clock[0])
    for i in range(500):
        rl.check(f"10.1.{i // 256}.{i % 256}")
    assert len(rl._hits) == 500
    clock[0] += 61
    rl.check("10.9.9.9")
    assert len(rl._hits) == 1, "entries older than the window are forgotten"


# --------------------------------------------------------------------- the endpoint

def test_evaluate_refuses_once_the_client_allowance_is_gone(client_factory, policy_text):
    with client_factory(rate_limit_per_client=1, rate_limit_window_s=3600) as c:
        assert c.post("/api/v1/evaluate", json={"text": policy_text}).status_code == 200
        r = c.post("/api/v1/evaluate", json={"text": policy_text})
        assert r.status_code == 429
        assert r.json()["error"]["code"] == "RATE_LIMITED"
        assert r.headers.get("Retry-After"), "a 429 must say when to come back"


def test_turning_the_limiter_off_restores_the_old_behaviour(client_factory, policy_text):
    with client_factory(rate_limit_per_client=0) as c:
        for _ in range(3):
            assert c.post("/api/v1/evaluate", json={"text": policy_text}).status_code == 200


def test_reading_the_saved_examples_is_never_rate_limited(client_factory):
    """Examples cost no provider call, so they are not what the limiter is defending."""
    with client_factory(rate_limit_per_client=1) as c:
        for _ in range(5):
            assert c.get("/api/v1/examples/P06").status_code == 200


@pytest.mark.parametrize("trust", [True, False])
def test_a_forwarded_header_is_only_believed_when_the_deployment_says_to(trust):
    """Behind a proxy the socket address is the proxy's, so X-Forwarded-For has to be read. With
    no proxy it is the client talking, so it must be ignored."""
    from app.limits import client_identity

    scope_ip = "10.0.0.1"
    headers = {"x-forwarded-for": "1.2.3.4, 203.0.113.9"}
    got = client_identity(scope_ip, headers, trust_proxy=trust, hops=1)
    assert got == ("203.0.113.9" if trust else scope_ip)


# ------------------------------------------------- what the security review found

def test_a_request_refused_as_busy_does_not_spend_the_daily_budget(client_factory, policy_text):
    """The budget exists to bound provider spend. A request refused with BUSY never reaches the
    provider, so charging it would let anyone exhaust the day's budget with rapid requests that
    cost the key nothing: a denial of service against the guard itself."""
    import asyncio

    with client_factory(rate_limit_per_client=0, rate_limit_daily_budget=5) as c:
        app = c.app
        # Hold the only permit, so every request below is refused with BUSY.
        app.state.gate = asyncio.Semaphore(0)

        for _ in range(5):
            r = c.post("/api/v1/evaluate", json={"text": policy_text})
            assert r.status_code == 429 and r.json()["error"]["code"] == "BUSY"

        assert app.state.rate_limiter._day_count == 0, \
            "a BUSY request must not be charged against the day's provider budget"


def test_the_forwarded_header_cannot_be_spoofed_by_the_client():
    """X-Forwarded-For is APPENDED to by each proxy, so anything the client puts there survives
    on the LEFT. Reading the left-most entry therefore reads the client's own claim, which hands
    it an unlimited supply of identities even behind a trusted proxy. With one trusted hop the
    real address is the right-most entry, the one the proxy itself added."""
    from app.limits import client_identity

    spoofed = {"x-forwarded-for": "1.2.3.4, 203.0.113.9"}
    got = client_identity("10.0.0.1", spoofed, trust_proxy=True, hops=1)
    assert got == "203.0.113.9", "must use the entry the trusted proxy added, not the client's"


def test_two_trusted_hops_skip_both_of_our_own_proxies():
    from app.limits import client_identity

    # client -> CDN (appends client) -> load balancer (appends CDN) -> app
    headers = {"x-forwarded-for": "1.2.3.4, 203.0.113.9, 198.51.100.7"}
    assert client_identity("10.0.0.1", headers, trust_proxy=True, hops=2) == "203.0.113.9"


def test_a_short_forwarded_header_falls_back_to_the_socket_address():
    """Fewer entries than configured hops means the header did not come through the expected
    chain. Trusting it then would be trusting the client, so use the socket address."""
    from app.limits import client_identity

    headers = {"x-forwarded-for": "1.2.3.4"}
    assert client_identity("10.0.0.1", headers, trust_proxy=True, hops=2) == "10.0.0.1"


def test_the_image_does_not_trust_a_proxy_by_default():
    """Believing the header without a proxy in front lets any client mint identities, so the
    default has to fail closed. Without it every client shares one bucket, which is restrictive
    rather than unsafe."""
    from app.settings import Settings

    assert Settings().trust_proxy is False

    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "PRIVASCORE_TRUST_PROXY=true" not in dockerfile, \
        "the image must not enable proxy trust for every deployment"


def test_a_provider_outage_does_not_drain_the_daily_budget(client_factory, policy_text):
    """Observed live: Gemini answered 503 twice and each attempt still cost a budget slot.

    The budget bounds what is spent at the provider. A 503 means the provider produced nothing
    and charged nothing, so charging our own budget for it lets an outage quietly eat the day's
    allowance and leave real users refused once the provider recovers.
    """
    from privascore.llm import ProviderOverloaded

    with client_factory(rate_limit_per_client=0, rate_limit_daily_budget=5) as c:
        def boom(*a, **k):
            exc = ProviderOverloaded("gemini: still overloaded")
            exc.completed_llm_calls = 0           # the provider never answered, so never billed
            raise exc

        c.app.state.pipeline.analyse = boom

        r = c.post("/api/v1/evaluate", json={"text": policy_text})
        assert r.status_code == 503 and r.json()["error"]["code"] == "LLM_OVERLOADED"
        assert c.app.state.rate_limiter._day_count == 0, \
            "a provider outage must not consume the day's budget"


def test_a_refund_also_returns_the_clients_own_allowance(client_factory, policy_text):
    """Otherwise a user who happened to arrive during an outage would be locked out of the
    retry they are being told to make."""
    from privascore.llm import ProviderOverloaded

    with client_factory(rate_limit_per_client=1, rate_limit_daily_budget=0) as c:
        def boom(*a, **k):
            exc = ProviderOverloaded("gemini: still overloaded")
            exc.completed_llm_calls = 0
            raise exc

        c.app.state.pipeline.analyse = boom
        assert c.post("/api/v1/evaluate", json={"text": policy_text}).status_code == 503

        # The allowance is back, so the retry the 503 invites is actually possible.
        assert c.post("/api/v1/evaluate", json={"text": policy_text}).status_code == 503


def test_an_outage_after_a_billed_call_is_not_refunded(client_factory, policy_text):
    """The refund has to be provable, not assumed.

    extract_policy_batch retries once, so a 503 can arrive AFTER a first call that the provider
    completed and billed. Refunding then would hand back budget for a call we really did spend.
    The extractor counts calls only once they return, so the count at failure time is exactly
    the number billed.
    """
    from privascore.llm import ProviderOverloaded

    with client_factory(rate_limit_per_client=0, rate_limit_daily_budget=5) as c:
        def boom_after_one_billed_call(*a, **k):
            exc = ProviderOverloaded("gemini: overloaded on the retry")
            exc.completed_llm_calls = 1           # the first batch call went through
            raise exc

        c.app.state.pipeline.analyse = boom_after_one_billed_call

        r = c.post("/api/v1/evaluate", json={"text": policy_text})
        assert r.status_code == 503
        assert c.app.state.rate_limiter._day_count == 1, \
            "a call the provider completed must stay charged"


def test_the_pipeline_reports_how_many_calls_were_billed(client, policy_text):
    """The route can only decide this if the pipeline tells it, so the attribute has to be set
    on the exception rather than guessed.

    A plain LLMError is absorbed inside the extractor (those flags become "rejected" and the
    result is a 200 with complete=false), so the escaping cases are the quota family.
    """
    from privascore.llm import ProviderOverloaded

    pipeline = client.app.state.pipeline

    def explode(system, user):
        raise ProviderOverloaded("mock: overloaded on the first call")

    original = pipeline.client.complete_json
    pipeline.client.complete_json = explode
    try:
        # Real policy text, because filler matches no flag candidates and the extractor then
        # skips the provider entirely (skip_llm_when_no_candidates).
        with pytest.raises(ProviderOverloaded) as caught:
            pipeline._extract(policy_text, "all_users", None)
        assert caught.value.completed_llm_calls == 0, \
            "nothing returned, so nothing was billed"
    finally:
        pipeline.client.complete_json = original
