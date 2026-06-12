"""FastAPI application factory: CORS, routers, lifespan, exception handlers."""

from __future__ import annotations

import logging
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.exceptions import register_exception_handlers
from app.routers import download, health, info, playlist
from app.routers.health import ffmpeg_available

logger = logging.getLogger("pullvid")


def _cleanup_stale_downloads(settings: Settings) -> None:
    """Delete temp files/dirs older than PULLVID_CLEANUP_AFTER_SECONDS."""
    root = Path(settings.download_dir)
    if not root.exists():
        return
    cutoff = time.time() - settings.cleanup_after_seconds
    for entry in root.iterdir():
        if entry.name == ".gitkeep":
            continue
        try:
            if entry.stat().st_mtime >= cutoff:
                continue
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not clean up %s: %s", entry, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.download_dir).mkdir(parents=True, exist_ok=True)

    if not ffmpeg_available():
        logger.warning(
            "ffmpeg not found on PATH. Video+audio merging will fail; "
            "install ffmpeg for full functionality."
        )
    _cleanup_stale_downloads(settings)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Pullvid", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    register_exception_handlers(app)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request body failed validation.",
                }
            },
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(info.router, prefix="/api")
    app.include_router(download.router, prefix="/api")
    app.include_router(playlist.router, prefix="/api")

    return app


app = create_app()
