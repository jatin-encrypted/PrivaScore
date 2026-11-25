"""Backend tests: mock provider, BERT off, no network, no API key needed.

The environment is set before app.settings is imported so Settings picks it up.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

os.environ.update(
    PRIVASCORE_LLM_PROVIDER="mock",
    PRIVASCORE_BERT="off",
    PRIVASCORE_BERT_REQUIRED="false",
    PRIVASCORE_ENV="dev",
)

FIXTURE = REPO_ROOT / "gold_set" / "policies" / "text" / "P11_razorpay.txt"


@pytest.fixture(scope="session")
def policy_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app
    with TestClient(create_app()) as c:      # `with` runs the lifespan
        yield c


@pytest.fixture
def client_no_reraise():
    """Like `client`, but returns the 500 response instead of re-raising the exception, so the
    production behaviour of the unhandled-exception handler can be asserted."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def client_factory():
    """A client with settings overridden, for the cases where the default app is the wrong shape
    (examples turned off, a different run directory)."""
    import contextlib

    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.settings import Settings

    @contextlib.contextmanager
    def make(**overrides):
        with TestClient(create_app(Settings(**overrides))) as c:
            yield c

    return make
