# syntax=docker/dockerfile:1

# ---- Base: Python 3.13 slim ----
FROM python:3.13-slim

# yt-dlp needs ffmpeg for merging/format conversion; the /health route probes it.
# ca-certificates keeps TLS working for outbound requests (YouTube/Instagram).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Bring in the uv binary from the official image (fast, reproducible installs).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Don't buffer stdout/stderr, don't write .pyc, and let uv install into the system env.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

WORKDIR /app

# Install deps first (cached until the lockfile changes) — no dev group, frozen to uv.lock.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Now copy the application code.
COPY app ./app

# Temp download dir (contents are ephemeral on Render; cleaned up on startup).
RUN mkdir -p downloads

# Render (and most PaaS) inject $PORT; default to 8000 for local runs.
ENV PULLVID_HOST=0.0.0.0 \
    PULLVID_PORT=8000
EXPOSE 8000

# Shell form so $PORT expands; falls back to 8000 when unset.
CMD uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
