"""GET /api/v1/examples and /api/v1/examples/{policy_id}: the saved gold-set analyses.

No user content is involved, so unlike /evaluate these responses are cacheable and cost nothing.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..errors import ApiError
from ..schemas import EvaluateResponse, ExampleList

router = APIRouter()


def _library(request: Request):
    library = getattr(request.app.state, "examples", None)
    if library is None or not library.available:
        raise ApiError("EXAMPLES_UNAVAILABLE", 404)
    return library


@router.get("/examples", response_model=ExampleList)
async def list_examples(request: Request, response: Response) -> ExampleList:
    library = _library(request)
    response.headers["Cache-Control"] = "public, max-age=300"
    return ExampleList(**library.run_meta, examples=library.summaries())


@router.get("/examples/{policy_id}", response_model=EvaluateResponse)
async def get_example(policy_id: str, request: Request, response: Response) -> EvaluateResponse:
    library = _library(request)
    if policy_id not in library.examples:
        raise ApiError("EXAMPLE_NOT_FOUND", 404)
    response.headers["Cache-Control"] = "public, max-age=300"
    return library.render(policy_id, request.app.state.pipeline)
