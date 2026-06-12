# Pullvid — Backend (FastAPI + yt-dlp)

Personal-use, ad-free video downloader backend. Resolves YouTube/Instagram URLs
with [yt-dlp](https://github.com/yt-dlp/yt-dlp), returns curated downloadable
formats, and streams the chosen format back as a file.

> Personal use only. No auth, no multi-tenancy. Runs locally or on a personal VPS.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- `ffmpeg` on `PATH` (required to merge separate video+audio streams). On macOS:
  `brew install ffmpeg`. The server logs a warning at startup if it is missing.

## Setup

```bash
uv sync                 # install dependencies from uv.lock
cp .env.example .env    # optional — defaults work out of the box
```

## Run

```bash
# Development (auto-reload)
uv run uvicorn app.main:app --reload

# Production (bind from .env, no reload)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API is served under `/api`. Quick check:

```bash
curl http://localhost:8000/api/health
# {"status":"ok","ytdlp_version":"2026.x.x","ffmpeg_available":true}
```

## Configuration

All settings are read from environment variables (prefix `PULLVID_`) or a `.env`
file. See [`.env.example`](.env.example) for the full list and defaults:

| Variable | Default | Purpose |
|---|---|---|
| `PULLVID_HOST` | `0.0.0.0` | Bind host |
| `PULLVID_PORT` | `8000` | Bind port |
| `PULLVID_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `PULLVID_DOWNLOAD_DIR` | `./downloads` | Temp download directory |
| `PULLVID_COOKIES_FILE` | _(unset)_ | Path to `cookies.txt` (needed for most Instagram) |
| `PULLVID_MAX_DURATION_SECONDS` | `7200` | Reject videos longer than this |
| `PULLVID_CLEANUP_AFTER_SECONDS` | `3600` | Delete stale temp files older than this on startup |

## API

All endpoints are prefixed `/api`. Errors use the envelope
`{"error": {"code": "...", "message": "..."}}`.

- `GET /api/health` — status, yt-dlp version, ffmpeg availability.
- `POST /api/info` — `{"url": "..."}` → metadata + curated formats (no download).
- `POST /api/download` — `{"url": "...", "format_id": "..."}` → binary file stream
  with `Content-Disposition`. Temp files are deleted after the response is sent.

Supported URLs: YouTube (`watch`, `youtu.be`, `shorts`, `m.youtube.com`) and
Instagram (`/p/`, `/reel/`, `/reels/`, `/tv/`). Playlists are reduced to the
single video where possible; bare playlists/profiles are rejected.

## Tests & linting

```bash
uv run pytest                 # offline tests only (network tests deselected)
uv run pytest -m network      # run live YouTube/Instagram tests (needs network)
uv run ruff check .           # lint
uv run ruff format .          # format
```

## Keeping yt-dlp up to date

Sites break and yt-dlp ships fixes frequently — keep it current. yt-dlp is
intentionally **not** version-pinned to a single release.

```bash
# Upgrade just yt-dlp to the latest release and refresh the lockfile
uv lock --upgrade-package yt-dlp
uv sync
```

A convenience target is also provided:

```bash
make update
```
