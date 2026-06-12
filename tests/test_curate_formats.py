"""Unit tests for curated-format selection (no network).

Guards the rule that we only advertise resolution tiers the source actually
supports: tiers >= the source height duplicate/overshoot "best", and when
yt-dlp reports no height we can't promise any fixed tier exists.
"""

from __future__ import annotations

from app.services.extractor import curate_formats


def _info(*heights: int, width: int | None = None) -> dict:
    """A minimal yt-dlp info dict with one video format per given height."""
    return {
        "width": width,
        "formats": [
            {"height": h, "vcodec": "avc1", "acodec": "none"} for h in heights
        ]
        + [{"height": None, "vcodec": "none", "acodec": "mp4a"}],  # audio track
    }


def _ids(info: dict) -> list[str]:
    return [f["format_id"] for f in curate_formats(info)]


def test_1080p_source_offers_lower_tiers_but_no_duplicate_of_best():
    # Source tops out at 1080 → "best" covers 1080; only 720/480 are distinct.
    assert _ids(_info(1080, 720, 480)) == ["best", "best-720", "best-480", "audio-best"]


def test_480p_source_hides_higher_tiers():
    assert _ids(_info(480)) == ["best", "audio-best"]


def test_720p_source_offers_only_480_below_it():
    assert _ids(_info(720, 480)) == ["best", "best-480", "audio-best"]


def test_unknown_height_offers_only_best_and_audio():
    # Common for Instagram: no per-format height reported. We can't promise a
    # 1080/720/480 tier exists, so don't advertise them.
    info = {
        "width": None,
        "formats": [
            {"height": None, "vcodec": "avc1", "acodec": "mp4a"},
            {"height": None, "vcodec": "none", "acodec": "mp4a"},
        ],
    }
    assert _ids(info) == ["best", "audio-best"]


def test_best_carries_source_resolution_when_known():
    formats = curate_formats(_info(1080, width=1920))
    best = next(f for f in formats if f["format_id"] == "best")
    assert best["resolution"] == "1920x1080"
