# PrivaScore backend

FastAPI layer around the frozen `privascore` pipeline. Nothing in `privascore/` is modified;
`app/pipeline.py` is the only module that imports it.

## Install

Into the **same** root `.venv` (the pipeline must be installed with `-e`, see the brief):

```bash
.venv/bin/pip install -e ".[bert,dev]"
.venv/bin/pip install -r backend/requirements.txt
```

## Run

```bash
# real pipeline (Gemini + BERT)
.venv/bin/uvicorn app.main:app --app-dir backend --port 8000 --no-access-log

# frontend work: no quota, no BERT, no API key
PRIVASCORE_LLM_PROVIDER=mock PRIVASCORE_BERT=off PRIVASCORE_BERT_REQUIRED=false \
  .venv/bin/uvicorn app.main:app --app-dir backend --port 8000 --reload --no-access-log
```

One worker only (each worker loads its own BERT, ~0.5 GB) and `--no-access-log` (uvicorn's
access log records client IPs).

## Test

```bash
.venv/bin/python -m pytest -q tests backend/tests     # pipeline + backend, no network, no key
```

## Endpoints

| Method + path | Purpose |
|---|---|
| `POST /api/v1/evaluate` | analyse pasted text; one blocking request, can take a minute or more |
| `GET /api/v1/health` | `{status, provider, model, bert}` |
| `GET /api/v1/meta` | limits, the 16 flags with questions and state meanings, categories, versions |

`MAX_CONCURRENT` is 1: a second analysis while one runs gets `429 BUSY` straight away rather
than queueing, which protects the Gemini quota and the client's shared throttle.

`/docs` and `/openapi.json` are served in `dev` and disabled when `PRIVASCORE_ENV=prod`.

## Privacy

Policy text lives only in request-local variables. `InMemoryExtractor` bypasses the on-disk LLM
reply cache (`.cache/llm/`), the 422 handler returns field names without values, and the request
log line carries no IP, body, text or company name. Configuration is `PRIVASCORE_*` environment
variables (`app/settings.py`); `GEMINI_API_KEY` is read by `privascore` itself and is never a
settings field.
