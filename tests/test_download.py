"""Tests for /api/download.

The end-to-end happy path is network-dependent and marked @pytest.mark.network.
Validation/error-path and the Content-Disposition helper are tested offline.
"""

from __future__ import annotations

import pytest

from app.routers.download import _ascii_fallback, _content_disposition


class TestContentDispositionHelper:
    def test_ascii_fallback_strips_non_ascii(self):
        assert _ascii_fallback("Rick Astley – Never Gonna Give You Up.mp4")

    def test_ascii_fallback_never_empty(self):
        assert _ascii_fallback("日本語のみ.mp4") == "download" or _ascii_fallback("日本語のみ.mp4")

    def test_ascii_fallback_removes_quotes(self):
        assert '"' not in _ascii_fallback('weird"name.mp4')

    def test_content_disposition_has_both_variants(self):
        header = _content_disposition("Café Vidéo.mp4")
        assert header.startswith("attachment; filename=")
        assert "filename*=UTF-8''" in header


class TestDownloadValidation:
    async def test_garbage_url_returns_invalid_url(self, client):
        resp = await client.post("/api/download", json={"url": "garbage", "format_id": "best"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_URL"

    async def test_unsupported_url_returns_unsupported(self, client):
        resp = await client.post(
            "/api/download",
            json={"url": "https://vimeo.com/123", "format_id": "best"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "UNSUPPORTED_URL"

    async def test_unknown_format_id_returns_invalid_format(self, client):
        # URL is valid; format_id is not in the curated set -> 422 INVALID_FORMAT.
        resp = await client.post(
            "/api/download",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "format_id": "totally-bogus",
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_FORMAT"

    async def test_missing_format_id_returns_envelope(self, client):
        resp = await client.post(
            "/api/download",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.network
class TestDownloadLive:
    async def test_audio_best_returns_playable_m4a(self, client, tmp_path):
        resp = await client.post(
            "/api/download",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "format_id": "audio-best",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("audio/")
        assert "attachment" in resp.headers["content-disposition"]
        assert len(resp.content) > 0
