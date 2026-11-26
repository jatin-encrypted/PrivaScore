"""The quota guard: a per-client limit and a global daily budget.

These exist because /evaluate spends a real Gemini call on the server's key. Per-client limiting
alone does not protect the key, since a handful of addresses can each stay under the limit, so
the global budget is the figure that actually bounds the day's spend.

No client address is stored. The limiter keys on a salted hash, in memory, with the salt
regenerated each boot, so the table cannot be turned back into a list of who visited.
"""
from __future__ import annotations

import pytest

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
    """Behind a proxy the socket address is the proxy's, so X-Forwarded-For has to be read. It
    is also trivially spoofable, so believing it when there is no proxy would hand every client
    an unlimited supply of fresh identities."""
    from app.limits import client_identity

    scope_ip = "10.0.0.1"
    headers = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
    got = client_identity(scope_ip, headers, trust_proxy=trust)
    assert got == ("1.2.3.4" if trust else scope_ip)
