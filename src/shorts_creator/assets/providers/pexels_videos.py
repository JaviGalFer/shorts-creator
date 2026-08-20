"""Pexels Video page-1 mapping and safe MP4 acquisition helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import os
import re
import urllib.error
import urllib.request
from typing import Any, Mapping

from shorts_creator.assets.candidates import CandidateAttribution, CandidateEnvelope, CandidateSemanticMetadata, RAW
from shorts_creator.assets.providers.pexels import MALFORMED_RESPONSE, PEXELS_USER_AGENT, PexelsClientError, get_json, resolve_pexels_api_key
from shorts_creator.contracts.visual_media import VIDEO

PEXELS_VIDEOS_SEARCH_PATH = "/v1/videos/search"
PEXELS_VIDEOS_PARAMS: Mapping[str, str | int] = {
    "orientation": "portrait", "locale": "en-US", "page": 1, "per_page": 15,
}
NO_RESULTS = "NO_RESULTS"
PROVIDER_METADATA_INSUFFICIENT = "PROVIDER_METADATA_INSUFFICIENT"
PROVIDER_METADATA_PARTIAL_MATCH = "PROVIDER_METADATA_PARTIAL_MATCH"
_SLUG_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class PexelsVideoCandidate:
    envelope: CandidateEnvelope
    pexels_video_id: str
    pexels_video_file_id: str
    pexels_query_rank: int
    source_duration_sec: float
    fps: float | None
    videographer_id: str | None = None


@dataclass(frozen=True)
class PexelsVideoSearchResult:
    status: str
    candidates: tuple[PexelsVideoCandidate, ...]
    telemetry: Mapping[str, str]


def _positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _positive_number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def descriptive_video_slug(source_url: str | None) -> str | None:
    """Extract non-tautological descriptive words from a Pexels video URL."""
    if not source_url:
        return None
    parts = [part for part in source_url.rstrip("/").split("/") if part]
    if not parts:
        return None
    slug = parts[-1]
    if slug.isdigit() and len(parts) > 1:
        slug = parts[-2]
    tokens = [token for token in _SLUG_TOKEN_RE.findall(slug.lower()) if token != "video" and not token.isdigit()]
    return " ".join(tokens) or None


def _eligible_file(video_files: Any) -> tuple[int, Mapping[str, Any]] | None:
    if not isinstance(video_files, list):
        return None
    eligible: list[tuple[int, Mapping[str, Any], int, int, int]] = []
    for raw_order, video_file in enumerate(video_files):
        if not isinstance(video_file, Mapping):
            continue
        width, height = _positive_int(video_file.get("width")), _positive_int(video_file.get("height"))
        link = _text(video_file.get("link"))
        file_type = (_text(video_file.get("file_type")) or "").lower()
        quality = (_text(video_file.get("quality")) or "").lower()
        if not link or file_type != "video/mp4" or quality == "hls" or link.lower().split("?", 1)[0].endswith(".m3u8"):
            continue
        if width is None or height is None or height <= width:
            continue
        tier = 1 if width >= 1080 and height >= 1920 else 2 if width >= 720 and height >= 1280 else 0
        if tier:
            eligible.append((tier, video_file, width * height, raw_order, _positive_int(video_file.get("id")) or 0))
    if not eligible:
        return None
    tier = min(item[0] for item in eligible)
    _, selected, _, _, _ = min((item for item in eligible if item[0] == tier), key=lambda item: (item[2], item[3], item[4]))
    return video_files.index(selected), selected


def _map_video(video: Mapping[str, Any], query_used: str, raw_rank: int) -> PexelsVideoCandidate | None:
    video_id = _positive_int(video.get("id"))
    source_url = _text(video.get("url"))
    duration = _positive_number(video.get("duration"))
    selected = _eligible_file(video.get("video_files"))
    if video_id is None or source_url is None or duration is None or selected is None:
        return None
    _, video_file = selected
    file_id = _positive_int(video_file.get("id"))
    width, height = _positive_int(video_file.get("width")), _positive_int(video_file.get("height"))
    acquisition_url = _text(video_file.get("link"))
    if file_id is None or width is None or height is None or acquisition_url is None:
        return None
    user = video.get("user") if isinstance(video.get("user"), Mapping) else {}
    tags = tuple(tag.strip() for tag in video.get("tags", []) if isinstance(tag, str) and tag.strip()) if isinstance(video.get("tags"), list) else ()
    preview = _text(video.get("image"))
    if preview is None and isinstance(video.get("video_pictures"), list):
        for picture in video["video_pictures"]:
            if isinstance(picture, Mapping) and _text(picture.get("picture")):
                preview = _text(picture.get("picture"))
                break
    fps = _positive_number(video_file.get("fps"))
    envelope = CandidateEnvelope(
        capability_id="pexels.video.stock", provider="pexels", provider_asset_id=str(video_id),
        media_kind=VIDEO, source_type="STOCK", query_used=query_used, query_variant=RAW,
        query_index=0, provider_rank=None, provider_score=None,
        semantic_metadata=CandidateSemanticMetadata(title=descriptive_video_slug(source_url), tags=tags),
        source_url=source_url, preview_url=preview, acquisition_url=acquisition_url,
        mime_type="video/mp4", width=width, height=height,
        attribution=CandidateAttribution(author=_text(user.get("name")), author_url=_text(user.get("url"))),
    )
    return PexelsVideoCandidate(
        envelope=envelope, pexels_video_id=str(video_id), pexels_video_file_id=str(file_id),
        pexels_query_rank=raw_rank, source_duration_sec=duration, fps=fps,
        videographer_id=str(_positive_int(user.get("id"))) if _positive_int(user.get("id")) else None,
    )


def bind_lifecycle_positions(candidates: tuple[PexelsVideoCandidate, ...], *, query_index: int, provider_rank_start: int) -> tuple[PexelsVideoCandidate, ...]:
    return tuple(replace(item, envelope=replace(item.envelope, query_index=query_index, provider_rank=provider_rank_start + offset)) for offset, item in enumerate(candidates, start=1))


def map_video_response(response: Mapping[str, Any], query_used: str) -> PexelsVideoSearchResult:
    videos = response.get("videos")
    if not isinstance(videos, list):
        raise PexelsClientError(MALFORMED_RESPONSE, "Pexels Videos response has invalid videos")
    if not videos:
        return PexelsVideoSearchResult(NO_RESULTS, (), {})
    candidates = tuple(candidate for rank, video in enumerate(videos[:15], start=1) if isinstance(video, Mapping) for candidate in [_map_video(video, query_used, rank)] if candidate is not None)
    if not candidates:
        raise PexelsClientError(MALFORMED_RESPONSE, "Pexels Videos response has no valid portrait MP4 videos")
    return PexelsVideoSearchResult("OK", candidates, {})


def search_pexels_videos(query_used: str, *, api_key: str | None = None, timeout: int = 30) -> PexelsVideoSearchResult:
    response = get_json(path=PEXELS_VIDEOS_SEARCH_PATH, params={"query": query_used, **PEXELS_VIDEOS_PARAMS}, api_key=api_key if api_key is not None else resolve_pexels_api_key(), timeout=timeout)
    mapped = map_video_response(response.data, query_used)
    return PexelsVideoSearchResult(mapped.status, mapped.candidates, response.telemetry)


def download_pexels_video(candidate: CandidateEnvelope, destination: Path, *, timeout: int = 60) -> dict[str, Any]:
    """Download one known MP4 candidate without image decoding or secret output."""
    if candidate.media_kind != VIDEO or candidate.mime_type != "video/mp4" or not candidate.acquisition_url:
        return {"ok": False, "error": "INVALID_VIDEO_CANDIDATE"}
    if destination.suffix.lower() != ".mp4":
        return {"ok": False, "error": "INVALID_VIDEO_DESTINATION"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".mp4.part")
    try:
        request = urllib.request.Request(
            candidate.acquisition_url,
            headers={"User-Agent": PEXELS_USER_AGENT},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            if content_type != "video/mp4":
                return {"ok": False, "error": "VIDEO_MIME_MISMATCH", "mimeType": content_type}
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        size = temporary.stat().st_size
        if size <= 0:
            return {"ok": False, "error": "VIDEO_EMPTY_BODY"}
        os.replace(temporary, destination)
        return {"ok": True, "size": size, "mimeType": "video/mp4"}
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {"ok": False, "error": "VIDEO_ACCESS_DENIED", "status": exc.code}
        return {"ok": False, "error": "VIDEO_DOWNLOAD_FAILED", "status": exc.code}
    except (urllib.error.URLError, OSError, TimeoutError):
        return {"ok": False, "error": "VIDEO_DOWNLOAD_FAILED"}
    finally:
        temporary.unlink(missing_ok=True)
