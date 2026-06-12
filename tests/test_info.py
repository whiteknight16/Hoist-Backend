"""Tests for /api/health and /api/info.

Network-dependent happy-path tests are marked @pytest.mark.network and are
deselected by default (see pyproject [tool.pytest.ini_options]).
"""

from __future__ import annotations

import pytest


class TestHealth:
    async def test_health_returns_ok_envelope(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "ytdlp_version" in body
        assert isinstance(body["ffmpeg_available"], bool)


class TestInfoValidation:
    """These exercise validation, which happens before any network call."""

    async def test_garbage_url_returns_invalid_url_envelope(self, client):
        resp = await client.post("/api/info", json={"url": "not a url"})
        assert resp.status_code == 400
        assert resp.json() == {
            "error": {"code": "INVALID_URL", "message": resp.json()["error"]["message"]}
        }
        assert resp.json()["error"]["code"] == "INVALID_URL"

    async def test_unsupported_host_returns_unsupported_url(self, client):
        resp = await client.post("/api/info", json={"url": "https://vimeo.com/123"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "UNSUPPORTED_URL"

    async def test_bare_playlist_returns_unsupported_url(self, client):
        resp = await client.post(
            "/api/info",
            json={"url": "https://www.youtube.com/playlist?list=PL123"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "UNSUPPORTED_URL"

    async def test_missing_url_field_returns_envelope(self, client):
        resp = await client.post("/api/info", json={})
        assert resp.status_code == 422
        assert "error" in resp.json()
        assert resp.json()["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.network
class TestInfoLive:
    async def test_public_youtube_url_returns_curated_formats(self, client):
        resp = await client.post(
            "/api/info",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["platform"] == "youtube"
        assert body["id"]
        assert body["title"]
        format_ids = {f["format_id"] for f in body["formats"]}
        assert "audio-best" in format_ids
        assert "best" in format_ids
        # Every curated format carries the contract fields.
        for f in body["formats"]:
            assert set(f) == {
                "format_id",
                "label",
                "kind",
                "ext",
                "resolution",
                "filesize_approx_bytes",
            }
