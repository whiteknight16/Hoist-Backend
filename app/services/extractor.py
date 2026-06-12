"""All yt-dlp logic and URL validation. Routers stay thin and call into here."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

import yt_dlp

from app.config import Settings
from app.exceptions import (
    EmptyPlaylistError,
    InvalidFormatError,
    InvalidURLError,
    UnsupportedURLError,
    VideoTooLongError,
    map_ytdlp_error,
)

Platform = Literal["youtube", "instagram"]

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}
_INSTAGRAM_PREFIXES = ("/p/", "/reel/", "/reels/", "/tv/")


@dataclass(frozen=True)
class ValidatedUrl:
    """A URL that has passed validation and been normalized for yt-dlp."""

    url: str
    platform: Platform
    video_id: str | None = None


@dataclass(frozen=True)
class ValidatedPlaylist:
    """A YouTube playlist URL normalized to its canonical /playlist form."""

    url: str
    playlist_id: str


# ---------------------------------------------------------------------------
# URL validation (pure functions — no network)
# ---------------------------------------------------------------------------


def validate_url(raw: str) -> ValidatedUrl:
    """Validate and normalize a user-supplied URL.

    Raises:
        InvalidURLError: not a parseable http(s) URL.
        UnsupportedURLError: not a supported YouTube/Instagram video URL,
            or a bare playlist/profile/channel.
    """
    if not raw or not raw.strip():
        raise InvalidURLError("No URL provided.")

    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise InvalidURLError("That does not look like a valid URL.")

    host = parsed.netloc.lower().split(":")[0]
    path = parsed.path or "/"

    if host in _YOUTUBE_HOSTS:
        return _validate_youtube(host, path, parsed.query)
    if host == "youtu.be":
        return _validate_youtu_be(path)
    if host in _INSTAGRAM_HOSTS:
        return _validate_instagram(path)

    raise UnsupportedURLError("Only YouTube and Instagram URLs are supported.")


def validate_playlist_url(raw: str) -> ValidatedPlaylist:
    """Validate a URL as a YouTube playlist and normalize it.

    A playlist is any supported YouTube URL (including youtu.be) carrying a
    non-empty `list=` param, regardless of host or path. Returns the canonical
    https://www.youtube.com/playlist?list=<id> form.

    Raises:
        InvalidURLError: not a parseable http(s) URL.
        UnsupportedURLError: not a YouTube host, or no `list=` present.
    """
    if not raw or not raw.strip():
        raise InvalidURLError("No URL provided.")

    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise InvalidURLError("That does not look like a valid URL.")

    host = parsed.netloc.lower().split(":")[0]
    if host not in _YOUTUBE_HOSTS and host != "youtu.be":
        raise UnsupportedURLError("Only YouTube playlists are supported.")

    list_ids = parse_qs(parsed.query).get("list")
    if not list_ids or not list_ids[0]:
        raise UnsupportedURLError("This YouTube URL is not a playlist.")

    playlist_id = list_ids[0]
    return ValidatedPlaylist(
        url=f"https://www.youtube.com/playlist?list={playlist_id}",
        playlist_id=playlist_id,
    )


def _validate_youtube(host: str, path: str, query: str) -> ValidatedUrl:
    params = parse_qs(query)

    if path == "/watch":
        video_ids = params.get("v")
        if not video_ids or not video_ids[0]:
            raise UnsupportedURLError("Missing video id in YouTube URL.")
        vid = video_ids[0]
        # Strip list= and all tracking params; keep only the single video.
        return ValidatedUrl(
            url=f"https://www.youtube.com/watch?v={vid}",
            platform="youtube",
            video_id=vid,
        )

    if path.startswith("/shorts/"):
        vid = path[len("/shorts/") :].split("/")[0]
        if not vid:
            raise UnsupportedURLError("Missing video id in YouTube Shorts URL.")
        return ValidatedUrl(
            url=f"https://www.youtube.com/shorts/{vid}",
            platform="youtube",
            video_id=vid,
        )

    # /playlist, /@channel, /c/, /channel/, /, etc. are not single videos.
    raise UnsupportedURLError("This YouTube URL is not a single video.")


def _validate_youtu_be(path: str) -> ValidatedUrl:
    vid = path.lstrip("/").split("/")[0]
    if not vid:
        raise UnsupportedURLError("Missing video id in youtu.be URL.")
    return ValidatedUrl(
        url=f"https://www.youtube.com/watch?v={vid}",
        platform="youtube",
        video_id=vid,
    )


def _validate_instagram(path: str) -> ValidatedUrl:
    if not path.startswith(_INSTAGRAM_PREFIXES):
        raise UnsupportedURLError("This Instagram URL is not a post, reel, or video.")
    # Normalize: drop query/tracking, keep canonical /<type>/<shortcode>/.
    clean_path = path if path.endswith("/") else path + "/"
    return ValidatedUrl(
        url=f"https://www.instagram.com{clean_path}",
        platform="instagram",
    )


# ---------------------------------------------------------------------------
# Format curation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CuratedFormat:
    """A user-facing format option mapped to a yt-dlp format selector string."""

    format_id: str
    label: str
    kind: Literal["video", "audio"]
    ext: str
    selector: str
    max_height: int | None = None


# Ordered list of candidate curated formats. `format_id` values are the stable
# identifiers shared with the frontend; `selector` is the yt-dlp format string.
_CURATED_VIDEO: list[CuratedFormat] = [
    CuratedFormat(
        format_id="best",
        label="Best available",
        kind="video",
        ext="mp4",
        selector="bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        max_height=None,
    ),
    CuratedFormat(
        format_id="best-1080",
        label="1080p MP4",
        kind="video",
        ext="mp4",
        selector="bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        max_height=1080,
    ),
    CuratedFormat(
        format_id="best-720",
        label="720p MP4",
        kind="video",
        ext="mp4",
        selector="bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]",
        max_height=720,
    ),
    CuratedFormat(
        format_id="best-480",
        label="480p MP4",
        kind="video",
        ext="mp4",
        selector="bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]",
        max_height=480,
    ),
]

_CURATED_AUDIO = CuratedFormat(
    format_id="audio-best",
    label="Audio only (M4A)",
    kind="audio",
    ext="m4a",
    selector="bestaudio[ext=m4a]/bestaudio/best",
    max_height=None,
)

# Lookup of every curated format by its stable id.
CURATED_BY_ID: dict[str, CuratedFormat] = {
    **{f.format_id: f for f in _CURATED_VIDEO},
    _CURATED_AUDIO.format_id: _CURATED_AUDIO,
}


def get_curated_format(format_id: str) -> CuratedFormat:
    """Return the curated format for an id, or raise InvalidFormatError."""
    fmt = CURATED_BY_ID.get(format_id)
    if fmt is None:
        raise InvalidFormatError(f"Unknown format_id: {format_id!r}")
    return fmt


def _max_available_height(info: dict[str, Any]) -> int:
    """Largest video height advertised by yt-dlp for this video (0 if none)."""
    heights = [
        f.get("height") or 0
        for f in info.get("formats", [])
        if f.get("vcodec") not in (None, "none")
    ]
    return max(heights, default=0)


def _approx_filesize(info: dict[str, Any], fmt: CuratedFormat) -> int | None:
    """Best-effort approximate filesize in bytes for a curated format."""
    formats = info.get("formats", [])
    if fmt.kind == "audio":
        sizes = [
            f.get("filesize") or f.get("filesize_approx")
            for f in formats
            if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")
        ]
        sizes = [s for s in sizes if s]
        return max(sizes) if sizes else None

    # For a merged video format, estimate as best video <= height plus best audio.
    video_sizes = [
        f.get("filesize") or f.get("filesize_approx")
        for f in formats
        if f.get("vcodec") not in (None, "none")
        and (fmt.max_height is None or (f.get("height") or 0) <= fmt.max_height)
    ]
    video_sizes = [s for s in video_sizes if s]
    audio_sizes = [
        f.get("filesize") or f.get("filesize_approx")
        for f in formats
        if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")
    ]
    audio_sizes = [s for s in audio_sizes if s]
    if not video_sizes:
        return None
    return max(video_sizes) + (max(audio_sizes) if audio_sizes else 0)


def curate_formats(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the curated, frontend-facing format list from raw yt-dlp info.

    Includes: best available, plus only the 1080/720/480 tiers strictly below
    the source resolution (so no tier duplicates or overshoots "best"), plus one
    best-audio. When yt-dlp reports no height (common for Instagram) we can't
    promise any fixed tier exists, so only "best" + audio are offered.
    """
    max_h = _max_available_height(info)
    width = info.get("width")
    out: list[dict[str, Any]] = []

    for fmt in _CURATED_VIDEO:
        if fmt.max_height is None:
            # "Best available" — always offered; labelled with the source
            # resolution when yt-dlp reported one.
            resolution = (
                (f"{width}x{max_h}" if width else f"{max_h}p") if max_h else None
            )
        else:
            # A fixed tier is a real, distinct option only when the source is
            # taller than it. Skip tiers >= source (they'd just duplicate
            # "best") and skip every fixed tier when the height is unknown.
            if not max_h or fmt.max_height >= max_h:
                continue
            resolution = f"{fmt.max_height}p"
        out.append(
            {
                "format_id": fmt.format_id,
                "label": fmt.label,
                "kind": fmt.kind,
                "ext": fmt.ext,
                "resolution": resolution,
                "filesize_approx_bytes": _approx_filesize(info, fmt),
            }
        )

    out.append(
        {
            "format_id": _CURATED_AUDIO.format_id,
            "label": _CURATED_AUDIO.label,
            "kind": _CURATED_AUDIO.kind,
            "ext": _CURATED_AUDIO.ext,
            "resolution": None,
            "filesize_approx_bytes": _approx_filesize(info, _CURATED_AUDIO),
        }
    )
    return out


# ---------------------------------------------------------------------------
# yt-dlp integration
# ---------------------------------------------------------------------------


def _base_opts(settings: Settings) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": True,
    }
    if settings.cookies_file:
        opts["cookiefile"] = settings.cookies_file
    return opts


def _extract_info_sync(url: str, settings: Settings) -> dict[str, Any]:
    opts = _base_opts(settings)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:  # includes ExtractorError
        raise map_ytdlp_error(str(exc)) from exc
    if info is None:
        raise map_ytdlp_error("yt-dlp returned no information for this URL.")
    # Playlists/multi_video: take the first entry (defensive; noplaylist should prevent).
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]
    return info


def _build_info_response(info: dict[str, Any], validated: ValidatedUrl) -> dict[str, Any]:
    return {
        "id": info.get("id") or validated.video_id or "",
        "title": info.get("title") or "Untitled",
        "platform": validated.platform,
        "thumbnail": info.get("thumbnail"),
        "duration_seconds": int(info["duration"]) if info.get("duration") else None,
        "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        "formats": curate_formats(info),
    }


async def get_info(url: str, settings: Settings) -> dict[str, Any]:
    """Resolve a URL to metadata + curated formats. Does not download."""
    validated = validate_url(url)
    info = await asyncio.to_thread(_extract_info_sync, validated.url, settings)

    duration = info.get("duration")
    if duration and int(duration) > settings.max_duration_seconds:
        raise VideoTooLongError(
            f"Video is {int(duration)}s long; the limit is {settings.max_duration_seconds}s."
        )

    return _build_info_response(info, validated)


@dataclass(frozen=True)
class DownloadResult:
    """A completed download ready to be streamed back to the client."""

    path: Path
    filename: str
    media_type: str


def _guess_media_type(ext: str, kind: str) -> str:
    ext = ext.lower().lstrip(".")
    mapping = {
        "mp4": "video/mp4",
        "webm": "video/webm" if kind == "video" else "audio/webm",
        "mkv": "video/x-matroska",
        "m4a": "audio/mp4",
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
    }
    return mapping.get(ext, "application/octet-stream")


def _download_sync(
    url: str, fmt: CuratedFormat, dest_dir: Path, settings: Settings
) -> DownloadResult:
    opts = _base_opts(settings)
    opts["format"] = fmt.selector
    opts["outtmpl"] = str(dest_dir / "%(title).200B [%(id)s].%(ext)s")
    if fmt.kind == "video":
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise map_ytdlp_error("yt-dlp produced no file.")
            if info.get("_type") == "playlist" and info.get("entries"):
                info = info["entries"][0]
            final_path_str = ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as exc:
        raise map_ytdlp_error(str(exc)) from exc

    final_path = Path(final_path_str)
    # After a merge, the real extension may differ from the pre-merge template.
    if not final_path.exists():
        produced = [p for p in dest_dir.iterdir() if p.is_file()]
        if not produced:
            raise map_ytdlp_error("Download completed but no file was found.")
        final_path = max(produced, key=lambda p: p.stat().st_size)

    return DownloadResult(
        path=final_path,
        filename=final_path.name,
        media_type=_guess_media_type(final_path.suffix, fmt.kind),
    )


async def download(url: str, format_id: str, dest_dir: Path, settings: Settings) -> DownloadResult:
    """Download the chosen curated format into dest_dir and return file info."""
    validated = validate_url(url)
    fmt = get_curated_format(format_id)
    os.makedirs(dest_dir, exist_ok=True)
    return await asyncio.to_thread(_download_sync, validated.url, fmt, dest_dir, settings)


# ---------------------------------------------------------------------------
# Playlist enumeration
# ---------------------------------------------------------------------------

_UNAVAILABLE_TITLES = {"[private video]", "[deleted video]", "[unavailable video]"}
_AVAILABLE_STATES = {None, "public", "unlisted"}


def _entry_unavailable(entry: dict[str, Any]) -> bool:
    title = (entry.get("title") or "").strip().lower()
    if title in _UNAVAILABLE_TITLES:
        return True
    return entry.get("availability") not in _AVAILABLE_STATES


def _build_playlist_response(raw: dict[str, Any], max_entries: int) -> dict[str, Any]:
    """Map a yt-dlp flat-playlist dict into the /api/playlist response shape.

    Skips null/id-less entries and caps the list at `max_entries`. Raises
    EmptyPlaylistError when nothing downloadable remains.
    """
    raw_entries = raw.get("entries") or []
    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        if len(entries) >= max_entries:
            break
        if not entry:
            continue
        vid = entry.get("id")
        if not vid:
            continue
        duration = entry.get("duration")
        entries.append(
            {
                "video_id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": entry.get("title") or "Untitled",
                "uploader": entry.get("uploader") or entry.get("channel"),
                "duration_seconds": int(duration) if duration else None,
                "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "unavailable": _entry_unavailable(entry),
            }
        )

    if not entries:
        raise EmptyPlaylistError("This playlist has no downloadable videos.")

    playlist_count = raw.get("playlist_count")
    # Never report fewer than we actually return — yt-dlp's count can be stale,
    # which would otherwise render a nonsensical "10 of 3 videos".
    total_count = max(int(playlist_count), len(entries)) if playlist_count else len(entries)
    return {
        "id": raw.get("id") or "",
        "title": raw.get("title") or "Playlist",
        "uploader": raw.get("uploader") or raw.get("channel"),
        "total_count": total_count,
        "truncated": total_count > len(entries),
        "entries": entries,
    }


def _extract_playlist_sync(url: str, settings: Settings) -> dict[str, Any]:
    opts = _base_opts(settings)
    opts["noplaylist"] = False
    opts["extract_flat"] = "in_playlist"
    opts["playlistend"] = settings.playlist_max
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:  # includes ExtractorError
        raise map_ytdlp_error(str(exc)) from exc
    if info is None:
        raise map_ytdlp_error("yt-dlp returned no information for this playlist.")
    return info


async def get_playlist(url: str, settings: Settings) -> dict[str, Any]:
    """Resolve a YouTube playlist URL to its (capped) list of entries."""
    validated = validate_playlist_url(url)
    raw = await asyncio.to_thread(_extract_playlist_sync, validated.url, settings)
    return _build_playlist_response(raw, settings.playlist_max)
