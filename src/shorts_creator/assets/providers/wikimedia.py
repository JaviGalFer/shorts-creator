"""Wikimedia Commons provider client v2.

Generic, neutral provider for searching and downloading images from
Wikimedia Commons.  No imports from v1 pipeline modules.  Stdlib only.
HTTP requests require an explicit User-Agent.

Exposed API:
- ``resolve_wikimedia_candidate_v2``  — search + select first acceptable candidate
- ``download_wikimedia_asset_v2``     — download a candidate to disk
- ``WikimediaRateLimitedError``       — raised when 429 retries exhausted
"""

from __future__ import annotations

import json
import math
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from shorts_creator.assets.renderability import (
    MIN_V2_ASSET_WIDTH,
    MIN_V2_ASSET_HEIGHT,
    SUPPORTED_WIKIMEDIA_MIME_TYPES,
)

# ── Constants ────────────────────────────────────────────────────────────────

_WIKI_API_BASE = "https://commons.wikimedia.org/w/api.php"
_DEFAULT_USER_AGENT = (
    "shorts-creator/0.1 (generic visual asset resolver; contact: configured)"
)

_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Max titles per batched imageinfo request (Wikimedia API limit)
_MAX_TITLES_PER_II_REQUEST = 50
# Cap on Retry-After wait to avoid unbounded stalls
_MAX_RETRY_AFTER_SEC = 10.0


# ── Custom exception for rate-limited diagnosis ──────────────────────────────


class WikimediaRateLimitedError(Exception):
    """Raised when 429 retries are exhausted for a Wikimedia API request."""
    pass


# ── Internal HTTP helpers ────────────────────────────────────────────────────


def _build_headers(user_agent: str | None) -> dict[str, str]:
    ua = (user_agent or "").strip() or _DEFAULT_USER_AGENT
    return {"User-Agent": ua}


def _http_get_json(
    url: str,
    user_agent: str | None = None,
    timeout: int = 30,
    retry_on_429: bool = True,
    retry_sleep_sec: float = 1.0,
) -> dict | None:
    """HTTP GET with JSON parsing.  Returns None on non-429 errors.
    Raises ``WikimediaRateLimitedError`` when 429 retries are exhausted.
    """
    headers = _build_headers(user_agent)
    max_attempts = 2 if retry_on_429 else 1
    for attempt in range(max_attempts):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 429 and retry_on_429 and attempt == 0:
                retry_after = _parse_retry_after(e.headers)
                wait = min(retry_after, _MAX_RETRY_AFTER_SEC)
                time.sleep(wait)
                continue
            if e.code == 429:
                raise WikimediaRateLimitedError(
                    "Wikimedia API returned 429 Too Many Requests "
                    "(retries exhausted)"
                )
            return None
        except (urllib.error.URLError, socket.timeout,
                json.JSONDecodeError, OSError, ValueError):
            return None
    return None


def _parse_retry_after(headers) -> float:
    """Extract Retry-After header value in seconds, clamped to a cap."""
    try:
        raw = headers.get("Retry-After")
        if raw is None:
            return 1.0
        return min(float(raw.strip()), _MAX_RETRY_AFTER_SEC)
    except Exception:
        return 1.0


def _http_download(
    url: str,
    output_path: Path,
    user_agent: str | None = None,
    timeout: int = 30,
) -> tuple[bool, str | None, int]:
    headers = _build_headers(user_agent)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content_type = (r.headers.get("Content-Type") or "").lower()
            if output_path.exists():
                return False, content_type, 0
            output_path.parent.mkdir(parents=True, exist_ok=True)
            data = r.read()
            output_path.write_bytes(data)
            return True, content_type, len(data)
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout,
            OSError, ValueError):
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        return False, None, 0


# ── Query text extraction ────────────────────────────────────────────────────


def _extract_query_text(query: Any) -> str:
    if isinstance(query, str):
        return query.strip()[:200]
    if isinstance(query, dict):
        text = query.get("text", "")
        if isinstance(text, str):
            return text.strip()[:200]
    return ""


# ── Wikimedia search (batched imageinfo) ──────────────────────────────────────


def _search_wikimedia_batched(
    query: str,
    max_results: int,
    user_agent: str,
    timeout: int,
) -> list[dict[str, Any]]:
    """Search Wikimedia and batch-resolve imageinfo for all results.

    Uses two HTTP calls: one search + one batched imageinfo.
    SVG titles and invalid entries are filtered out.

    Returns:
        Ordered list of candidate dicts.  Empty list if no valid results.
    """
    sq = urllib.parse.quote(query[:200])
    search_url = (
        f"{_WIKI_API_BASE}"
        f"?action=query&list=search&srsearch={sq}+-filetype:svg&srnamespace=6"
        f"&srlimit={max_results}&format=json&origin=*"
    )

    data = _http_get_json(search_url, user_agent, timeout)
    if data is None:
        return []

    pages = data.get("query", {}).get("search", [])
    titles: list[str] = []
    for p in pages:
        title = p.get("title", "").replace(" ", "_")
        if not title or title.lower().endswith(".svg"):
            continue
        titles.append(title)

    if not titles:
        return []

    return _batch_imageinfo(titles, user_agent, timeout, query)


def _batch_imageinfo(
    titles: list[str],
    user_agent: str,
    timeout: int,
    query_used: str = "",
) -> list[dict[str, Any]]:
    """Query imageinfo for a batch of titles in a single API call.

    Handles pagination when titles > _MAX_TITLES_PER_II_REQUEST.
    """
    results: list[dict[str, Any]] = []

    for offset in range(0, len(titles), _MAX_TITLES_PER_II_REQUEST):
        batch = titles[offset:offset + _MAX_TITLES_PER_II_REQUEST]
        encoded = urllib.parse.quote("|".join(batch))
        info_url = (
            f"{_WIKI_API_BASE}"
            f"?action=query&titles={encoded}"
            f"&prop=imageinfo&iiprop=url|extmetadata|size|mime"
            f"&format=json&origin=*"
        )

        info_data = _http_get_json(info_url, user_agent, timeout)
        if info_data is None:
            continue

        pages_dict = info_data.get("query", {}).get("pages", {})
        for pid, pdict in pages_dict.items():
            if pid == "-1":
                continue
            imageinfo_list = pdict.get("imageinfo", [{}])
            for info in imageinfo_list:
                mime = (info.get("mime") or "").lower()
                file_url = info.get("url", "")

                if mime not in SUPPORTED_WIKIMEDIA_MIME_TYPES:
                    continue
                if not file_url:
                    continue

                extmeta = info.get("extmetadata", {})
                license_name = _extract_license(extmeta)
                author = _extract_author(extmeta)

                title_meta = _extract_title(extmeta, pdict)

                page_title = pdict.get("title", "")
                source_url = ""
                if page_title:
                    source_url = (
                        "https://commons.wikimedia.org/wiki/"
                        + urllib.parse.quote(page_title, safe="/:")
                    )

                results.append({
                    "provider": "wikimedia_commons",
                    "title": title_meta,
                    "sourceUrl": source_url,
                    "fileUrl": file_url,
                    "thumbnailUrl": info.get("thumburl", ""),
                    "license": license_name,
                    "author": author,
                    "width": info.get("width", 0) or 0,
                    "height": info.get("height", 0) or 0,
                    "mimeType": mime,
                    "queryUsed": query_used,
                    "score": 0.0,
                })

    return results


def _extract_license(extmeta: dict) -> str:
    for key in ("LicenseShortName", "License"):
        val = extmeta.get(key, {})
        if isinstance(val, dict):
            v = val.get("value", "")
            if isinstance(v, str) and v.strip():
                return v.strip()
    return "unknown"


def _extract_author(extmeta: dict) -> str:
    val = extmeta.get("Artist", {})
    if isinstance(val, dict):
        v = val.get("value", "")
        if isinstance(v, str):
            clean = v.replace("<br />", ", ").replace("<br>", ", ")
            clean = clean.replace("&lt;", "<").replace("&gt;", ">")
            stripped = clean.strip()[:200]
            if stripped:
                return stripped
    return "Unknown"


def _extract_title(extmeta: dict, page: dict) -> str:
    val = extmeta.get("ImageDescription", {})
    if isinstance(val, dict):
        v = val.get("value", "")
        if isinstance(v, str) and v.strip():
            return v.strip()[:500]
    return page.get("title", "")


def _candidate_passes_filters(
    c: dict,
    min_width: int,
    min_height: int,
    excluded_source_urls: set[str] | None,
    excluded_file_urls: set[str] | None,
) -> bool:
    width = c.get("width", 0) or 0
    height = c.get("height", 0) or 0
    mime = (c.get("mimeType") or "").lower()
    file_url = c.get("fileUrl", "")

    if mime not in SUPPORTED_WIKIMEDIA_MIME_TYPES:
        return False
    if not file_url:
        return False
    if width < min_width or height < min_height:
        return False
    if excluded_source_urls and c.get("sourceUrl", "") in excluded_source_urls:
        return False
    if excluded_file_urls and file_url in excluded_file_urls:
        return False
    return True


# ── Public API ───────────────────────────────────────────────────────────────


def resolve_wikimedia_candidate_v2(
    queries: list,
    max_results: int = 5,
    min_width: int = MIN_V2_ASSET_WIDTH,
    min_height: int = MIN_V2_ASSET_HEIGHT,
    user_agent: str | None = None,
    timeout: int = 30,
    excluded_source_urls: set[str] | None = None,
    excluded_file_urls: set[str] | None = None,
    cache: dict[str, list] | None = None,
) -> dict | None:
    """Search Wikimedia Commons using each query in order.

    Returns the first candidate that meets minimum criteria and is not
    present in either exclusion set, or ``None``.

    On 429 rate limit exhaustion, raises ``WikimediaRateLimitedError``
    so callers can propagate ``PROVIDER_ERROR / RATE_LIMITED`` instead
    of ``NO_RESULTS``.

    Args:
        queries: List of query strings or dicts with ``text`` key.
        max_results: Max search results per query.
        min_width: Minimum acceptable image width.
        min_height: Minimum acceptable image height.
        user_agent: Optional User-Agent header override.
        timeout: HTTP timeout per request in seconds.
        excluded_source_urls: Optional set of already-used source URLs.
        excluded_file_urls: Optional set of already-used file URLs.
        cache: Optional mutable dict for query → candidate list cache.
            Populated by this function and reused across calls.

    Returns:
        Candidate dict or ``None`` if no candidate passes all filters.

    Raises:
        WikimediaRateLimitedError: When 429 retries are exhausted.
    """
    ua = (user_agent or "").strip() or _DEFAULT_USER_AGENT
    _use_cache = cache is not None

    for query_raw in queries:
        query_text = _extract_query_text(query_raw)
        if not query_text:
            continue

        # ── Cache hit: reuse previously fetched candidates ─────────────────
        if _use_cache and query_text in cache:
            candidates = list(cache[query_text])
        else:
            candidates = _search_wikimedia_batched(
                query_text, max_results, ua, timeout,
            )
            if _use_cache and candidates is not None:
                cache[query_text] = list(candidates)

        if not candidates:
            continue

        for c in candidates:
            if _candidate_passes_filters(
                c, min_width, min_height,
                excluded_source_urls, excluded_file_urls,
            ):
                return c

        time.sleep(1.0)

    return None


def download_wikimedia_asset_v2(
    candidate: dict,
    output_path: Path,
    user_agent: str | None = None,
    timeout: int = 30,
    min_size_bytes: int = 1000,
) -> dict:
    """Download a candidate file to *output_path*.

    Args:
        candidate: Candidate dict from ``resolve_wikimedia_candidate_v2``.
        output_path: Destination file path.
        user_agent: Optional User-Agent header override.
        timeout: HTTP timeout in seconds.
        min_size_bytes: Minimum file size to accept.

    Returns:
        ``{"ok", "path", "size", "mimeType", "error"}``
    """
    file_url = candidate.get("fileUrl", "")
    if not file_url:
        return {
            "ok": False,
            "path": str(output_path),
            "size": 0,
            "mimeType": None,
            "error": "no fileUrl in candidate",
        }

    if output_path.exists():
        return {
            "ok": False,
            "path": str(output_path),
            "size": 0,
            "mimeType": None,
            "error": f"file already exists: {output_path}",
        }

    success, content_type, size = _http_download(
        file_url, output_path, user_agent, timeout,
    )

    if not success:
        return {
            "ok": False,
            "path": str(output_path),
            "size": 0,
            "mimeType": content_type,
            "error": "download failed",
        }

    ct = (content_type or "").lower()
    if ct not in SUPPORTED_WIKIMEDIA_MIME_TYPES:
        output_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "path": str(output_path),
            "size": 0,
            "mimeType": ct,
            "error": f"invalid Content-Type: {content_type}",
        }

    if size < min_size_bytes:
        output_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "path": str(output_path),
            "size": size,
            "mimeType": ct,
            "error": f"file too small: {size} bytes < {min_size_bytes}",
        }

    return {
        "ok": True,
        "path": str(output_path),
        "size": size,
        "mimeType": ct,
        "error": None,
    }
