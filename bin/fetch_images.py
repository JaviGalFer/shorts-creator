#!/usr/bin/env python3

import argparse
import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Scoring weights (centralized)
# ---------------------------------------------------------------------------
SCORING_WEIGHTS: dict[str, int] = {
    "entity_match": 30,
    "period_or_location_match": 20,
    "asset_type_match": 15,
    "sufficient_resolution": 15,
    "clear_license": 10,
    "preferred_source": 10,
    "modern_or_irrelevant": -30,
    "duplicate_entity": -30,
    "unknown_license": -40,
    "low_resolution": -50,
    "duplicate_url": -50,
    "same_author_provider": -40,
    "same_query": -30,
    "same_asset_type": -20,
}

MIN_WIDTH = 400
MIN_HEIGHT = 400
USER_AGENT = "ShortsHistoricos/1.0 (historical video pipeline; +https://github.com/javi/shorts-historicos)"

# ---------------------------------------------------------------------------
# Strategy -> provider chain (ordered by priority)
# ---------------------------------------------------------------------------
STRATEGY_CHAINS: dict[str, list[str]] = {
    "historical_archive": ["wikimedia_commons", "pexels", "freeai", "pollinations"],
    "map_or_document": ["wikimedia_commons", "pexels", "freeai", "pollinations"],
    "atmospheric_broll": ["pexels", "pixabay", "freeai", "pollinations"],
    "generated_reconstruction": ["freeai", "pollinations"],
}

# ---------------------------------------------------------------------------
# EditorialRole -> provider chain (overrides strategy chain for hard historical roles)
# Hard historical roles: only archives, NO Pexels/Pollinations fallback.
# Soft roles: use strategy chain (may include stock photo providers).
# ---------------------------------------------------------------------------
HARD_HISTORICAL_ROLES: set[str] = {
    "context_map", "character_portrait", "battle_or_assault",
    "military_technology", "civilian_impact", "document_or_date",
}
ROLE_PROVIDER_CHAINS: dict[str, list[str]] = {
    role: ["wikimedia_commons"] for role in HARD_HISTORICAL_ROLES
}
# Soft roles use the strategy-based chain (no override)
SOFT_ROLES: set[str] = {
    "atmospheric_transition", "legacy", "consequence_or_legacy",
    "abstract", "unknown",
}

# ---------------------------------------------------------------------------
# Query adaptation per provider
# Maps strategy -> list of visual/generic query templates for stock photo APIs
# ---------------------------------------------------------------------------
STRATEGY_VISUAL_QUERIES: dict[str, list[str]] = {
    "historical_archive": [
        "old historical photograph",
        "vintage documentary photo",
        "archival historical image",
        "retro black and white scene",
        "historical event photography",
        "19th century engraving",
        "old military portrait",
        "vintage war photograph",
        "historical battle scene painting",
        "ancient manuscript illustration",
        "old newspaper front page",
        "historical map archive",
        "vintage propaganda poster",
        "antique portrait painting",
        "old city panoramic view",
    ],
    "map_or_document": [
        "old map historical",
        "ancient manuscript document",
        "vintage cartography",
        "historical letter document",
        "old parchment map",
        "medieval illuminated manuscript",
        "antique world map",
        "18th century navigation chart",
        "old treaty document",
        "renaissance map engraving",
        "ancient papyrus scroll",
        "medieval castle blueprint",
        "old military campaign map",
    ],
    "atmospheric_broll": [
        "old ruins dramatic sky",
        "candlelight dark room",
        "ancient stone texture",
        "smoke fog atmosphere",
        "medieval castle storm",
        "ancient military camp",
        "old fortress walls",
        "historical siege scene",
        "battlefield mist morning",
        "medieval armor weapon display",
        "ancient city gate medieval",
        "old harbor medieval town",
        "cathedral interior dark",
        "ancient cobblestone street",
        "old cannon fortress defense",
    ],
    "generated_reconstruction": [
        "historical reconstruction",
        "ancient city landscape",
        "medieval fortress concept",
        "historical scene illustration",
    ],
}

CANDIDATES_PER_PROVIDER = 5

EDITORIAL_ROLE_PREFERENCES: dict[str, dict[str, set[str]]] = {
    "context_map": {
        "preferred": {"map", "document", "historical_map"},
        "forbidden": {"atmospheric_broll", "generated_reconstruction", "broll"},
    },
    "character_portrait": {
        "preferred": {"portrait", "historical_photograph", "painting"},
        "forbidden": {"atmospheric_broll", "broll"},
    },
    "military_technology": {
        "preferred": {"historical_photograph", "painting", "document"},
        "forbidden": {"generated_reconstruction", "atmospheric_broll"},
    },
    "civilian_impact": {
        "preferred": {"historical_photograph", "document"},
        "forbidden": {"atmospheric_broll", "generated_reconstruction"},
    },
    "battle_or_assault": {
        "preferred": {"painting", "historical_photograph"},
        "forbidden": {"atmospheric_broll", "broll"},
    },
    "document_or_date": {
        "preferred": {"document", "map"},
        "forbidden": {"generated_reconstruction", "atmospheric_broll"},
    },
    "consequence_or_legacy": {
        "preferred": {"historical_photograph", "painting"},
        "forbidden": {"atmospheric_broll", "broll"},
    },
    "atmospheric_transition": {
        "preferred": {"atmospheric_broll", "broll"},
        "forbidden": {"generated_reconstruction"},
    },
}

SCENE_PAUSE_SEC = 0.5

# ---------------------------------------------------------------------------
# Rate limiter for Wikimedia Commons
# ---------------------------------------------------------------------------
class WikimediaRateLimiter:
    def __init__(self, max_per_window: int = 5, window_sec: float = 12.0):
        self.max_per_window = max_per_window
        self.window_sec = window_sec
        self.timestamps: list[float] = []

    def wait_if_needed(self):
        now = time.monotonic()
        cutoff = now - self.window_sec
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) >= self.max_per_window:
            sleep = self.timestamps[0] + self.window_sec - now
            if sleep > 0:
                time.sleep(sleep)
        self.timestamps.append(time.monotonic())

    def wait_between(self):
        time.sleep(0.6)

wikimedia_limiter = WikimediaRateLimiter()

# ---------------------------------------------------------------------------
# Wikimedia Commons cache (prevents re-requesting same query)
# ---------------------------------------------------------------------------
_wikimedia_cache: dict[str, list[dict[str, Any]]] = {}

def _http_request(url: str, timeout: int = 30, headers: dict | None = None) -> tuple[int, str | None]:
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------
VALID_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp", "image/gif")

def download(url: str, path: Path, timeout: int = 60) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content_type = r.headers.get("Content-Type", "").lower()
            if content_type and not any(content_type.startswith(p) for p in VALID_MIME_PREFIXES):
                return False
            path.write_bytes(r.read())
        if not path.stat().st_size > 1000:
            path.unlink()
            return False
        return True
    except Exception:
        if path.exists():
            path.unlink()
        return False


# ---------------------------------------------------------------------------
# Wikimedia Commons
# ---------------------------------------------------------------------------
def search_wikimedia(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    cache_key = f"wikimedia:{query}:{max_results}"
    if cache_key in _wikimedia_cache:
        return _wikimedia_cache[cache_key]

    results: list[dict[str, Any]] = []
    sq = urllib.parse.quote(query[:200])
    search_url = (
        f"https://commons.wikimedia.org/w/api.php"
        f"?action=query&list=search&srsearch={sq}+-filetype:svg&srnamespace=6"
        f"&srlimit={max_results}&format=json&origin=*"
    )

    wikimedia_limiter.wait_if_needed()
    status, body = _http_request(search_url)
    if status != 200 or body is None:
        _wikimedia_cache[cache_key] = results
        return results
    if status == 429:
        time.sleep(5)
        status, body = _http_request(search_url)
        if status != 200 or body is None:
            _wikimedia_cache[cache_key] = results
            return results

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        _wikimedia_cache[cache_key] = results
        return results

    pages = data.get("query", {}).get("search", [])
    for p in pages:
        title = p["title"].replace(" ", "_")
        if title.lower().endswith(".svg"):
            continue
        info_url = (
            f"https://commons.wikimedia.org/w/api.php"
            f"?action=query&titles={urllib.parse.quote(title)}"
            f"&prop=imageinfo&iiprop=url|extmetadata|size|mime&format=json&origin=*"
        )
        wikimedia_limiter.wait_between()
        wikimedia_limiter.wait_if_needed()
        info_status, info_body = _http_request(info_url)
        if info_status != 200 or info_body is None:
            continue

        try:
            idata = json.loads(info_body)
        except json.JSONDecodeError:
            continue

        for pid, pdata in idata.get("query", {}).get("pages", {}).items():
            if pid == "-1":
                continue
            info = pdata.get("imageinfo", [{}])[0]
            mime = (info.get("mime") or "").lower()
            if mime and not mime.startswith("image/"):
                continue
            meta = info.get("extmetadata", {})
            license_name = None
            if "LicenseShortName" in meta:
                license_name = meta["LicenseShortName"].get("value")
            elif "License" in meta:
                license_name = meta["License"].get("value")
            author = None
            if "Artist" in meta:
                author = meta["Artist"].get("value", "")
                author = author.replace("<br />", ", ").replace("<br>", ", ")
                author = author.replace("&lt;", "<").replace("&gt;", ">")
                author = author[:200] if author else None
            title_meta = None
            if "ImageDescription" in meta:
                title_meta = meta["ImageDescription"].get("value", "")
                title_meta = title_meta[:200] if title_meta else None
            results.append({
                "provider": "wikimedia_commons",
                "sourceUrl": info.get("url", ""),
                "thumbnailUrl": info.get("thumburl", ""),
                "title": title_meta or p.get("title", ""),
                "author": author or "Unknown",
                "license": license_name or "unknown",
                "width": info.get("width", 0),
                "height": info.get("height", 0),
                "queryUsed": query,
            })

    _wikimedia_cache[cache_key] = results
    return results


# ---------------------------------------------------------------------------
# Pexels
# ---------------------------------------------------------------------------
PEXELS_URL = "https://api.pexels.com/v1/search"

def search_pexels(query: str, api_key: str, max_results: int = 5) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    sq = urllib.parse.quote(query[:200])
    url = f"{PEXELS_URL}?query={sq}&per_page={max_results}&orientation=portrait"
    try:
        req = urllib.request.Request(url, headers={"Authorization": api_key, "User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        for photo in data.get("photos", []):
            src = photo.get("src", {})
            results.append({
                "provider": "pexels",
                "sourceUrl": src.get("original", ""),
                "thumbnailUrl": src.get("medium", ""),
                "title": photo.get("alt", "") or "",
                "author": photo.get("photographer", "Unknown"),
                "license": "Pexels License",
                "width": photo.get("width", 0),
                "height": photo.get("height", 0),
                "queryUsed": query,
            })
    except Exception:
        pass
    return results


# ---------------------------------------------------------------------------
# Pixabay
# ---------------------------------------------------------------------------
PIXABAY_URL = "https://pixabay.com/api/"

def search_pixabay(query: str, api_key: str, max_results: int = 5) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    sq = urllib.parse.quote(query[:200])
    url = f"{PIXABAY_URL}?key={api_key}&q={sq}&per_page={max_results}&orientation=vertical"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        for hit in data.get("hits", []):
            results.append({
                "provider": "pixabay",
                "sourceUrl": hit.get("largeImageURL", ""),
                "thumbnailUrl": hit.get("webformatURL", ""),
                "title": hit.get("tags", "") or "",
                "author": hit.get("user", "Unknown"),
                "license": "Pixabay License",
                "width": hit.get("imageWidth", 0),
                "height": hit.get("imageHeight", 0),
                "queryUsed": query,
            })
    except Exception:
        pass
    return results


# ---------------------------------------------------------------------------
# FreeAI (generated images)
# ---------------------------------------------------------------------------
FREEAI_URL = "https://api.free.ai/v1/image/generate/"

def generate_freeai(prompt: str, negative_prompt: str, api_key: str, scene_num: int) -> list[dict[str, Any]]:
    body = {
        "prompt": prompt[:500],
        "model": "flux-schnell",
        "aspect_ratio": "9:16",
    }
    if negative_prompt:
        body["negative_prompt"] = negative_prompt[:200]
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        FREEAI_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        image_url = result.get("image_url")
        if image_url:
            return [{
                "provider": "freeai",
                "sourceUrl": image_url,
                "thumbnailUrl": image_url,
                "title": f"AI generated: {prompt[:80]}",
                "author": "AI (FLUX Schnell)",
                "license": "Generated (no copyright)",
                "width": 576,
                "height": 1024,
                "queryUsed": prompt[:200],
            }]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Pollinations (last resort fallback)
# ---------------------------------------------------------------------------
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

def generate_pollinations(prompt: str, scene_num: int) -> list[dict[str, Any]]:
    safe = urllib.parse.quote(prompt[:200])
    url = f"{POLLINATIONS_URL}{safe}?width=576&height=1024&seed={scene_num}&nofeed=true"
    return [{
        "provider": "pollinations",
        "sourceUrl": url,
        "thumbnailUrl": url,
        "title": f"AI generated: {prompt[:80]}",
        "author": "AI (Pollinations)",
        "license": "Generated (no copyright)",
        "width": 576,
        "height": 1024,
        "queryUsed": prompt[:200],
    }]


# ---------------------------------------------------------------------------
# Provider query resolution
# ---------------------------------------------------------------------------
def _resolve_query_for_segment(
    segment: dict[str, Any] | None,
    provider: str,
    visual_plan: dict[str, Any] | None,
    strategy: str,
    visual_prompt: str,
    image_prompt: str,
) -> list[str]:
    if segment and segment.get("searchQuery"):
        sq = segment["searchQuery"][:200]
        if provider == "wikimedia_commons":
            return [sq]
        if provider in ("pexels", "pixabay"):
            visual_templates = STRATEGY_VISUAL_QUERIES.get(strategy, [])
            queries = []
            for template in visual_templates:
                queries.append(f"{sq} {template}"[:200])
            queries.append(sq)
            return queries[:3]
        if provider == "freeai":
            gen = segment.get("imageGenerationPrompt", "") or visual_prompt
            return [gen[:500]] if gen else [sq]
        if provider == "pollinations":
            return [sq]
    return resolve_queries_for_provider(provider, visual_plan, strategy, visual_prompt, image_prompt)


def _fetch_one_asset(
    query: str,
    visual_plan: dict[str, Any] | None,
    strategy: str,
    scene_num: int,
    dest: Path,
    dest_exists: bool,
    previous_entity_pool: set[str],
    args: argparse.Namespace,
    pexels_key: str,
    pixabay_key: str,
    freeai_key: str,
    visual_prompt: str,
    image_prompt: str,
    provider_chain: list[str],
    anti_rep_context: dict[str, Any] | None = None,
    extra_queries: list[str] | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    selected_candidate = None
    provider_attempt_order: list[str] = []
    provider_failures: list[dict[str, Any]] = []
    fallback_used = None
    fallback_reason = None
    best_score = None
    ok = False

    for provider in provider_chain:
        provider_attempt_order.append(provider)
        if ok:
            break

        candidates.clear()
        failure_reason = None

        if query or extra_queries:
            base: list[str] = [query] if query else []
            if extra_queries:
                for eq in extra_queries:
                    if eq not in base:
                        base.append(eq)
            pqs = base
        else:
            pqs = resolve_queries_for_provider(
                provider, visual_plan, strategy, visual_prompt, image_prompt
            )

        for q in pqs[:2]:
            if provider == "wikimedia_commons":
                candidates = search_wikimedia(q, args.max_candidates)
                if not candidates:
                    failure_reason = f"wikimedia returned 0 for: {q[:60]}"
            elif provider == "pexels":
                if pexels_key:
                    candidates = search_pexels(q, pexels_key, args.max_candidates)
                    if not candidates:
                        failure_reason = f"pexels returned 0 for: {q[:60]}"
                else:
                    failure_reason = "pexels: no API key"
            elif provider == "pixabay":
                if pixabay_key:
                    candidates = search_pixabay(q, pixabay_key, args.max_candidates)
                    if not candidates:
                        failure_reason = f"pixabay returned 0 for: {q[:60]}"
                else:
                    failure_reason = "pixabay: no API key"
            elif provider == "freeai":
                if freeai_key:
                    candidates = generate_freeai(
                        q, visual_plan.get("negativePrompt", "") if visual_plan else "",
                        freeai_key, scene_num,
                    )
                    if not candidates:
                        failure_reason = "freeai returned no image"
                else:
                    failure_reason = "freeai: no API key"
            elif provider == "pollinations":
                poll_prompt = q or visual_prompt or image_prompt or f"historical {strategy} scene"
                candidates = generate_pollinations(poll_prompt, scene_num)

            if candidates:
                for c in candidates:
                    c["strategy"] = strategy
                break

        if not candidates:
            provider_failures.append({
                "provider": provider,
                "reason": failure_reason or f"{provider}: no candidates",
            })
            continue

        scored = []
        for c in candidates:
            s, reasons = score_candidate(c, visual_plan, scene_num, previous_entity_pool, anti_rep_context)
            if visual_plan:
                er = visual_plan.get("editorialRole")
                er_score, er_reasons = score_editorial_role(c.get("strategy", ""), er)
                s += er_score
                reasons.extend(er_reasons)
            scored.append((s, reasons, c))

        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            bs, breasons, bcandidate = scored[0]
            if dest_exists:
                ok = True
                best_score = bs
            else:
                source_url = bcandidate.get("sourceUrl") or bcandidate.get("thumbnailUrl", "")
                if source_url:
                    ok = download(source_url, dest)
                    if ok:
                        best_score = bs
                else:
                    ok = False

            if ok and (dest_exists or (dest.exists() and dest.stat().st_size > 1000)):
                selected_candidate = bcandidate
                selected_candidate["score"] = bs
                selected_candidate["scoreReasons"] = breasons
                best_score = bs
                if visual_plan:
                    for ent in visual_plan.get("entities", []):
                        previous_entity_pool.add(ent.lower())
                if provider != provider_chain[0]:
                    fallback_used = provider
                    fallback_reason = failure_reason or f"fell back to {provider}"
                break
            else:
                ok = False
                provider_failures.append({
                    "provider": provider,
                    "reason": f"{provider}: download failed for best candidate (score={bs})",
                })
                continue

    if not fallback_used and selected_candidate:
        fallback_used = provider_chain[0]
        fallback_reason = "primary provider succeeded"

    return {
        "ok": ok,
        "selected_candidate": selected_candidate,
        "best_score": best_score,
        "scored": [],
        "provider_attempt_order": provider_attempt_order,
        "provider_failures": provider_failures,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "candidates_count": len(candidates) if candidates else 0,
    }


def resolve_queries_for_provider(
    provider: str,
    visual_plan: dict[str, Any] | None,
    strategy: str,
    visual_prompt: str,
    image_prompt: str,
) -> list[str]:
    if not visual_plan:
        return [visual_prompt or image_prompt or "historical scene"]

    if provider == "wikimedia_commons":
        qs = list(visual_plan.get("searchQueries", []))
        if visual_prompt:
            qs.append(visual_prompt[:200])
        if not qs:
            qs.append(f"historical {strategy.replace('_', ' ')}")
        return qs[:3]

    if provider in ("pexels", "pixabay"):
        visual_templates = STRATEGY_VISUAL_QUERIES.get(strategy, [])
        qs = list(visual_templates)
        for sq in visual_plan.get("searchQueries", [])[:2]:
            qs.append(f"historical {sq}"[:200])
        if image_prompt:
            qs.append(image_prompt[:200])
        return qs[:3]

    if provider == "freeai":
        gen_prompt = visual_plan.get("imageGenerationPrompt", "") or visual_prompt
        if gen_prompt:
            return [gen_prompt[:500]]
        return [visual_prompt or f"historical {strategy} scene"][:1]

    if provider == "pollinations":
        return [visual_prompt or image_prompt or f"historical {strategy} scene"]

    return [visual_prompt or image_prompt or "historical scene"]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_candidate(
    candidate: dict[str, Any],
    visual_plan: dict[str, Any] | None,
    scene_num: int,
    previous_entity_pool: set[str],
    anti_rep_context: dict[str, Any] | None = None,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    title = (candidate.get("title") or "").lower()
    query_used = (candidate.get("queryUsed") or "").lower()
    w = candidate.get("width", 0) or 0
    h = candidate.get("height", 0) or 0
    license_val = (candidate.get("license") or "").lower()
    provider = candidate.get("provider", "")

    if visual_plan:
        entities = visual_plan.get("entities", [])
        for ent in entities:
            if ent.lower() in title or ent.lower() in query_used:
                score += SCORING_WEIGHTS["entity_match"]
                reasons.append(f"Entity match: {ent}")
                break

    if visual_plan:
        period = (visual_plan.get("period") or "").lower()
        location = (visual_plan.get("location") or "").lower()
        if period and (period in title or period in query_used):
            score += SCORING_WEIGHTS["period_or_location_match"]
            reasons.append(f"Period match: {period}")
        if location and (location in title or location in query_used):
            score += SCORING_WEIGHTS["period_or_location_match"]
            reasons.append(f"Location match: {location}")

    primary = (visual_plan.get("primaryAssetType") or "") if visual_plan else ""
    if primary and provider in ("wikimedia_commons",) and primary in ("historical_photograph", "map", "painting"):
        score += SCORING_WEIGHTS["asset_type_match"]
        reasons.append(f"Archive source suitable for {primary}")

    if w >= MIN_WIDTH and h >= MIN_HEIGHT:
        score += SCORING_WEIGHTS["sufficient_resolution"]
        reasons.append(f"Sufficient resolution ({w}x{h})")
    else:
        score += SCORING_WEIGHTS["low_resolution"]
        reasons.append(f"Low resolution ({w}x{h})")

    if license_val in ("public domain", "cc0", "cc-by", "cc-by-sa", "pexels license", "pixabay license"):
        score += SCORING_WEIGHTS["clear_license"]
        reasons.append(f"Clear license: {license_val}")
    elif license_val in ("unknown", ""):
        score += SCORING_WEIGHTS["unknown_license"]
        reasons.append("Unknown license")

    if visual_plan:
        preferred = visual_plan.get("preferredSources", [])
        if provider in preferred:
            score += SCORING_WEIGHTS["preferred_source"]
            reasons.append(f"Preferred source: {provider}")

    if visual_plan:
        for ent in visual_plan.get("entities", []):
            if ent.lower() in previous_entity_pool:
                score += SCORING_WEIGHTS["duplicate_entity"]
                reasons.append(f"Duplicate entity: {ent}")
                break

    # --- Anti-repetition scoring ---
    if anti_rep_context:
        used_urls = anti_rep_context.get("used_urls", set())
        used_authors = anti_rep_context.get("used_authors", {})
        used_queries = anti_rep_context.get("used_queries", [])
        used_asset_types = anti_rep_context.get("used_asset_types", [])
        current_scene_num = anti_rep_context.get("current_scene_num", scene_num)
        current_asset_type = anti_rep_context.get("current_asset_type", "")

        source_url = candidate.get("sourceUrl", "").rstrip("/")
        if source_url in used_urls:
            score += SCORING_WEIGHTS.get("duplicate_url", -50)
            reasons.append("Duplicate URL already used in video")

        author = candidate.get("author", "").strip()
        provider = candidate.get("provider", "")
        author_key = f"{provider}|{author}" if author and provider else ""
        if author_key and author_key in used_authors:
            last_scene = used_authors[author_key]
            if current_scene_num - last_scene <= 1:
                score += SCORING_WEIGHTS.get("same_author_provider", -40)
                reasons.append(f"Same author+provider in consecutive scenes")

        query_used = candidate.get("queryUsed", "").lower().strip()
        if query_used:
            for prev_scene, prev_query in used_queries:
                if prev_query == query_used and current_scene_num - prev_scene < 3:
                    score += SCORING_WEIGHTS.get("same_query", -30)
                    reasons.append("Same query used in nearby scene")
                    break

        if used_asset_types and current_asset_type:
            consecutive_scenes_with_same_type = 0
            for at in reversed(used_asset_types):
                if at == current_asset_type:
                    consecutive_scenes_with_same_type += 1
                else:
                    break
            if consecutive_scenes_with_same_type >= 1:
                score += SCORING_WEIGHTS.get("same_asset_type", -20)
                reasons.append(f"Same assetType as previous scene")

    return score, reasons


def score_editorial_role(asset_type: str, editorial_role: str | None) -> tuple[int, list[str]]:
    if not editorial_role:
        return 0, []
    prefs = EDITORIAL_ROLE_PREFERENCES.get(editorial_role, {})
    preferred = prefs.get("preferred", set())
    forbidden = prefs.get("forbidden", set())
    if asset_type in forbidden:
        return -20, [f"Asset type {asset_type} forbidden for role {editorial_role}"]
    if asset_type in preferred:
        return 15, [f"Asset type {asset_type} preferred for role {editorial_role}"]
    return -10, [f"Asset type {asset_type} suboptimal for role {editorial_role}"]


# ---------------------------------------------------------------------------
# Historical query hierarchy builder
# Generates prioritized queries for historical segments:
#   a) entity + asset type
#   b) entity + period
#   c) asset type + event
#   d) documentary fallback
# ---------------------------------------------------------------------------
ASSET_TYPE_QUERY_TERMS: dict[str, list[str]] = {
    "historical_map": ["map", "cartography", "atlas"],
    "historical_photograph": ["portrait", "photograph", "illustration", "painting", "miniature"],
    "historical_art_or_document": ["painting", "engraving", "manuscript", "document", "miniature", "drawing"],
    "atmospheric_broll": ["walls", "fortress", "city", "landscape", "architecture"],
    "document": ["document", "manuscript", "letter", "scroll"],
    "map": ["map", "atlas", "cartography"],
    "illustration": ["illustration", "drawing", "engraving", "miniature"],
    "painting": ["painting", "oil", "canvas", "fresco"],
}

def build_historical_queries(
    visual_plan: dict[str, Any] | None,
    seg: dict[str, Any] | None,
    strategy: str,
    visual_prompt: str,
    image_prompt: str,
) -> list[str]:
    queries: list[str] = []
    if not visual_plan:
        return [visual_prompt or image_prompt or "historical scene"]

    entities = visual_plan.get("entities", [])
    period = visual_plan.get("period", "")
    location = visual_plan.get("location", "")
    asset_type = (seg.get("assetType") if seg else None) or visual_plan.get("primaryAssetType", "")
    event_query = (seg.get("searchQuery") if seg else None) or ""
    at_terms = ASSET_TYPE_QUERY_TERMS.get(asset_type, [asset_type.replace("_", " ")])

    # Level 0: segment searchQuery (most specific, use as-is for Wikimedia)
    if event_query and event_query not in queries:
        queries.append(event_query)

    # Level a: entity + concrete asset type (highly specific)
    for ent in entities:
        for term in at_terms:
            q = f"{ent} {term}".strip()
            if q and q not in queries:
                queries.append(q)

    # Level b: event/entity + period + location (contextual)
    context_parts = []
    if event_query:
        context_parts.append(event_query)
    for ent in entities:
        context_parts.append(ent)
    if period:
        context_parts.append(period)
    if location:
        context_parts.append(location)
    if context_parts:
        # Build "event period location" style queries
        base = context_parts[0]
        for extra in context_parts[1:]:
            q = f"{base} {extra}".strip()
            if q and q not in queries and len(q) < 150:
                queries.append(q)

    # Level c: event + term
    if event_query:
        for term in at_terms:
            q = f"{event_query} {term}".strip()
            if q and q not in queries:
                queries.append(q)

    # Level d: location/period + asset type (good when entities are empty)
    loc_period = location or period or ""
    if loc_period and not entities:
        for term in at_terms:
            q = f"{loc_period} {term}".strip()
            if q and q not in queries:
                queries.append(q)
        if period and location:
            q = f"{period} {location}".strip()
            if q and q not in queries:
                queries.append(q)

    # Level e: entity + documentary fallback
    for ent in entities:
        q = f"Byzantine {ent} manuscript".strip()
        if q and q not in queries:
            queries.append(q)
        q = f"historical {ent} illustration".strip()
        if q and q not in queries:
            queries.append(q)

    # Level f: generic prompt fallback
    if visual_prompt and visual_prompt not in queries:
        queries.append(visual_prompt[:200])
    if image_prompt and image_prompt not in queries:
        queries.append(image_prompt[:200])

    return queries[:8]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_path")
    parser.add_argument("--max-candidates", type=int, default=5, help="Max candidates per provider")
    args = parser.parse_args()

    metadata_path = Path(args.metadata_path).resolve()
    video_dir = metadata_path.parent
    data = json.loads(metadata_path.read_text())
    job_id = data["jobId"]
    scenes = data["script"]["scenes"]

    sdir = video_dir / "scenes"
    sdir.mkdir(parents=True, exist_ok=True)

    DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"
    env = {}
    if DOTENV_PATH.exists():
        for line in DOTENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    env.update(dict(__import__("os").environ))
    freeai_key = env.get("FREEAI_API_KEY", "")
    pexels_key = env.get("PEXELS_API_KEY", "")
    pixabay_key = env.get("PIXABAY_API_KEY", "")

    previous_entity_pool: set[str] = set()
    used_urls: set[str] = set()
    used_authors: dict[str, int] = {}
    used_queries: list[tuple[int, str]] = []
    used_asset_types: list[str] = []

    results = []
    for scene in scenes:
        scene_num = int(scene["sceneNumber"])
        visual_plan = scene.get("visualPlan")
        visual_prompt = scene.get("visualPrompt", "")
        image_prompt = scene.get("imagePrompt", "")

        if visual_plan:
            strategy = visual_plan.get("strategy", "historical_archive")
            provider_chain = STRATEGY_CHAINS.get(strategy, STRATEGY_CHAINS["historical_archive"])
        else:
            strategy = "legacy"
            provider_chain = ["pollinations"]
            visual_prompt = visual_prompt or image_prompt or "historical scene"
            image_prompt = ""

        visual_sequence = visual_plan.get("visualSequence") if visual_plan else None

        if visual_sequence:
            segments = []
            all_ok_segments = True
            for seg in visual_sequence:
                seg_idx = seg["segmentIndex"]
                seg_dest = sdir / f"scene-{scene_num:02}-{seg_idx:02}.jpg"
                seg_exists = seg_dest.exists() and seg_dest.stat().st_size > 1000

                seg_query = seg.get("searchQuery", "")
                seg_at = seg.get("assetType", "broll")
                editorial_role = visual_plan.get("editorialRole") if visual_plan else None

                # Select provider chain based on editorial role
                if editorial_role in ROLE_PROVIDER_CHAINS:
                    seg_chain = list(ROLE_PROVIDER_CHAINS[editorial_role])
                elif seg_at == "generated_reconstruction":
                    seg_chain = STRATEGY_CHAINS.get("generated_reconstruction", ["freeai", "pollinations"])
                elif seg_at == "atmospheric_broll":
                    seg_chain = STRATEGY_CHAINS.get("atmospheric_broll", ["pexels", "pixabay", "freeai", "pollinations"])
                elif seg_at in ("historical_map", "map"):
                    seg_chain = STRATEGY_CHAINS.get("map_or_document", provider_chain)
                else:
                    seg_chain = list(provider_chain)

                # Build historical queries for hard historical roles
                if editorial_role in HARD_HISTORICAL_ROLES:
                    hist_queries = build_historical_queries(visual_plan, seg, strategy, visual_prompt, image_prompt)
                    if hist_queries:
                        seg_query = hist_queries[0]
                        # Store all queries for multi-query fallback within wikimedia
                        _all_seg_queries = hist_queries
                    else:
                        _all_seg_queries = [seg_query] if seg_query else []
                else:
                    _all_seg_queries = [seg_query] if seg_query else []

                anti_rep_context = {
                    "used_urls": used_urls,
                    "used_authors": used_authors,
                    "used_queries": used_queries,
                    "used_asset_types": used_asset_types,
                    "current_scene_num": scene_num,
                    "current_asset_type": seg_at,
                }

                extra_qs = _all_seg_queries[1:] if _all_seg_queries else None
                result = _fetch_one_asset(
                    query=seg_query,
                    visual_plan=visual_plan,
                    strategy=strategy,
                    scene_num=scene_num,
                    dest=seg_dest,
                    dest_exists=seg_exists,
                    previous_entity_pool=previous_entity_pool,
                    args=args,
                    pexels_key=pexels_key,
                    pixabay_key=pixabay_key,
                    freeai_key=freeai_key,
                    visual_prompt=visual_prompt,
                    image_prompt=image_prompt,
                    provider_chain=seg_chain,
                    anti_rep_context=anti_rep_context,
                    extra_queries=extra_qs,
                )

                cand = result["selected_candidate"]
                dur_frac = seg.get("durationFraction", 1.0 / len(visual_sequence))
                seg_entry = {
                    "segmentIndex": seg_idx,
                    "path": str(seg_dest) if result["ok"] else None,
                    "assetType": seg_at,
                    "durationSec": round(scene["targetDurationSec"] * dur_frac, 1),
                    "transition": seg.get("transition", "cut"),
                    "provider": cand.get("provider") if cand else None,
                    "sourceUrl": cand.get("sourceUrl") if cand else None,
                    "license": cand.get("license") if cand else None,
                    "author": cand.get("author") if cand else None,
                    "score": cand.get("score") if cand else None,
                    "scoreReasons": cand.get("scoreReasons") if cand else None,
                    "width": cand.get("width") if cand else None,
                    "height": cand.get("height") if cand else None,
                    "editorialReason": seg.get("editorialReason", ""),
                    "downloadedAt": datetime.now(timezone.utc).isoformat() if result["ok"] else None,
                    # Anti-repetition metadata
                    "duplicateRisk": "none",
                    "previousSimilarAssets": [],
                    "reuseAllowed": False,
                    "reuseReason": "",
                    "focalRegion": seg.get("focalRegion", "center"),
                    "cropMode": seg.get("cropMode", "full_map"),
                    "overlayText": seg.get("overlayText", ""),
                    "mapReadabilityScore": None,
                    "visualAuthenticityRisk": None,
                }

                if seg_at in ("historical_map", "map", "document"):
                    w = seg_entry.get("width", 0) or 0
                    h = seg_entry.get("height", 0) or 0
                    if w and h and w > h:
                        readability = min(w / 1080, h / 1920) * (1 - abs(w / h - 9 / 16) / 2)
                        seg_entry["mapReadabilityScore"] = round(min(readability, 1.0), 2)

                # Editorial role scoring
                editorial_role = visual_plan.get("editorialRole") if visual_plan else None
                if editorial_role and result["ok"]:
                    er_score, er_reasons = score_editorial_role(seg_at, editorial_role)
                    if seg_entry["score"] is not None:
                        seg_entry["score"] = seg_entry["score"] + er_score
                    seg_entry["scoreReasons"] = (seg_entry.get("scoreReasons") or []) + er_reasons
                    seg_entry["editorialScore"] = er_score
                    seg_entry["editorialRole"] = editorial_role

                if not result["ok"]:
                    all_ok_segments = False
                    if editorial_role in HARD_HISTORICAL_ROLES and result.get("provider_attempt_order") == ["wikimedia_commons"]:
                        seg_entry["error"] = "ASSET_UNRESOLVED"
                        print(f"  scene {scene_num} seg {seg_idx}: ASSET_UNRESOLVED ({seg_query[:50]})")
                    else:
                        seg_entry["error"] = "Download failed"
                        print(f"  scene {scene_num} seg {seg_idx}: FAILED ({seg_query[:50]})")
                else:
                    source_url = (cand.get("sourceUrl") or "").rstrip("/")
                    if source_url:
                        used_urls.add(source_url)
                    author = (cand.get("author") or "").strip()
                    provider = cand.get("provider", "")
                    author_key = f"{provider}|{author}" if author and provider else ""
                    if author_key:
                        used_authors[author_key] = scene_num
                    q_used = (cand.get("queryUsed") or "").lower().strip()
                    if q_used:
                        used_queries.append((scene_num, q_used))
                    if seg_at:
                        used_asset_types.append(seg_at)
                    print(f"  scene {scene_num} seg {seg_idx}: OK ({cand.get('provider')}) score={cand.get('score')}")

                segments.append(seg_entry)
                time.sleep(SCENE_PAUSE_SEC)

            ok = all_ok_segments
            first_seg = segments[0] if segments else {}
            asset_meta = {
                "sceneNumber": scene_num,
                "selected": ok,
                "path": first_seg.get("path"),
                "strategy": strategy,
                "assetType": visual_plan.get("primaryAssetType"),
                "segments": segments,
                "provider": first_seg.get("provider"),
                "sourceUrl": first_seg.get("sourceUrl"),
                "originalUrl": first_seg.get("sourceUrl"),
                "title": None,
                "author": first_seg.get("author"),
                "license": first_seg.get("license"),
                "score": first_seg.get("score"),
                "scoreReasons": first_seg.get("scoreReasons"),
                "downloadedAt": first_seg.get("downloadedAt"),
                "error": None if ok else "Some segments failed",
            }
        else:
            dest = sdir / f"scene-{scene_num:02}.jpg"
            dest_exists = dest.exists() and dest.stat().st_size > 1000

            anti_rep_context = {
                "used_urls": used_urls,
                "used_authors": used_authors,
                "used_queries": used_queries,
                "used_asset_types": used_asset_types,
                "current_scene_num": scene_num,
                "current_asset_type": visual_plan.get("primaryAssetType", "") if visual_plan else "",
            }

            result = _fetch_one_asset(
                query="",
                visual_plan=visual_plan,
                strategy=strategy,
                scene_num=scene_num,
                dest=dest,
                dest_exists=dest_exists,
                previous_entity_pool=previous_entity_pool,
                args=args,
                pexels_key=pexels_key,
                pixabay_key=pixabay_key,
                freeai_key=freeai_key,
                visual_prompt=visual_prompt,
                image_prompt=image_prompt,
                provider_chain=provider_chain,
                anti_rep_context=anti_rep_context,
            )

            ok = result["ok"]
            selected_candidate = result["selected_candidate"]
            best_score = result["best_score"]
            scored = result["scored"]

            if not dest_exists and ok:
                print(f"  scene {scene_num}: OK ({selected_candidate.get('provider')}) score={best_score}")
            elif not ok:
                print(f"  scene {scene_num}: download FAILED" if not dest_exists else f"  scene {scene_num}: exists")

            asset_meta = {
                "sceneNumber": scene_num,
                "selected": ok,
                "path": str(dest) if ok else None,
                "strategy": strategy,
                "provider": selected_candidate.get("provider") if selected_candidate else None,
                "assetType": visual_plan.get("primaryAssetType") if visual_plan else None,
                "sourceUrl": selected_candidate.get("sourceUrl") if selected_candidate else None,
                "originalUrl": selected_candidate.get("sourceUrl") if selected_candidate else None,
                "title": selected_candidate.get("title") if selected_candidate else None,
                "author": selected_candidate.get("author") if selected_candidate else None,
                "license": selected_candidate.get("license") if selected_candidate else None,
                "attributionRequired": selected_candidate.get("license", "").lower() in ("cc-by", "cc-by-sa") if selected_candidate else None,
                "queryUsed": selected_candidate.get("queryUsed") if selected_candidate else None,
                "width": selected_candidate.get("width") if selected_candidate else None,
                "height": selected_candidate.get("height") if selected_candidate else None,
                "score": selected_candidate.get("score") if selected_candidate else None,
                "scoreReasons": selected_candidate.get("scoreReasons") if selected_candidate else None,
                "downloadedAt": datetime.now(timezone.utc).isoformat() if ok else None,
                "providerAttemptOrder": result["provider_attempt_order"],
                "providerFailures": result["provider_failures"] if result["provider_failures"] else None,
                "fallbackApplied": result["fallback_used"],
                "fallbackReason": result["fallback_reason"],
                "fallbackChain": provider_chain,
                "candidateCount": result.get("candidates_count", 0),
                "selectedCandidateScore": best_score,
                "error": None if ok else "No valid candidate found or download failed",
            }

            discarded = []
            if scored:
                for s, reasons, c in scored[1:]:
                    source = c.get("sourceUrl") or c.get("thumbnailUrl", "")
                    discarded.append({
                        "provider": c.get("provider"),
                        "sourceUrl": source,
                        "score": s,
                        "discardReason": reasons[:2],
                        "license": c.get("license"),
                    })
            asset_meta["discardedCandidates"] = discarded if discarded else None

        results.append(asset_meta)
        time.sleep(SCENE_PAUSE_SEC)

    data["assets"] = results
    data["updatedAt"] = datetime.now(timezone.utc).isoformat()

    all_ok = all(r.get("selected", False) for r in results)
    data["status"] = "ASSETS_READY" if all_ok else "ASSETS_PARTIAL"
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    print(json.dumps({"jobId": job_id, "success": all_ok}))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
