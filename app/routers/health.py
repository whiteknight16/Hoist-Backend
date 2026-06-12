"""GET /api/health — liveness + dependency availability."""

from __future__ import annotations

import shutil

from fastapi import APIRouter

from app.models.schemas import HealthResponse

router = APIRouter()


def ffmpeg_available() -> bool:
    """True if the ffmpeg binary is on PATH (needed for video+audio merge)."""
    return shutil.which("ffmpeg") is not None


def ytdlp_version() -> str:
    import yt_dlp.version

    return yt_dlp.version.__version__


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        ytdlp_version=ytdlp_version(),
        ffmpeg_available=ffmpeg_available(),
    )
