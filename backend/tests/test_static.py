"""Serving the built frontend from the same process, so a deployment is one URL.

One origin means no CORS to configure and no second service to keep alive. The API must keep
precedence over the static mount, or a built file could shadow an endpoint.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def built(tmp_path):
    """A stand-in for frontend/dist."""
    (tmp_path / "index.html").write_text("<!doctype html><title>PrivaScore</title>", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hi')", encoding="utf-8")
    return tmp_path


def test_the_app_is_served_at_the_root(client_factory, built):
    with client_factory(static_dir=str(built)) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "PrivaScore" in r.text


def test_assets_are_served(client_factory, built):
    with client_factory(static_dir=str(built)) as c:
        r = c.get("/assets/app.js")
        assert r.status_code == 200
        assert "console.log" in r.text


def test_the_api_still_wins_over_the_static_mount(client_factory, built):
    """The mount is at "/", so it would swallow everything if it were matched first."""
    with client_factory(static_dir=str(built)) as c:
        assert c.get("/api/v1/health").json()["status"] == "ok"
        assert c.get("/api/v1/examples").status_code == 200


def test_an_unknown_api_path_is_still_a_json_404_not_the_app_shell(client_factory, built):
    """A missing endpoint must not return index.html with status 200: a client checking the
    API would read the HTML as a successful response."""
    with client_factory(static_dir=str(built)) as c:
        r = c.get("/api/v1/nope")
        assert r.status_code == 404
        assert "text/html" not in r.headers.get("content-type", "")


def test_without_a_build_the_api_runs_on_its_own(client_factory):
    """Local development serves the frontend from Vite, so no build is present."""
    with client_factory(static_dir="") as c:
        assert c.get("/api/v1/health").status_code == 200
        assert c.get("/").status_code == 404


def test_a_missing_static_dir_does_not_stop_the_server(client_factory):
    """A deployment misconfiguration should degrade to an API-only service, not a crash loop."""
    with client_factory(static_dir="/no/such/directory") as c:
        assert c.get("/api/v1/health").status_code == 200
