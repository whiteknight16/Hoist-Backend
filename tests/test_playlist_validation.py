"""Pure-function tests for playlist URL validation. No network."""

from __future__ import annotations

import pytest

from app.exceptions import InvalidURLError, UnsupportedURLError
from app.services.extractor import validate_playlist_url


class TestPlaylistAccept:
    def test_bare_playlist_url(self):
        result = validate_playlist_url(
            "https://www.youtube.com/playlist?list=PL1234567890"
        )
        assert result.playlist_id == "PL1234567890"
        assert result.url == "https://www.youtube.com/playlist?list=PL1234567890"

    def test_watch_url_with_list(self):
        result = validate_playlist_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc&index=2"
        )
        assert result.playlist_id == "PLabc"
        assert result.url == "https://www.youtube.com/playlist?list=PLabc"

    def test_mobile_host_with_list(self):
        result = validate_playlist_url(
            "https://m.youtube.com/watch?v=abc&list=PLxyz"
        )
        assert result.playlist_id == "PLxyz"

    def test_youtu_be_with_list(self):
        result = validate_playlist_url("https://youtu.be/dQw4w9WgXcQ?list=PLshare")
        assert result.playlist_id == "PLshare"
        assert result.url == "https://www.youtube.com/playlist?list=PLshare"


class TestPlaylistReject:
    def test_watch_url_without_list_is_unsupported(self):
        with pytest.raises(UnsupportedURLError):
            validate_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_youtu_be_without_list_is_unsupported(self):
        with pytest.raises(UnsupportedURLError):
            validate_playlist_url("https://youtu.be/dQw4w9WgXcQ")

    def test_instagram_is_unsupported(self):
        with pytest.raises(UnsupportedURLError):
            validate_playlist_url("https://www.instagram.com/p/Cabc/")

    def test_empty_list_param_is_unsupported(self):
        with pytest.raises(UnsupportedURLError):
            validate_playlist_url("https://www.youtube.com/playlist?list=")

    def test_empty_string_raises_invalid_url(self):
        with pytest.raises(InvalidURLError):
            validate_playlist_url("")

    def test_non_http_scheme_raises_invalid_url(self):
        with pytest.raises(InvalidURLError):
            validate_playlist_url("ftp://www.youtube.com/playlist?list=PL123")
