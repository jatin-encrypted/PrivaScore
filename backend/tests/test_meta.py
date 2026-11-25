"""/health and /meta, and the startup wiring they prove."""
from __future__ import annotations

from privascore.flags import load_flags


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "provider": "mock", "model": "mock", "bert": "disabled"}


def test_meta_lists_all_16_flags_in_pipeline_order(client):
    m = client.get("/api/v1/meta").json()
    assert [f["id"] for f in m["flags"]] == [f.id for f in load_flags().flags]
    assert len(m["flags"]) == 16


def test_meta_flag_fields_come_from_the_pipeline(client):
    m = client.get("/api/v1/meta").json()
    by_id = {f["id"]: f for f in m["flags"]}
    src = {f.id: f for f in load_flags().flags}
    for fid, f in by_id.items():
        assert f["question"] == src[fid].question
        assert f["weight"] == src[fid].weight
        assert f["type"] == src[fid].type
        assert f["group"] in ("general", "ai", "dpdp")
        assert f["title"]
        # ED/CD/EE are the verbatim rule texts the model was given; NS/UN are the shared texts.
        assert all(f["state_meanings"][s] for s in ("ED", "CD", "EE", "NS", "UN"))


def test_meta_versions_and_limits(client):
    m = client.get("/api/v1/meta").json()
    assert m["versions"]["scoring"] == "1.0"
    assert m["versions"]["privascore"] == "0.1.0"
    assert m["limits"]["min_chars"] == 1000 and m["limits"]["max_chars"] == 200_000
    assert len(m["bert"]["categories"]) == 10


def test_api_key_never_appears_in_meta_or_health(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-123")
    for path in ("/api/v1/health", "/api/v1/meta"):
        assert "test-secret-123" not in client.get(path).text


def test_body_too_large_is_rejected_before_parsing(client):
    r = client.post("/api/v1/meta", content=b"x" * 10,
                    headers={"Content-Length": "2000000", "Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "BODY_TOO_LARGE"


def test_unknown_path_is_404(client):
    assert client.get("/api/v1/nope").status_code == 404
