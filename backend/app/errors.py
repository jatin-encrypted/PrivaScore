"""One error shape for every failure: {"error": {code, message, retry_after_s}}.

Messages are fixed strings chosen here. Provider and pipeline exception text never reaches the
client (it can quote response bodies, which may contain policy text).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("privascore.api")

MESSAGES = {
    "INVALID_REQUEST": "The request body is not valid.",
    "TEXT_TOO_SHORT": "The text is shorter than the minimum.",
    "TEXT_TOO_LONG": "The text is longer than the maximum.",
    "BODY_TOO_LARGE": "The request body is too large.",
    "BUSY": "Another analysis is running. Try again in about a minute.",
    "LLM_QUOTA": "The analysis provider's usage limit has been reached.",
    "LLM_OVERLOADED": "The analysis provider is overloaded right now.",
    "LLM_ERROR": "The analysis provider failed.",
    "EXAMPLES_UNAVAILABLE": "Saved examples are not available on this server.",
    "EXAMPLE_NOT_FOUND": "There is no saved example with that id.",
    "NOT_FOUND": "Not found.",
    "INTERNAL": "Something went wrong on our side.",
}


class ApiError(Exception):
    def __init__(self, code: str, status: int, retry_after_s: int | None = None, fields: list[str] | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after_s = retry_after_s
        self.fields = fields

    def response(self) -> JSONResponse:
        body = {"error": {"code": self.code, "message": MESSAGES.get(self.code, MESSAGES["INTERNAL"]),
                          "retry_after_s": self.retry_after_s}}
        if self.fields is not None:
            body["error"]["fields"] = self.fields
        headers = {"Retry-After": str(self.retry_after_s)} if self.retry_after_s else None
        return JSONResponse(body, status_code=self.status, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return exc.response()

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # Pydantic's default 422 body echoes the offending `input` value, which would be the
        # policy text. Return field NAMES only.
        fields = sorted({".".join(str(p) for p in e.get("loc", ())[1:]) or "body" for e in exc.errors()})
        return ApiError("INVALID_REQUEST", 422, fields=fields).response()

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "-")
        log.error("unhandled %s request_id=%s", type(exc).__name__, rid)
        return ApiError("INTERNAL", 500).response()
