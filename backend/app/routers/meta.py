"""GET /api/v1/health and GET /api/v1/meta. No user content is involved in either."""
from __future__ import annotations

from fastapi import APIRouter, Request

import privascore
from privascore.extractor import PROMPT_VERSION
from privascore.scoring import SCORING_VERSION

from .. import catalog

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    p = request.app.state.pipeline
    return {"status": "ok", "provider": p.provider, "model": p.model, "bert": p.bert_status}


@router.get("/meta")
async def meta(request: Request) -> dict:
    s, p = request.app.state.settings, request.app.state.pipeline
    try:
        from privascore.bert import CATEGORIES, THRESHOLD
        categories, threshold = list(CATEGORIES), THRESHOLD
    except Exception:
        # CATEGORIES lives in privascore.bert, which imports torch. Fall back to the label map
        # the module itself reads, so /meta works on a server without torch installed.
        categories, threshold = _categories_without_torch(), 0.5
    return {
        "api_version": "1",
        "limits": {"min_chars": s.min_chars, "max_chars": s.max_chars,
                   "max_body_bytes": s.max_body_bytes, "max_concurrent": s.max_concurrent},
        "scopes": ["all_users", "consumer"],
        "groups": [{"id": g, "title": t} for g, t in catalog.GROUP_TITLES.items()],
        "flags": [
            {"id": f.id, "key": f.key, "title": catalog.title(f.id), "group": catalog.group(f.id),
             "type": f.type, "weight": f.weight, "question": f.question,
             "state_meanings": {st: catalog.state_meaning(p.rules, f.id, st)
                                for st in ("ED", "CD", "EE", "NS", "UN")}}
            for f in p.flagset.flags
        ],
        "state_labels": catalog.STATE_LABELS,
        "bert": {"status": p.bert_status, "categories": categories, "threshold": threshold},
        "versions": {
            "privascore": privascore.__version__,
            "prompt": PROMPT_VERSION,
            "rules": p.rules["version"],
            "flag_definitions": p.flagset.version,
            "scoring": SCORING_VERSION,
        },
        "provider": p.provider,
        "model": p.model,
        "env": s.env,
    }


def _categories_without_torch() -> list[str]:
    """privascore.bert imports numpy at module level; this reads the same label map it reads,
    so /meta still works on a server that has no ML dependencies installed."""
    import json

    from privascore.flags import REPO_ROOT
    labels = json.loads((REPO_ROOT / "data" / "opp115" / "opp115_label_map.json").read_text(encoding="utf-8"))
    return [labels[str(i)] for i in range(10)]
