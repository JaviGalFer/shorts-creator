"""Small shared Pexels GET client for provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

from shorts_creator.assets.provider_credentials import resolve_api_key

PEXELS_API_BASE = "https://api.pexels.com"
DEFAULT_TIMEOUT_SECONDS = 30

CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
AUTH_ERROR = "AUTH_ERROR"
RATE_LIMITED = "RATE_LIMITED"
NETWORK_ERROR = "NETWORK_ERROR"
MALFORMED_RESPONSE = "MALFORMED_RESPONSE"

_RATE_LIMIT_HEADERS = frozenset({
    "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "retry-after",
})


class PexelsClientError(Exception):
    """A secret-safe, small error exposed to provider adapters."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PexelsJsonResponse:
    data: Mapping[str, Any]
    telemetry: Mapping[str, str]


def resolve_pexels_api_key() -> str | None:
    """Resolve ``PEXELS_API_KEY`` with the project visual-provider convention."""
    return resolve_api_key("PEXELS_API_KEY")


def _sanitize_rate_limit_headers(headers: Any) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    if headers is None:
        return sanitized
    items = headers.items() if hasattr(headers, "items") else ()
    for key, value in items:
        normalized = str(key).lower()
        if normalized in _RATE_LIMIT_HEADERS and value is not None:
            sanitized[normalized] = str(value)
    return sanitized


def _request_url(path: str, params: Mapping[str, str | int]) -> str:
    if not isinstance(path, str) or not path.startswith("/") or "://" in path:
        raise ValueError("INVALID_PEXELS_PATH")
    return f"{PEXELS_API_BASE}{path}?{urllib.parse.urlencode(params)}"


def get_json(
    *,
    path: str,
    params: Mapping[str, str | int],
    api_key: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> PexelsJsonResponse:
    """Perform one authenticated JSON GET without retries or secret output."""
    key = api_key.strip() if isinstance(api_key, str) else ""
    if not key:
        raise PexelsClientError(CREDENTIAL_MISSING, "PEXELS_API_KEY is not configured")
    request = urllib.request.Request(
        _request_url(path, params), headers={"Authorization": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            try:
                data = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise PexelsClientError(MALFORMED_RESPONSE, "Pexels returned invalid JSON") from exc
            if not isinstance(data, dict):
                raise PexelsClientError(MALFORMED_RESPONSE, "Pexels JSON response must be an object")
            return PexelsJsonResponse(data=data, telemetry=_sanitize_rate_limit_headers(response.headers))
    except PexelsClientError:
        raise
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            code, message = AUTH_ERROR, "Pexels authentication failed"
        elif exc.code == 429:
            code, message = RATE_LIMITED, "Pexels rate limit reached"
        else:
            code, message = NETWORK_ERROR, f"Pexels request failed with HTTP status {exc.code}"
        raise PexelsClientError(code, message) from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        raise PexelsClientError(NETWORK_ERROR, "Pexels network request failed") from exc
