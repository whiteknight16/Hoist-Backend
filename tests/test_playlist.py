"""Tests for playlist response mapping and the /api/playlist endpoint."""

from __future__ import annotations

import pytest

from app.exceptions import EmptyPlaylistError
from app.services.extractor import _build_playlist_response


def _raw(entries, **kw):
    base = {
        "id": "PLabc",
        "title": "My Playlist",
        "uploader": "Some Channel",
        "playlist_count": kw.get("playlist_count", len(entries)),
        "entries": entries,
    }
    base.update({k: v for k, v in kw.items() if k != "playlist_count"})
    return base


class TestBuildPlaylistResponse:
    def test_maps_basic_entries(self):
        raw = _raw(
            [
                {"id": "aaa", "title": "First", "duration": 100, "uploader": "Chan"},
                {"id": "bbb", "title": "Second", "duration": 200},
            ]
        )
        out = _build_playlist_response(raw, max_entries=50)
        assert out["id"] == "PLabc"
        assert out["title"] == "My Playlist"
        assert out["uploader"] == "Some Channel"
        assert out["total_count"] == 2
        assert out["truncated"] is False
        assert len(out["entries"]) == 2
        first = out["entries"][0]
        assert first["video_id"] == "aaa"
        assert first["url"] == "https://www.youtube.com/watch?v=aaa"
        assert first["title"] == "First"
        assert first["duration_seconds"] == 100
        assert first["thumbnail"] == "https://i.ytimg.com/vi/aaa/hqdefault.jpg"
        assert first["unavailable"] is False

    def test_truncates_to_max_entries(self):
        entries = [{"id": f"v{i}", "title": str(i)} for i in range(10)]
        raw = _raw(entries, playlist_count=312)
        out = _build_playlist_response(raw, max_entries=5)
        assert len(out["entries"]) == 5
        assert out["total_count"] == 312
        assert out["truncated"] is True

    def test_skips_none_and_idless_entries(self):
        raw = _raw([None, {"title": "no id"}, {"id": "ok", "title": "Keep"}])
        out = _build_playlist_response(raw, max_entries=50)
        assert [e["video_id"] for e in out["entries"]] == ["ok"]

    def test_flags_unavailable_entries(self):
        raw = _raw(
            [
                {"id": "p", "title": "[Private video]"},
                {"id": "d", "title": "[Deleted video]"},
                {"id": "ok", "title": "Fine", "availability": "public"},
            ]
        )
        out = _build_playlist_response(raw, max_entries=50)
        flags = {e["video_id"]: e["unavailable"] for e in out["entries"]}
        assert flags == {"p": True, "d": True, "ok": False}

    def test_missing_duration_is_none(self):
        raw = _raw([{"id": "x", "title": "X"}])
        out = _build_playlist_response(raw, max_entries=50)
        assert out["entries"][0]["duration_seconds"] is None

    def test_empty_playlist_raises(self):
        with pytest.raises(EmptyPlaylistError):
            _build_playlist_response(_raw([]), max_entries=50)

    def test_all_unmappable_raises(self):
        with pytest.raises(EmptyPlaylistError):
            _build_playlist_response(_raw([None, {"title": "no id"}]), max_entries=50)


class TestPlaylistEndpointValidation:
    """Validation happens before any network call."""

    async def test_garbage_url_returns_invalid_url(self, client):
        resp = await client.post("/api/playlist", json={"url": "not a url"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_URL"

    async def test_instagram_returns_unsupported(self, client):
        resp = await client.post(
            "/api/playlist", json={"url": "https://www.instagram.com/p/Cabc/"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "UNSUPPORTED_URL"

    async def test_watch_without_list_returns_unsupported(self, client):
        resp = await client.post(
            "/api/playlist",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "UNSUPPORTED_URL"

    async def test_missing_url_field_returns_envelope(self, client):
        resp = await client.post("/api/playlist", json={})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_REQUEST"
