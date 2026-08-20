"""Centralized application exception taxonomy and HTTP error mapping.

Routes must not raise ``HTTPException(500, str(exc))`` scattered around.
Handlers raise a typed ``ApplicationError`` subclass; a single global
handler maps it to a stable sanitized ``{"error": {"code", "message"}}``
response. Unexpected exceptions are logged by the backend and surface to
the browser only as a stable ``INTERNAL_ERROR`` — never a traceback,
exception repr, or subprocess stderr.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Base class for all web-job application errors.

    ``code`` is a stable machine-readable string; ``message`` is a
    sanitized human string safe to expose over HTTP.
    """

    status_code = 500
    code = "INTERNAL_ERROR"
    message = "Internal error."

    def __init__(self, *, message: str | None = None):
        self.message = message if message is not None else self.message
        super().__init__(self.message)


class InvalidJobRequestError(ApplicationError):
    status_code = 400
    code = "INVALID_JOB_REQUEST"
    message = "Invalid job request."


class InvalidJobIdError(ApplicationError):
    status_code = 400
    code = "INVALID_JOB_ID"
    message = "Invalid job id."


class JobNotFoundError(ApplicationError):
    status_code = 404
    code = "JOB_NOT_FOUND"
    message = "Job not found."


class JobVideoUnavailableError(ApplicationError):
    status_code = 404
    code = "JOB_VIDEO_UNAVAILABLE"
    message = "Job video is not available."


class JobExecutionBusyError(ApplicationError):
    status_code = 409
    code = "JOB_EXECUTION_BUSY"
    message = "Job executor is busy."


class JobExecutionError(ApplicationError):
    status_code = 500
    code = "JOB_EXECUTION_ERROR"
    message = "Job execution error."


class InternalStorageError(ApplicationError):
    status_code = 500
    code = "INTERNAL_STORAGE_ERROR"
    message = "Internal storage error."


def error_payload(exc: ApplicationError) -> dict[str, Any]:
    """Stable sanitized error body."""
    return {"error": {"code": exc.code, "message": exc.message}}


def to_http_error(exc: ApplicationError) -> tuple[int, dict[str, Any]]:
    """Return (status_code, sanitized_body) for an application error."""
    return exc.status_code, error_payload(exc)


def to_http_internal_error(log_context: str = "") -> tuple[int, dict[str, Any]]:
    """Return a stable INTERNAL_ERROR body for unexpected exceptions."""
    if log_context:
        logger.error("unexpected web-api error (%s)", log_context, exc_info=True)
    return (
        500,
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal error.",
            }
        },
    )