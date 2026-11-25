"""create_app(): the FastAPI application.

Run it with ONE worker (each worker would load its own BERT) and --no-access-log (uvicorn's
access log records client IPs):

    .venv/bin/uvicorn app.main:app --app-dir backend --port 8000 --no-access-log
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import privascore

from . import errors, logging_setup
from .errors import ApiError
from .examples import ExampleLibrary
from .pipeline import PipelineService
from .routers import evaluate, examples, meta
from .settings import Settings

log = logging.getLogger("privascore.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s: Settings = app.state.settings
    app.state.pipeline = PipelineService(s)
    app.state.gate = asyncio.Semaphore(s.max_concurrent)
    p = app.state.pipeline
    log.info("ready provider=%s model=%s bert=%s privascore=%s env=%s",
             p.provider, p.model, p.bert_status, privascore.__version__, s.env)
    if p.provider == "mock":
        log.warning("PROVIDER IS MOCK: labels are placeholders, not a real analysis "
                    "(set [llm] provider in privascore.toml, or PRIVASCORE_LLM_PROVIDER)")
    app.state.examples = None
    if s.examples == "on":
        # Verifies 15 text hashes against three files each; no model runs here.
        app.state.examples = ExampleLibrary(s.examples_run)

    if s.bert_sanity == "on" and p.bert is not None:
        from privascore.bert import sanity_gate
        gate = await asyncio.to_thread(sanity_gate, p.bert)
        if not gate.get("passed"):
            raise RuntimeError(f"BERT sanity gate failed: macro_f1={gate.get('rescored_macro_f1')}")
        log.info("bert sanity gate passed macro_f1=%s", gate.get("rescored_macro_f1"))
    yield


def _route_template(request: Request) -> str:
    """The route pattern, never the full URL: no query string, and path parameter values
    (an example id) are put back as {name}. A nested router's own `route.path` is missing the
    /api/v1 prefix, so the template is rebuilt from the request path instead."""
    path = request.scope.get("path") or "unmatched"
    for name, value in (request.scope.get("path_params") or {}).items():
        path = path.replace(str(value), "{" + name + "}")
    return path


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings()
    logging_setup.configure(s.env)
    docs = None if s.env == "prod" else "/docs"
    app = FastAPI(title="PrivaScore API", version="1", lifespan=lifespan,
                  docs_url=docs, redoc_url=None,
                  openapi_url=None if s.env == "prod" else "/openapi.json")
    app.state.settings = s

    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def guard_and_log(request: Request, call_next):
        """Body-size limit, request id, and the only request log line. Never logs the URL query,
        the client IP, the user agent or anything from the body."""
        rid = uuid.uuid4().hex[:12]
        request.state.request_id = rid
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > s.max_body_bytes:
            return ApiError("BODY_TOO_LARGE", 413).response()
        t = time.perf_counter()
        response = await call_next(request)
        log.info("request_id=%s %s %s status=%s duration_ms=%d",
                 rid, request.method, _route_template(request),
                 response.status_code, round((time.perf_counter() - t) * 1000))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.include_router(evaluate.router, prefix="/api/v1", tags=["evaluate"])
    app.include_router(meta.router, prefix="/api/v1", tags=["meta"])
    app.include_router(examples.router, prefix="/api/v1", tags=["examples"])
    errors.install(app)
    return app


app = create_app()
