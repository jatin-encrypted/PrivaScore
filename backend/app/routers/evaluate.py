"""POST /api/v1/evaluate: one blocking analysis of pasted text.

The text exists only in this function's locals and in the worker threads it starts. Nothing is
written to disk, logged or cached.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from privascore.llm import LLMError, ProviderOverloaded, QuotaExhausted

from ..errors import ApiError
from ..limits import client_identity, run_guarded
from ..presenter import present
from ..schemas import EvaluateRequest, EvaluateResponse

router = APIRouter()


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(body: EvaluateRequest, request: Request, response: Response) -> EvaluateResponse:
    s = request.app.state.settings
    pipeline = request.app.state.pipeline
    gate = request.app.state.gate

    # The frontend normalises line endings the same way before sending. Offsets in the response
    # refer to THIS string, so the backend must not change the text in any other way.
    text = body.text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text.strip()) < s.min_chars:
        raise ApiError("TEXT_TOO_SHORT", 422)
    if len(text) > s.max_chars:
        raise ApiError("TEXT_TOO_LONG", 422)

    # BUSY is decided first, and deliberately so. The limiter's budget exists to bound what is
    # spent at the provider; a request refused here never reaches it. Charging those would let
    # anyone exhaust the day's budget with rapid requests that cost the key nothing, which is a
    # denial of service against the guard itself. Neither check awaits, so nothing can slip in
    # between them.
    if gate.locked():
        raise ApiError("BUSY", 429, retry_after_s=30)

    limiter = request.app.state.rate_limiter
    if limiter.enabled:
        who = client_identity(request.client.host if request.client else "unknown",
                              request.headers, s.trust_proxy, s.trusted_proxy_hops)
        wait_s = limiter.check(who)
        if wait_s is not None:
            raise ApiError("RATE_LIMITED", 429, retry_after_s=max(1, int(wait_s)))
    # NOT `async with gate`: the analysis runs in threads that cannot be cancelled, so a client
    # that disconnects would release the permit while its Gemini call was still in flight.
    # run_guarded releases on the work finishing, not on this request finishing.
    try:
        raw = await run_guarded(gate, pipeline.analyse(text, body.scope, body.company_name))
    except ProviderOverloaded:                   # subclass of QuotaExhausted: catch it FIRST
        raise ApiError("LLM_OVERLOADED", 503, retry_after_s=120) from None
    except QuotaExhausted:
        raise ApiError("LLM_QUOTA", 429, retry_after_s=60) from None
    except LLMError:
        # Most LLMErrors are absorbed inside the pipeline (those flags become "rejected" and
        # the result is a 200 with complete=false). Only an escaping one lands here.
        raise ApiError("LLM_ERROR", 502) from None

    response.headers["Cache-Control"] = "no-store"
    return present(text, raw, pipeline, source="live", company_name=body.company_name)
