"""Pixabay provider client v2.

Generic provider for searching and downloading images from Pixabay.
No imports from v1 pipeline modules.  Stdlib only.

Exposed API:
- ``resolve_pixabay_candidates_v2``  — search Pixabay API
- ``download_pixabay_asset_v2``       — download a candidate to disk
"""

from __future__ import annotations

import hashlib
import json
import os
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
    is_v2_asset_dimension_renderable,
    SUPPORTED_WIKIMEDIA_MIME_TYPES,
)

# ── Constants ────────────────────────────────────────────────────────────────

_PIXABAY_API_BASE = "https://pixabay.com/api/"

_PIXABAY_IMAGE_TYPE_MAX_DIM = 1280

_ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
})

_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_ASSET_PREF_TO_IMAGE_TYPES: dict[str, list[str]] = {
    "photograph": ["photo"],
    "stock": ["photo"],
    "illustration": ["illustration", "vector"],
    "diagram": ["illustration", "vector"],
}

_UNSUPPORTED_ASSET_PREFS: frozenset[str] = frozenset({
    "archive", "document", "map", "painting", "generated",
})

_DIAGRAM_WARNING = (
    "Pixabay illustration/vector fallback may not represent "
    "a precise technical diagram"
)

# Max pages to fetch per query (20 results each)
_MAX_PAGES = 5


# ── Internal helpers ─────────────────────────────────────────────────────────


def _extract_query_text(query: Any) -> str:
    if isinstance(query, str):
        return query.strip()[:200]
    if isinstance(query, dict):
        text = query.get("text", "")
        if isinstance(text, str):
            return text.strip()[:200]
    return ""


def _build_cache_key(
    query: str,
    language: str,
    image_type: str,
    min_width: int,
    min_height: int,
    page: int,
    per_page: int,
) -> str:
    raw = (
        f"q={query}|lang={language}|type={image_type}"
        f"|mw={min_width}|mh={min_height}|p={page}|pp={per_page}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_cache(cache_path: Path, ttl_sec: int) -> list[dict] | None:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        ts = data.get("_cachedAt", 0)
        if time.time() - ts > ttl_sec:
            return None
        return data.get("results") or []
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _write_cache(cache_path: Path, results: list[dict]) -> None:
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_cachedAt": time.time(),
            "results": results,
        }
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(str(tmp), str(cache_path))
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _calculate_expected_dimensions(
    orig_w: int, orig_h: int, max_dim: int = _PIXABAY_IMAGE_TYPE_MAX_DIM
) -> tuple[int, int]:
    if orig_w <= 0 or orig_h <= 0:
        return 0, 0
    if orig_w <= max_dim and orig_h <= max_dim:
        return orig_w, orig_h
    ratio = orig_w / orig_h
    if orig_w >= orig_h:
        w = max_dim
        h = int(round(w / ratio))
    else:
        h = max_dim
        w = int(round(h * ratio))
    return w, h


# ── HTTP helpers ─────────────────────────────────────────────────────────────


def _http_get_json(
    url: str,
    timeout: int = 30,
) -> tuple[dict | None, int | None]:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
            return json.loads(body), r.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except (urllib.error.URLError, socket.timeout,
            json.JSONDecodeError, OSError, ValueError):
        return None, None


def _http_download(
    url: str,
    output_path: Path,
    timeout: int = 30,
) -> tuple[bool, str | None, int]:
    headers = {
        "User-Agent": "shorts-creator/0.1 (Pixabay visual asset downloader)",
        "Accept": "image/jpeg,image/png,image/webp,image/gif,*/*",
    }
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


# ── Public API ───────────────────────────────────────────────────────────────


def resolve_pixabay_candidates_v2(
    queries: list,
    *,
    api_key: str,
    asset_preference: str,
    min_width: int = MIN_V2_ASSET_WIDTH,
    min_height: int = MIN_V2_ASSET_HEIGHT,
    language: str = "en",
    max_results: int = 20,
    cache_dir: Path | None = None,
    cache_ttl_sec: int = 86400,
    excluded_source_urls: set[str] | None = None,
    excluded_file_urls: set[str] | None = None,
    timeout: int = 30,
) -> list[dict]:
    """Search Pixabay for candidates matching the given queries.

    Returns an ordered list of candidate dicts.  Empty list if no
    valid results or if the API key is empty/invalid.

    Raises:
        ValueError: if ``api_key`` is empty or ``asset_preference``
            is unsupported for Pixabay.
    """
    if not api_key or not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("Pixabay API key is required and must be non-empty")

    if asset_preference in _UNSUPPORTED_ASSET_PREFS:
        raise ValueError(
            f"Pixabay does not support assetPreference '{asset_preference}'"
        )

    image_types = _ASSET_PREF_TO_IMAGE_TYPES.get(asset_preference)
    if not image_types:
        return []

    all_candidates: list[dict] = []
    seen_page_urls: set[str] = set()

    for query_raw in queries:
        query_text = _extract_query_text(query_raw)
        if not query_text:
            continue

        for image_type in image_types:
            for page in range(1, _MAX_PAGES + 1):
                per_page = min(max_results, 200)

                candidates, status_code = _search_pixabay_page(
                    query_text,
                    api_key,
                    image_type,
                    language,
                    min_width,
                    min_height,
                    page,
                    per_page,
                    cache_dir,
                    cache_ttl_sec,
                    timeout,
                )

                if status_code is not None and status_code != 200:
                    break

                if not candidates:
                    break

                for hit_index, c in enumerate(candidates, start=1):
                    source_url = c.get("pageURL", "")
                    file_url = c.get("largeImageURL", "")

                    if not file_url:
                        continue
                    if source_url in seen_page_urls:
                        continue
                    if excluded_source_urls and source_url in excluded_source_urls:
                        continue
                    if excluded_file_urls and file_url in excluded_file_urls:
                        continue

                    orig_w = c.get("imageWidth", 0) or 0
                    orig_h = c.get("imageHeight", 0) or 0
                    exp_w, exp_h = _calculate_expected_dimensions(orig_w, orig_h)

                    if not is_v2_asset_dimension_renderable(exp_w, exp_h):
                        continue

                    seen_page_urls.add(source_url)

                    all_candidates.append({
                        "provider": "pixabay",
                        "pixabayId": c.get("id"),
                        "sourceUrl": source_url,
                        "fileUrl": file_url,
                        "previewURL": c.get("previewURL", ""),
                        "author": c.get("user", "Unknown"),
                        "license": "Pixabay Content License",
                        "width": exp_w,
                        "height": exp_h,
                        "originalWidth": orig_w,
                        "originalHeight": orig_h,
                        "mimeType": "",
                        "mimeTypeKnown": False,
                        "queryUsed": query_text,
                        "tags": c.get("tags", ""),
                        "imageType": c.get("type", ""),
                        "likes": c.get("likes", 0),
                        "downloads": c.get("downloads", 0),
                        # Preserve the API hit position without using it to rank.
                        "providerRank": (page - 1) * per_page + hit_index,
                    })

                if len(all_candidates) >= max_results:
                    break

            if len(all_candidates) >= max_results:
                break

        if all_candidates:
            break

    return all_candidates


def _search_pixabay_page(
    query: str,
    api_key: str,
    image_type: str,
    language: str,
    min_width: int,
    min_height: int,
    page: int,
    per_page: int,
    cache_dir: Path | None,
    cache_ttl_sec: int,
    timeout: int,
) -> tuple[list[dict], int | None]:
    cache_key = _build_cache_key(
        query, language, image_type, min_width, min_height, page, per_page,
    )

    if cache_dir is not None:
        cache_path = cache_dir / f"{cache_key}.json"
        cached = _read_cache(cache_path, cache_ttl_sec)
        if cached is not None:
            return cached, 200

    params = {
        "key": api_key,
        "q": query,
        "image_type": image_type,
        "lang": language,
        "min_width": str(min_width),
        "min_height": str(min_height),
        "safesearch": "true",
        "page": str(page),
        "per_page": str(per_page),
    }
    qs = urllib.parse.urlencode(params)
    url = f"{_PIXABAY_API_BASE}?{qs}"

    data, status_code = _http_get_json(url, timeout)

    if status_code is None:
        return [], None

    if status_code != 200:
        return [], status_code

    if data is None:
        return [], status_code

    hits = data.get("hits") or []
    if not isinstance(hits, list):
        hits = []

    if cache_dir is not None:
        cache_path = cache_dir / f"{cache_key}.json"
        _write_cache(cache_path, hits)

    return hits, status_code


def download_pixabay_asset_v2(
    candidate: dict,
    output_path: Path,
    *,
    timeout: int = 30,
    min_size_bytes: int = 1000,
) -> dict:
    """Download a Pixabay candidate to *output_path*.

    Validates Content-Type, size, and expected dimensions after download.

    Returns:
        ``{"ok", "path", "size", "mimeType", "actualWidth", "actualHeight", "error"}``
    """
    file_url = candidate.get("fileUrl", "")
    if not file_url:
        return {
            "ok": False,
            "path": str(output_path),
            "size": 0,
            "mimeType": None,
            "actualWidth": 0,
            "actualHeight": 0,
            "error": "no fileUrl in candidate",
        }

    if output_path.exists():
        return {
            "ok": False,
            "path": str(output_path),
            "size": 0,
            "mimeType": None,
            "actualWidth": 0,
            "actualHeight": 0,
            "error": f"file already exists: {output_path}",
        }

    success, content_type, size = _http_download(
        file_url, output_path, timeout,
    )

    if not success:
        return {
            "ok": False,
            "path": str(output_path),
            "size": 0,
            "mimeType": content_type,
            "actualWidth": 0,
            "actualHeight": 0,
            "error": "download failed",
        }

    ct = (content_type or "").lower()
    if ct not in _ALLOWED_MIME_TYPES:
        output_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "path": str(output_path),
            "size": size,
            "mimeType": ct,
            "actualWidth": 0,
            "actualHeight": 0,
            "error": f"invalid Content-Type: {content_type}",
        }

    mime_main = ct.split(";")[0].strip()

    if size < min_size_bytes:
        output_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "path": str(output_path),
            "size": size,
            "mimeType": mime_main,
            "actualWidth": 0,
            "actualHeight": 0,
            "error": f"file too small: {size} bytes < {min_size_bytes}",
        }

    expected_w = candidate.get("width", 0) or 0
    expected_h = candidate.get("height", 0) or 0

    if not is_v2_asset_dimension_renderable(expected_w, expected_h):
        output_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "path": str(output_path),
            "size": size,
            "mimeType": mime_main,
            "actualWidth": expected_w,
            "actualHeight": expected_h,
            "error": (
                f"expected dimensions {expected_w}x{expected_h} "
                f"do not meet minimum {MIN_V2_ASSET_WIDTH}x{MIN_V2_ASSET_HEIGHT}"
            ),
        }

    actual_w, actual_h = _read_image_dimensions(output_path, mime_main)
    if actual_w > 0 and actual_h > 0:
        if not is_v2_asset_dimension_renderable(actual_w, actual_h):
            output_path.unlink(missing_ok=True)
            return {
                "ok": False,
                "path": str(output_path),
                "size": size,
                "mimeType": mime_main,
                "actualWidth": actual_w,
                "actualHeight": actual_h,
                "error": (
                    f"actual dimensions {actual_w}x{actual_h} "
                    f"do not meet minimum {MIN_V2_ASSET_WIDTH}x{MIN_V2_ASSET_HEIGHT}"
                ),
            }
        final_w, final_h = actual_w, actual_h
    else:
        final_w, final_h = expected_w, expected_h

    return {
        "ok": True,
        "path": str(output_path),
        "size": size,
        "mimeType": mime_main,
        "actualWidth": final_w,
        "actualHeight": final_h,
        "error": None,
    }


def _read_image_dimensions(file_path: Path, mime_type: str) -> tuple[int, int]:
    """Read actual image dimensions from file headers (stdlib only).

    Supports JPEG, PNG, GIF, and WebP.  Returns (0, 0) on error.
    """
    try:
        data = file_path.read_bytes()
        if mime_type == "image/jpeg":
            return _read_jpeg_dimensions(data)
        elif mime_type == "image/png":
            return _read_png_dimensions(data)
        elif mime_type == "image/gif":
            return _read_gif_dimensions(data)
        elif mime_type == "image/webp":
            return _read_webp_dimensions(data)
    except Exception:
        pass
    return 0, 0


def _read_jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Read JPEG dimensions from file header."""
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return 0, 0
    i = 2
    while i < len(data) - 1:
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker == 0xD8 or marker == 0xD9:
            i += 2
            continue
        if marker in (0xC0, 0xC1, 0xC2):
            if i + 9 <= len(data):
                h = int.from_bytes(data[i + 5:i + 7], "big")
                w = int.from_bytes(data[i + 7:i + 9], "big")
                return w, h
            break
        if i + 4 > len(data):
            break
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        i += 2 + seg_len
    return 0, 0


def _read_png_dimensions(data: bytes) -> tuple[int, int]:
    """Read PNG dimensions from file header."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    w = int.from_bytes(data[16:20], "big")
    h = int.from_bytes(data[20:24], "big")
    return w, h


def _read_gif_dimensions(data: bytes) -> tuple[int, int]:
    """Read GIF dimensions from file header."""
    if len(data) < 10 or data[:6] not in (b"GIF89a", b"GIF87a"):
        return 0, 0
    w = int.from_bytes(data[6:8], "little")
    h = int.from_bytes(data[8:10], "little")
    return w, h


def _read_webp_dimensions(data: bytes) -> tuple[int, int]:
    """Read WebP dimensions from file header (VP8X or VP8L or VP8)."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return 0, 0
    chunk = data[12:16]
    if chunk == b"VP8 ":
        if len(data) >= 30:
            w = int.from_bytes(data[26:28], "little") & 0x3FFF
            h = int.from_bytes(data[28:30], "little") & 0x3FFF
            return w, h
    elif chunk == b"VP8L":
        if len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            w = (bits & 0x3FFF) + 1
            h = ((bits >> 14) & 0x3FFF) + 1
            return w, h
    elif chunk == b"VP8X":
        if len(data) >= 30:
            w = (int.from_bytes(data[24:27], "little") + 1) & 0xFFFFFF
            h = (int.from_bytes(data[27:30], "little") + 1) & 0xFFFFFF
            return w, h
    return 0, 0
