"""Pydantic request/response models matching the frozen API contract (§5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InfoRequest(BaseModel):
    url: str = Field(..., min_length=1, description="YouTube or Instagram URL")


class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=1, description="YouTube or Instagram URL")
    format_id: str = Field(..., min_length=1, description="Curated format id from /api/info")


class FormatOption(BaseModel):
    format_id: str
    label: str
    kind: Literal["video", "audio"]
    ext: str
    resolution: str | None = None
    filesize_approx_bytes: int | None = None


class InfoResponse(BaseModel):
    id: str
    title: str
    platform: Literal["youtube", "instagram"]
    thumbnail: str | None = None
    duration_seconds: int | None = None
    uploader: str | None = None
    formats: list[FormatOption]


class PlaylistRequest(BaseModel):
    url: str = Field(..., min_length=1, description="YouTube playlist URL")


class PlaylistEntry(BaseModel):
    video_id: str
    url: str
    title: str
    uploader: str | None = None
    duration_seconds: int | None = None
    thumbnail: str | None = None
    unavailable: bool = False


class PlaylistResponse(BaseModel):
    id: str
    title: str
    uploader: str | None = None
    total_count: int
    truncated: bool
    entries: list[PlaylistEntry]


class HealthResponse(BaseModel):
    status: str
    ytdlp_version: str
    ffmpeg_available: bool


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
