"""Pure-function tests for URL validation/normalization. No network."""

from __future__ import annotations

import pytest

from app.exceptions import InvalidURLError, UnsupportedURLError
from app.services.extractor import validate_url


class TestPlatformDetection:
    def test_youtube_watch_url_is_youtube(self):
        result = validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.platform == "youtube"

    def test_youtu_be_short_link_is_youtube(self):
        result = validate_url("https://youtu.be/dQw4w9WgXcQ")
        assert result.platform == "youtube"

    def test_youtube_shorts_is_youtube(self):
        result = validate_url("https://www.youtube.com/shorts/abc123XYZ")
        assert result.platform == "youtube"

    def test_mobile_youtube_is_youtube(self):
        result = validate_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.platform == "youtube"

    def test_instagram_post_is_instagram(self):
        result = validate_url("https://www.instagram.com/p/CabcdEfghij/")
        assert result.platform == "instagram"

    def test_instagram_reel_is_instagram(self):
        result = validate_url("https://www.instagram.com/reel/CabcdEfghij/")
        assert result.platform == "instagram"

    def test_instagram_reels_plural_is_instagram(self):
        result = validate_url("https://www.instagram.com/reels/CabcdEfghij/")
        assert result.platform == "instagram"

    def test_instagram_tv_is_instagram(self):
        result = validate_url("https://www.instagram.com/tv/CabcdEfghij/")
        assert result.platform == "instagram"


class TestRejection:
    def test_garbage_string_raises_invalid_url(self):
        with pytest.raises(InvalidURLError):
            validate_url("not a url at all")

    def test_empty_string_raises_invalid_url(self):
        with pytest.raises(InvalidURLError):
            validate_url("")

    def test_non_http_scheme_raises_invalid_url(self):
        with pytest.raises(InvalidURLError):
            validate_url("ftp://youtube.com/watch?v=abc")

    def test_unsupported_host_raises_unsupported_url(self):
        with pytest.raises(UnsupportedURLError):
            validate_url("https://vimeo.com/12345")

    def test_youtube_channel_page_is_unsupported(self):
        with pytest.raises(UnsupportedURLError):
            validate_url("https://www.youtube.com/@somechannel")

    def test_bare_youtube_playlist_is_unsupported(self):
        with pytest.raises(UnsupportedURLError):
            validate_url("https://www.youtube.com/playlist?list=PL1234567890")

    def test_instagram_profile_is_unsupported(self):
        with pytest.raises(UnsupportedURLError):
            validate_url("https://www.instagram.com/someuser/")


class TestNormalization:
    def test_strips_tracking_params(self):
        result = validate_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=trackingjunk&feature=share"
        )
        assert "si=" not in result.url
        assert "feature=" not in result.url
        assert "v=dQw4w9WgXcQ" in result.url

    def test_strips_list_param_but_keeps_video(self):
        result = validate_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1234567890&index=2"
        )
        assert "list=" not in result.url
        assert "v=dQw4w9WgXcQ" in result.url
        assert result.platform == "youtube"

    def test_youtu_be_normalizes_to_watch_url(self):
        result = validate_url("https://youtu.be/dQw4w9WgXcQ?si=abc")
        assert "dQw4w9WgXcQ" in result.url
        assert "si=" not in result.url

    def test_whitespace_is_trimmed(self):
        result = validate_url("  https://youtu.be/dQw4w9WgXcQ  ")
        assert result.platform == "youtube"
