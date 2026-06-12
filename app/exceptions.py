"""Error taxonomy, exception handlers, and yt-dlp error mapping."""

from __future__ import annotations

import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class PullvidError(Exception):
    """Base application error rendered through the standard error envelope.

    Maps directly to the API contract in §5.4 of the spec.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class InvalidURLError(PullvidError):
    status_code = 400
    code = "INVALID_URL"


class UnsupportedURLError(PullvidError):
    status_code = 400
    code = "UNSUPPORTED_URL"


class VideoTooLongError(PullvidError):
    status_code = 400
    code = "VIDEO_TOO_LONG"


class VideoNotFoundError(PullvidError):
    status_code = 404
    code = "VIDEO_NOT_FOUND"


class LoginRequiredError(PullvidError):
    status_code = 403
    code = "LOGIN_REQUIRED"


class InvalidFormatError(PullvidError):
    status_code = 422
    code = "INVALID_FORMAT"


class RateLimitedError(PullvidError):
    status_code = 429
    code = "RATE_LIMITED"


class ExtractionFailedError(PullvidError):
    status_code = 502
    code = "EXTRACTION_FAILED"


class EmptyPlaylistError(PullvidError):
    status_code = 404
    code = "EMPTY_PLAYLIST"


def _envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


# Ordered (pattern, exception factory) pairs. First match wins.
# Patterns match against the lowercased yt-dlp error string.
_YTDLP_ERROR_PATTERNS: list[tuple[re.Pattern[str], type[PullvidError]]] = [
    (re.compile(r"private video|this video is private"), VideoNotFoundError),
    (
        re.compile(
            r"video unavailable|has been removed|no longer available|does not exist|not found|removed by the user|account.*terminated"
        ),
        VideoNotFoundError,
    ),
    (
        re.compile(
            r"sign in to confirm|login required|requested content is not available|use --cookies|cookies"
        ),
        LoginRequiredError,
    ),
    (re.compile(r"rate.?limit|429|too many requests|throttl"), RateLimitedError),
]


def map_ytdlp_error(message: str) -> PullvidError:
    """Translate a yt-dlp DownloadError/ExtractorError message into a PullvidError.

    Falls back to EXTRACTION_FAILED (502) and includes the original yt-dlp message,
    per §5.4.
    """
    lowered = message.lower()
    for pattern, exc_type in _YTDLP_ERROR_PATTERNS:
        if pattern.search(lowered):
            return exc_type(message)
    return ExtractionFailedError(message)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that render every error through the standard envelope."""

    @app.exception_handler(PullvidError)
    async def _pullvid_error_handler(_: Request, exc: PullvidError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message),
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
        )
