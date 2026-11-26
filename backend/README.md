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

## Deploying

One container serves both the API and the built frontend, so a deployment is a single origin
with no CORS and nothing to keep in sync. Build it from the **repository root**:

```sh
docker build -f backend/Dockerfile -t privascore .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=...                   \
  -e PRIVASCORE_LLM_PROVIDER=gemini       \
  -e PRIVASCORE_LLM_MODEL=gemini-3.6-flash \
  privascore
```

On Render, Fly or similar: point the service at `backend/Dockerfile` with the build context set
to the repository root, and set those three variables as secrets. The platform supplies `$PORT`.

### BERT is off in the image

torch, transformers and the checkpoint come to about 1.2 GB, and they are needed only for the
paragraph category chart on a **freshly pasted** policy. The 15 saved analyses keep their full
category chart either way, because those numbers were precomputed into `runs/policy_metrics/`.
A live analysis without BERT shows a plain "category profile unavailable" note and is otherwise
complete. The image is roughly 300 MB instead of 1.5 GB and runs in well under 512 MB of RAM.

To deploy the full stack instead: install the `bert` extra, mount
`models/Bert_seed_44/checkpoints/`, and set `PRIVASCORE_BERT=on`. Budget about 2 GB of RAM.

### Protecting the API key

`/evaluate` spends a real provider call on whatever key the server holds, so the image ships
with rate limiting on:

| Variable | Default | What it does |
|---|---|---|
| `PRIVASCORE_RATE_LIMIT_PER_CLIENT` | `10` | analyses per client per window; `0` disables |
| `PRIVASCORE_RATE_LIMIT_WINDOW_S` | `3600` | the window |
| `PRIVASCORE_RATE_LIMIT_DAILY_BUDGET` | `200` | total analyses per day across everyone; `0` disables |
| `PRIVASCORE_TRUST_PROXY` | `true` in the image | read `X-Forwarded-For`. Only correct behind a proxy |

The **daily budget** is the figure that actually bounds the day's spend. A per-client limit
alone does not: a handful of addresses each staying politely under their allowance can still
run far more than a day's quota between them.

`PRIVASCORE_TRUST_PROXY` must be `false` when nothing sits in front of the app. The header is
trivially spoofable, so believing it without a proxy hands every client an unlimited supply of
fresh identities.

Counters are in memory, keyed by a salted hash of the address, with the salt regenerated each
boot: no database (section 6.8 forbids one) and no record of who visited. They are also
per-process, so running more than one worker multiplies the effective limit by the worker count.
Keep it to one worker, which also matches `max_concurrent=1`.

### If the provider variables are missing

`privascore.example.toml` applies, which is `provider = "mock"`. The app still starts and every
response carries a `MOCK_PROVIDER` warning, so placeholder labels cannot be mistaken for a real
analysis. Check `/api/v1/health` after deploying: it reports the live provider, model and BERT
status.
