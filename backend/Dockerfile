# Single-origin image: the API also serves the built frontend, so a deployment is one URL
# with no CORS and nothing to keep in sync.
#
# Build it from the REPOSITORY ROOT, not from backend/:
#     docker build -f backend/Dockerfile -t privascore .
#     docker run -p 8000:8000 -e GEMINI_API_KEY=... -e PRIVASCORE_LLM_PROVIDER=gemini \
#                -e PRIVASCORE_LLM_MODEL=gemini-3.6-flash privascore
#
# BERT is off here on purpose. torch, transformers and the checkpoint are about 1.2 GB and are
# needed only for the paragraph category chart on a FRESHLY PASTED policy. The 15 saved
# analyses keep their full category chart regardless, because those numbers were precomputed
# into runs/policy_metrics/. A live analysis without BERT shows a plain "unavailable" note.
# To run the full stack instead, add the bert extra and mount models/Bert_seed_44/checkpoints.
#
# Files are copied path by path rather than with `COPY . .`, so no .dockerignore is needed at
# the repository root and node_modules/ and .venv/ cannot leak into the image.

# ---------------------------------------------------------------- frontend build
FROM node:24-bookworm-slim AS web
WORKDIR /build

# Dependencies first, so a source-only change does not reinstall them.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json ./
COPY frontend/vite.config.ts frontend/index.html ./
COPY frontend/src/ ./src/
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM python:3.13-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dependencies first, again for layer caching. `pip install -e .` needs the package present.
COPY pyproject.toml privascore.example.toml ./
COPY privascore/ ./privascore/
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -e . -r backend/requirements.txt

COPY backend/ ./backend/

# The data the saved analyses are built from. privascore.flags.REPO_ROOT resolves to /app, so
# these keep their repository-relative paths.
# The 16 flag definitions: privascore.flags.load_flags() reads this at startup.
COPY gold_set/flag_definitions.json ./gold_set/flag_definitions.json
COPY gold_set/policies/manifest.json ./gold_set/policies/manifest.json
COPY gold_set/policies/text/ ./gold_set/policies/text/
COPY runs/gemini36_batch_v1.1/ ./runs/gemini36_batch_v1.1/
COPY runs/policy_metrics/ ./runs/policy_metrics/
# Read by /meta to name the 10 OPP-115 categories without importing torch.
COPY data/opp115/opp115_label_map.json ./data/opp115/opp115_label_map.json

COPY --from=web /build/dist ./frontend/dist

ENV PRIVASCORE_ENV=prod \
    PRIVASCORE_BERT=off \
    PRIVASCORE_BERT_REQUIRED=false \
    PRIVASCORE_STATIC_DIR=/app/frontend/dist
# PRIVASCORE_TRUST_PROXY is deliberately NOT set here. X-Forwarded-For is only meaningful
# behind a proxy, and trusting it without one lets any client mint a fresh identity per
# request. Set it (with PRIVASCORE_TRUSTED_PROXY_HOPS) in the specific deployment that has a
# proxy in front. Left off, every client shares one bucket: restrictive, but not unsafe.
# GEMINI_API_KEY, PRIVASCORE_LLM_PROVIDER and PRIVASCORE_LLM_MODEL are supplied at run time.
# Without them privascore.example.toml applies, which is provider = "mock": the app still runs
# and every response carries a MOCK_PROVIDER warning, so placeholder labels cannot be mistaken
# for a real analysis.

# Nothing here needs to write to the filesystem: no database, no cache, no logs to disk.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000
# Shell form, because $PORT is supplied by the platform at run time.
CMD exec uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}
