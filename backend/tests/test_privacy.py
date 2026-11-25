"""Section 6.8 is a promise to the user: "PrivaScore does not store or log your text."

These tests are the proof. A canary string is put into the policy text and must not appear in
any log record, any error body, or any file on disk.
"""
from __future__ import annotations

import logging
import time

from privascore.flags import REPO_ROOT

CANARY = "ZEBRA-CANARY-7731"
IGNORE = ("__pycache__", ".pytest_cache", ".git/", ".venv/", "node_modules")


def _with_canary(text: str) -> str:
    return f"{CANARY} is a sentence we inserted for the privacy test.\n{text}"


def _all_log_text(caplog) -> str:
    parts = []
    for rec in caplog.records:
        parts += [str(rec.getMessage()), str(rec.args), str(rec.msg)]
        if rec.exc_info and rec.exc_info[1]:
            parts.append(repr(rec.exc_info[1]))
        if rec.exc_text:
            parts.append(rec.exc_text)
    return "\n".join(parts)


def _listing() -> set[str]:
    return {str(p.relative_to(REPO_ROOT)) for p in REPO_ROOT.rglob("*")
            if p.is_file() and not any(i in str(p.relative_to(REPO_ROOT)) for i in IGNORE)}


def test_the_text_never_reaches_the_logs(client, policy_text, caplog):
    with caplog.at_level(logging.DEBUG):
        r = client.post("/api/v1/evaluate", json={"text": _with_canary(policy_text),
                                                  "company_name": "AcmeCorpCanary"})
    assert r.status_code == 200
    logs = _all_log_text(caplog)
    assert CANARY not in logs
    assert "AcmeCorpCanary" not in logs                 # no company name either
    assert "ZEBRA" not in logs


def test_the_request_log_line_has_no_content_and_no_client_details(client, policy_text, caplog):
    with caplog.at_level(logging.INFO, logger="privascore.api"):
        client.post("/api/v1/evaluate", json={"text": policy_text})
    line = next(m for m in (r.getMessage() for r in caplog.records) if "duration_ms" in m)
    assert "/api/v1/evaluate" in line and "status=200" in line and "request_id=" in line
    for forbidden in ("testclient", "python-httpx", "user-agent", "127.0.0.1", "sha256"):
        assert forbidden not in line.lower()


def test_a_422_does_not_echo_the_text_back(client):
    r = client.post("/api/v1/evaluate", json={"text": f"{CANARY} too short"})
    assert r.status_code == 422
    assert CANARY not in r.text
    assert r.json()["error"]["code"] == "TEXT_TOO_SHORT"


def test_a_schema_422_returns_field_names_without_values(client):
    r = client.post("/api/v1/evaluate", json={"text": 12345, "nope": CANARY})
    assert r.status_code == 422
    assert CANARY not in r.text and "12345" not in r.text
    err = r.json()["error"]
    assert err["code"] == "INVALID_REQUEST"
    assert set(err["fields"]) == {"text", "nope"}       # names only, no `input` echo


def test_nothing_is_written_to_disk(client, policy_text):
    before = _listing()
    cache = REPO_ROOT / ".cache" / "llm"
    n_cache_before = len(list(cache.glob("*"))) if cache.exists() else 0
    assert client.post("/api/v1/evaluate", json={"text": _with_canary(policy_text)}).status_code == 200
    n_cache_after = len(list(cache.glob("*"))) if cache.exists() else 0
    assert n_cache_after == n_cache_before, "InMemoryExtractor must not touch .cache/llm/"
    assert _listing() - before == set(), "the request created files in the repo"


def test_the_canary_is_not_in_any_file_afterwards(client, policy_text):
    """Only files CHANGED by the request count as a leak.

    Scanning every file in the repo looked stricter but was wrong: any file that merely contains
    the canary string for an unrelated reason (the build brief uses it as an example) failed the
    test on a machine that had one, while nothing had actually been written.

    _local/ is deliberately NOT added to IGNORE. A real leak into that folder has to stay
    visible, and the mtime check is what makes an unchanged file there harmless.

    The window is the request itself. A filesystem with coarse mtime granularity could in
    principle stamp a file written early in the request just below `start`; that would be a
    missed leak rather than a false alarm, and no mainstream filesystem used here is that coarse.
    """
    start = time.time()
    client.post("/api/v1/evaluate", json={"text": _with_canary(policy_text)})
    hits = []
    for p in REPO_ROOT.rglob("*"):
        rel = str(p.relative_to(REPO_ROOT))
        if not p.is_file() or any(i in rel for i in IGNORE) or rel.startswith("backend/tests"):
            continue
        try:
            if p.stat().st_mtime < start:
                continue          # unchanged since before the request
            if CANARY in p.read_text(encoding="utf-8", errors="ignore"):
                hits.append(rel)
        except OSError:
            pass
    assert hits == []


def test_the_api_key_is_never_returned_or_logged(client, policy_text, monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-123")
    with caplog.at_level(logging.DEBUG):
        r = client.post("/api/v1/evaluate", json={"text": policy_text})
    assert "test-secret-123" not in r.text
    assert "test-secret-123" not in _all_log_text(caplog)
    assert "test-secret-123" not in client.get("/api/v1/meta").text
    assert "test-secret-123" not in client.get("/api/v1/health").text


def test_the_settings_object_has_no_api_key_field(monkeypatch):
    """privascore reads GEMINI_API_KEY from the environment itself. If it were also a Settings
    field, its value would ride along in any repr, log line or validation error."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-123")
    from app.settings import Settings
    s = Settings()
    assert not any(w in f.lower() for f in type(s).model_fields
                   for w in ("key", "secret", "token", "password"))
    # The point is the VALUE, not the provider's name: examples_run legitimately names the model.
    assert "test-secret-123" not in repr(s)


def test_dropped_quotes_are_counted_but_never_sent(client, policy_text):
    """A quote the verifier rejected is model-invented text; only its count may be shown."""
    import json as _json

    from privascore.llm.mock import MockClient

    pipeline = client.app.state.pipeline
    real = pipeline.client.complete_json

    def fake(system, user):
        resp = real(system, user)
        data = _json.loads(resp.text)
        # Add one fabricated quote to the first answer; the verifier must drop it.
        data["answers"][0]["evidence"].append(
            {"id": data["answers"][0]["evidence"][0]["id"],
             "quote": "PINEAPPLE-FABRICATED-QUOTE that is not in the policy at all"})
        resp.text = _json.dumps(data)
        return resp

    assert isinstance(pipeline.client, MockClient)
    pipeline.client.complete_json = fake
    try:
        r = client.post("/api/v1/evaluate", json={"text": policy_text})
    finally:
        pipeline.client.complete_json = real
    assert r.status_code == 200
    assert "PINEAPPLE-FABRICATED-QUOTE" not in r.text
    assert sum(f["dropped_evidence_count"] for f in r.json()["flags"]) >= 1


def test_the_cache_bypass_is_what_prevents_the_write(client, policy_text, tmp_path):
    """Proof that InMemoryExtractor is load-bearing.

    The base Extractor only caches when the provider is not "mock", so a mock-only test would
    pass even with the override deleted. Telling the client it is "gemini" makes the base class
    take its caching path while MockClient still answers locally: no network, real coverage.
    """
    from privascore.extractor import Extractor

    from app.pipeline import InMemoryExtractor

    p = client.app.state.pipeline
    p.client.settings.provider = "gemini"
    try:
        base_dir, mem_dir = tmp_path / "base", tmp_path / "mem"
        Extractor(p.client, p.flagset, p.cfg.extractor, cache_dir=base_dir).extract_policy_batch(
            policy_text, policy_id="t")
        assert list(base_dir.glob("*.json")), "the base class is expected to cache replies"

        InMemoryExtractor(p.client, p.flagset, p.cfg.extractor, cache_dir=mem_dir).extract_policy_batch(
            policy_text, policy_id="t")
        assert not mem_dir.exists(), "InMemoryExtractor must not create its cache directory"
    finally:
        p.client.settings.provider = "mock"
