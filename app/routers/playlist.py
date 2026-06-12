"""POST /api/playlist — enumerate a YouTube playlist into selectable entries."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.schemas import PlaylistRequest, PlaylistResponse
from app.services import extractor

router = APIRouter()


@router.post("/playlist", response_model=PlaylistResponse)
async def playlist(
    payload: PlaylistRequest,
    settings: Settings = Depends(get_settings),
) -> PlaylistResponse:
    data = await extractor.get_playlist(payload.url, settings)
    return PlaylistResponse(**data)
