"""POST /api/download — download chosen format and stream the file back."""

from __future__ import annotations

import shutil
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.config import Settings, get_settings
from app.models.schemas import DownloadRequest
from app.services import extractor

router = APIRouter()


def _ascii_fallback(name: str) -> str:
    """ASCII-safe filename for the legacy Content-Disposition `filename` field."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    # Strip characters that would break the quoted-string syntax.
    ascii_name = ascii_name.replace('"', "").replace("\\", "").replace("\n", "").replace("\r", "")
    return ascii_name.strip() or "download"


def _content_disposition(filename: str) -> str:
    """Build `attachment` header with both ASCII fallback and UTF-8 variant (§5.3)."""
    ascii_name = _ascii_fallback(filename)
    utf8_name = quote(filename)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"


@router.post("/download")
async def download(
    payload: DownloadRequest,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    request_dir = Path(settings.download_dir) / uuid.uuid4().hex
    result = await extractor.download(payload.url, payload.format_id, request_dir, settings)

    # Delete the whole per-request subdir once the response has been sent.
    cleanup = BackgroundTask(shutil.rmtree, request_dir, ignore_errors=True)

    return FileResponse(
        path=result.path,
        media_type=result.media_type,
        headers={"Content-Disposition": _content_disposition(result.filename)},
        background=cleanup,
    )
