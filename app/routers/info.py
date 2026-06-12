"""POST /api/info — resolve a URL into metadata + curated formats."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.schemas import InfoRequest, InfoResponse
from app.services import extractor

router = APIRouter()


@router.post("/info", response_model=InfoResponse)
async def info(
    payload: InfoRequest,
    settings: Settings = Depends(get_settings),
) -> InfoResponse:
    data = await extractor.get_info(payload.url, settings)
    return InfoResponse(**data)
