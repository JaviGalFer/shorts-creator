#!/usr/bin/env python3

import argparse
import json
import os
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from editorial_asset_contract import EDITORIAL_ROLE_PREFERENCES, is_asset_type_allowed

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
RENDER_MIN_WIDTH = 720
RENDER_MIN_HEIGHT = 720
MIN_MAP_READABILITY = 0.40
USER_AGENT = "ShortsHistoricos/1.0 (historical video pipeline; +https://github.com/javi/shorts-historicos)"

ACCENT_MAP = {
    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
    'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
    'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
    'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
    'ñ': 'n', 'ç': 'c',
}
def _unaccent(text: str) -> str:
    return ''.join(ACCENT_MAP.get(c, c) for c in text.lower())

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
    "border_closure_construction",
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
# Visual/generic query templates for stock photo APIs.
# These are intentionally EMPTY: provider queries are composed exclusively
# from scene metadata (searchQueries, entities, location, period,
# visualPrompt, imagePrompt). No hardcoded genre or era templates.
# ---------------------------------------------------------------------------
STRATEGY_VISUAL_QUERIES: dict[str, list[str]] = {
    "historical_archive": [],
    "map_or_document": [],
    "atmospheric_broll": [],
    "generated_reconstruction": [],
}

CANDIDATES_PER_PROVIDER = 5
MIN_SCORE = 30

# ---------------------------------------------------------------------------

# (EDITORIAL_ROLE_PREFERENCES and is_asset_type_allowed imported from
#  editorial_asset_contract.py — shared with generate_script.py)

SCENE_PAUSE_SEC = 0.5

# ---------------------------------------------------------------------------
# Temporal visual intent model
# ---------------------------------------------------------------------------
# event_depiction: the image must depict the historical event, period, or
#   contemporary evidence. For example, "El Muro cayó en 1989" requires 1989
#   fall footage/photos, people on the wall in 1989, or an archival image
#   directly tied to the event.
# legacy_or_commemoration: allows modern memorials, anniversaries, museums,
#   monuments, or current gatherings. For example, "El legado del Muro sigue
#   presente" may use a 2024 anniversary event.

EVENT_DEPICTION_ROLES = {"context_map", "character_portrait", "battle_or_assault",
                         "border_closure_construction", "military_technology",
                         "civilian_impact", "document_or_date"}

def _classify_temporal_intent(scene: dict) -> str:
    """Classify a scene's visual temporal intent.  Prefers the explicit
    ``visualTemporalIntent`` field authored by the LLM (Phase 23 follow-up).
    Falls back to heuristic when the field is absent."""
    llm_intent = (scene.get("visualTemporalIntent") or "").strip().lower()
    if llm_intent in ("event_depiction", "legacy_or_commemoration", "context_or_setup"):
        return llm_intent
    vp = scene.get("visualPlan") or {}
    role = vp.get("editorialRole", "")
    if role in EVENT_DEPICTION_ROLES:
        return "event_depiction"
    if role == "consequence_or_legacy":
        vo = (scene.get("voiceover") or "").lower()
        legacy_indicators = ["legado", "recuerda", "sigue", "presente", "hoy", "actualmente",
                             "memoria", "conmemora", "aniversario", "museo", "monumento"]
        for ind in legacy_indicators:
            if ind in vo:
                return "legacy_or_commemoration"
        event_indicators = ["cayó", "cayo", "derribó", "derrumbó", "1989", "1990", "1991",
                            "caída", "caida"]
        for ind in event_indicators:
            if ind in vo:
                return "event_depiction"
        return "event_depiction"
    return "legacy_or_commemoration"


def _determine_asset_temporal_match(candidate: dict, visual_plan: dict, scene: dict | None = None) -> str:
    """Determine if a candidate shows historical event, archival context, or modern legacy."""
    title = (candidate.get("title") or "").lower()
    description = (candidate.get("description") or candidate.get("sourceDescription") or "").lower()
    combined = f"{title} {description}"
    combined_u = _unaccent(combined)
    url = (candidate.get("sourceUrl") or "").lower()
    url_u = _unaccent(url)

    period = (visual_plan.get("period") or "").lower()
    period_u = _unaccent(period)
    event_year = ""
    # Extract 4-digit year from period
    for token in period.split():
        if token.isdigit() and len(token) == 4:
            event_year = token
            break
    # Fallback: check entities and voiceover for explicit year
    if not event_year:
        for ent in visual_plan.get("entities", []):
            ent_clean = ent.strip(".,;:!?")
            if ent_clean.isdigit() and len(ent_clean) == 4:
                event_year = ent_clean
                break
    if not event_year and scene:
        scene_vo = (scene.get("voiceover") or "")
        for token in scene_vo.split():
            clean = token.strip(".,;:!?()[]{}'\"")
            if clean.isdigit() and len(clean) == 4:
                event_year = clean
                break

    # Modern indicators: recent anniversaries, modern dates, contemporary events
    modern_years = {"2024", "2023", "2022", "2021", "2020", "2019",
                    "2018", "2017", "2016", "2015", "2014", "2013",
                    "2012", "2011", "2010", "2009", "2008", "2007",
                    "2006", "2005", "2004", "2003", "2002", "2001", "2000"}
    modern_indicators = {"anniversary", "aniversario", "commemoration", "conmemoración",
                         "today", "hoy", "modern", "current", "actual",
                         "celebration", "celebración", "festival", "event"}
    has_modern_year = any(y in combined or y in url for y in modern_years)
    has_modern_indicator = any(i in combined for i in modern_indicators)
    # Historical years in candidate metadata
    historical_years_in_candidate = set()
    context_years_in_candidate = set()
    for m in _DASH_RANGE_RE.finditer(combined + " " + url):
        start_y = int(m.group(1))
        end_y = int(m.group(2))
        if end_y < start_y:
            start_y, end_y = end_y, start_y
        for y in range(start_y, end_y + 1):
            context_years_in_candidate.add(str(y))
    for token in (combined + " " + url).split():
        clean = token.strip(".,;:!?()[]{}'\"")
        if clean.isdigit() and len(clean) == 4:
            y = int(clean)
            if 1800 <= y <= 1999:
                historical_years_in_candidate.add(clean)
    depicted_years_in_candidate = historical_years_in_candidate - context_years_in_candidate

    has_event_year = bool(event_year) and (
        event_year in depicted_years_in_candidate or
        (event_year in combined and event_year not in context_years_in_candidate)
    )

    # Accent-insensitive matching for period/entity terms
    # Combined text is checked in both original and unaccented forms
    # to handle Spanish terms vs English text matching
    def _match_term(term: str) -> bool:
        """Check term against combined text with accent-insensitive matching."""
        term_lower = term.lower()
        term_u = _unaccent(term_lower)
        return (term_u in combined_u) or (term_lower in combined)

    def _match_period(period_raw: str) -> bool:
        """Match period with multilingual fallback."""
        if not period_raw:
            return False
        pr = period_raw.lower()
        # Direct check
        if _match_term(pr):
            return True
        # Unaccented check
        pr_u = _unaccent(pr)
        if pr_u in combined_u:
            return True
        # English/German fallback for Spanish period names
        period_equivalents = {
            "guerra fría": ["cold war", "kalter krieg", "post-war", "coldwar"],
            "guerra fria": ["cold war", "kalter krieg", "post-war", "coldwar"],
            "segunda guerra mundial": ["world war ii", "wwii", "second world war", "zweiter weltkrieg"],
            "posguerra": ["post-war", "postwar", "nachkriegszeit"],
            "post-guerra fría": ["cold war", "post-war", "postwar"],  # generic post-Cold-War translations
            "post-guerra fria": ["cold war", "post-war", "postwar"],
            "entreguerras": ["interwar", "between wars", "zwischenkriegszeit"],
        }
        for eq in period_equivalents.get(pr, period_equivalents.get(pr_u, [])):
            if eq in combined or _unaccent(eq) in combined_u:
                return True
        return False

    def _match_location(loc_raw: str) -> bool:
        """Match location with multilingual fallback."""
        if not loc_raw:
            return False
        lr = loc_raw.lower()
        if _match_term(lr):
            return True
        lr_u = _unaccent(lr)
        # Check individual location tokens (e.g. a town name in text containing the same stem)
        for token in lr_u.split():
            if len(token) > 2 and token in combined_u:
                return True
        # Generic location translation equivalents (no topic-specific locations)
        location_equivalents = {
            "alemania": ["germany", "deutschland", "german"],
        }
        for eq in location_equivalents.get(lr, location_equivalents.get(lr_u, [])):
            if eq in combined or _unaccent(eq) in combined_u:
                return True
        return False

    def _match_entity(ent_raw: str) -> bool:
        """Match entity with accent-insensitive and multilingual support."""
        if not ent_raw:
            return False
        er = ent_raw.lower()
        if _match_term(er):
            return True
        er_u = _unaccent(er)
        # Token-level intersection for multi-word entities
        ent_tokens = set(er_u.split())
        if len(ent_tokens) >= 1 and ent_tokens.intersection(combined_u.split()):
            return True
        # Generic entity translation equivalents (no topic-specific entities)
        entity_equivalents = {
            "familias": ["family", "families", "familie"],
            "familia": ["family", "families", "familie"],
        }
        for eq in entity_equivalents.get(er, entity_equivalents.get(er_u, [])):
            if eq in combined or _unaccent(eq) in combined_u:
                return True
        return False

    entities = visual_plan.get("entities", [])
    has_event_term = _match_period(period)
    has_entity_term = any(_match_entity(e) for e in entities)
    has_location_term = _match_location(visual_plan.get("location", ""))
    # Map/document indicators in the candidate itself (not in role terms)
    _map_or_doc_in_title = any(
        ind in combined or _unaccent(ind) in combined_u
        for ind in (
            "map", "karte", "atlas", "plan", "cartography", "cartografía",
            "diagram", "diagrama", "occupation zones", "sectors",
            "document", "dokument", "newspaper", "zeitung", "treaty", "vertrag",
        )
    )
    if has_event_year and has_event_term:
        return "historical_event"
    if has_modern_indicator and not has_event_year:
        return "modern_legacy"
    if historical_years_in_candidate and (has_event_term or has_entity_term or has_location_term):
        return "archival_context"
    if has_event_term and not has_modern_year:
        return "archival_context"
    if has_modern_year or has_modern_indicator:
        return "modern_legacy"
    if historical_years_in_candidate and (has_entity_term or has_location_term):
        return "archival_context"
    # Maps and archival documents with entity/location match are archival context
    # even without an explicit year (e.g., 1945 occupation-zone maps are relevant
    # to border context)
    if _map_or_doc_in_title and (has_entity_term or has_location_term):
        return "archival_context"
    return "unknown"


def _build_scene_query_variants(scene: dict, visual_plan: dict) -> list[str]:
    """Generate structured query variants for a scene, including English and German."""
    vp = visual_plan or {}
    queries: list[str] = []
    seen: set[str] = set()

    topic = scene.get("voiceover", "")
    role = vp.get("editorialRole", "")
    period = vp.get("period", "")
    location = vp.get("location", "")
    entities = vp.get("entities", [])
    primary_at = vp.get("primaryAssetType", "")

    def add(q: str):
        qs = q.strip()[:200]
        if qs and qs.lower() not in seen:
            seen.add(qs.lower())
            queries.append(qs)

    # Role-specific term maps for each editorial role
    role_terms = {
        "context_map": ["map", "cartography", "atlas", "occupation zones", "division", "sectors"],
        "battle_or_assault": ["construction", "building", "barbed wire", "barricades",
                             "concrete", "border guards", "military", "soldiers"],
        "border_closure_construction": ["barbed wire", "barricades", "road block",
                                       "border closure", "Stacheldraht",
                                       "Abriegelung", "Grenzsperre", "Sperranlagen",
                                       "construction", "building", "concrete barrier"],
        "civilian_impact": ["families", "family separation", "border crossing",
                            "refugees", "escape", "checkpoint", "divided city"],
        "consequence_or_legacy": ["fall", "opening", "celebration", "crowd",
                                 "wall coming down", "border open", "freedom"],
    }
    extra_terms = role_terms.get(role, [])

    # Entity-based queries (English)
    for ent in entities:
        for term in extra_terms:
            add(f"{ent} {term}")
        if period:
            add(f"{ent} {period}")
        if location:
            add(f"{ent} {location}")

    # Period + location + role term
    if period and location:
        for term in extra_terms:
            add(f"{location} {period} {term}")
        add(f"{period} {location}")

    # Primary asset type queries
    if primary_at == "historical_map":
        add(f"Map of {location} {period}")
        add(f"{location} map {period}")
    elif primary_at == "historical_photograph":
        for ent in entities:
            add(f"{ent} historical photograph")
        if location and period:
            add(f"{location} {period} photograph")

    # Add scene search queries from visualPlan
    vs = vp.get("visualSequence", [])
    for seg in vs:
        sq = seg.get("searchQuery", "")
        if sq:
            add(sq)

    # Add seed query from visualPlan searchQueries
    for sq in vp.get("searchQueries", []):
        add(sq)

    return queries[:12]

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
                title_meta = title_meta[:500] if title_meta else None
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
    topic: str = "",
    scene: dict | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    selected_candidate = None
    provider_attempt_order: list[str] = []
    provider_failures: list[dict[str, Any]] = []
    fallback_used = None
    fallback_reason = None
    best_score = None
    ok = False
    _download_attempted = False
    _failure_classification = None

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
            if not pqs:
                provider_failures.append({
                    "provider": provider,
                    "reason": f"{provider}: MISSING_VISUAL_METADATA (empty visualPlan or no searchQueries/prompts)",
                })
                continue

        all_candidates: list[dict[str, Any]] = []
        for q in pqs[:6]:
            batch: list[dict[str, Any]] = []
            if provider == "wikimedia_commons":
                batch = search_wikimedia(q, args.max_candidates)
                if not batch:
                    failure_reason = f"wikimedia returned 0 for: {q[:60]}"
            elif provider == "pexels":
                if pexels_key:
                    batch = search_pexels(q, pexels_key, args.max_candidates)
                    if not batch:
                        failure_reason = f"pexels returned 0 for: {q[:60]}"
                else:
                    failure_reason = "pexels: no API key"
            elif provider == "pixabay":
                if pixabay_key:
                    batch = search_pixabay(q, pixabay_key, args.max_candidates)
                    if not batch:
                        failure_reason = f"pixabay returned 0 for: {q[:60]}"
                else:
                    failure_reason = "pixabay: no API key"
            elif provider == "freeai":
                if freeai_key:
                    batch = generate_freeai(
                        q, visual_plan.get("negativePrompt", "") if visual_plan else "",
                        freeai_key, scene_num,
                    )
                    if not batch:
                        failure_reason = "freeai returned no image"
                else:
                    failure_reason = "freeai: no API key"
            elif provider == "pollinations":
                poll_prompt = q or visual_prompt or image_prompt
                if poll_prompt:
                    batch = generate_pollinations(poll_prompt, scene_num)
                else:
                    failure_reason = "pollinations: MISSING_VISUAL_METADATA (no prompt available)"

            for c in batch:
                c["strategy"] = strategy
            all_candidates.extend(batch)

        candidates = all_candidates

        if scene_num == 3 and candidates:
            s_test, r_test = score_candidate(candidates[0], visual_plan, scene_num, previous_entity_pool, anti_rep_context)
            s_no_rep, _ = score_candidate(candidates[0], visual_plan, scene_num, previous_entity_pool, None)
        if not candidates:
            provider_failures.append({
                "provider": provider,
                "reason": failure_reason or f"{provider}: no candidates",
            })
            continue

        scored = []
        for c in candidates:
            s, reasons = score_candidate(c, visual_plan, scene_num, previous_entity_pool, anti_rep_context)
            scored.append((s, reasons, c))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Stage 1: Filter candidates before download selection
        # Reject: negative score, score < MIN_SCORE,
        # unsupported dimensions, Pexels for hard historical roles.
        # (Requested-type compatibility is verified by the final
        #  shared validator, not by candidate strategy.)
        editorial_role_str = (visual_plan.get("editorialRole") if visual_plan else None) or ""

        valid_scored = []
        for s, reasons, c in scored:
            if s < 0:
                continue  # reject negative score
            if s < MIN_SCORE:
                continue  # reject below minimum threshold
            provider = c.get("provider", "")
            if provider == "pexels" and editorial_role_str in HARD_HISTORICAL_ROLES:
                continue  # reject Pexels for hard historical roles
            c_width = c.get("width", 0) or 0
            c_height = c.get("height", 0) or 0
            if c_width > 10000 or c_height > 10000:
                continue  # reject decompression-bomb risk
            # Semantic provenance check
            semantic_ev = _check_semantic_evidence(c, scene or {}, topic)
            c["semanticEvidence"] = semantic_ev
            if semantic_ev["semanticConfidence"] == "low":
                if editorial_role_str in HARD_HISTORICAL_ROLES:
                    continue
                has_topic_or_loc = bool(semantic_ev.get("topicTermsMatched")) or bool(semantic_ev.get("locationTermsMatched"))
                if not semantic_ev["sourceTitle"] or not has_topic_or_loc:
                    continue  # reject: low confidence without meaningful provenance
                reasons.append(f"semanticEvidence=low topicMatch={semantic_ev['topicTermsMatched']}")
                s -= 20
            else:
                reasons.append(f"semanticEvidence={semantic_ev['semanticConfidence']}")

            # Temporal intent filtering
            temporal_intent = _classify_temporal_intent(scene or {})
            c["visualTemporalIntent"] = temporal_intent
            asset_match = _determine_asset_temporal_match(c, visual_plan or {}, scene)
            c["assetTemporalMatch"] = asset_match

            # Hard rule: context_map requires map/document asset type + evidence
            if editorial_role_str == "context_map":
                declared_type = visual_plan.get("primaryAssetType", "") if visual_plan else ""
                effective_type = _infer_effective_asset_type(c, declared_type)
                role_ev = semantic_ev.get("roleEvidence", [])

                c["declaredAssetType"] = declared_type
                c["effectiveAssetType"] = effective_type
                c["assetTypeValidationStatus"] = "FAIL"

                allowed_context_map_types = {"map", "historical_map", "document", "newspaper",
                                             "map_or_document", "historical_map_or_document"}
                if effective_type not in allowed_context_map_types:
                    continue  # reject: effective type is not a map/document
                if not role_ev:
                    continue  # reject: no context-map evidence in candidate metadata
                if asset_match == "unknown":
                    continue  # reject: map needs clear temporal match

                c["assetTypeValidationStatus"] = "PASS"

            # Hard rule: document_or_date requires map/document asset types
            if editorial_role_str == "document_or_date":
                declared_type = visual_plan.get("primaryAssetType", "") if visual_plan else ""
                effective_type = _infer_effective_asset_type(c, declared_type)
                role_ev = semantic_ev.get("roleEvidence", [])
                c["declaredAssetType"] = declared_type
                c["effectiveAssetType"] = effective_type
                c["assetTypeValidationStatus"] = "FAIL"
                allowed_doc = {"map", "historical_map", "document", "newspaper",
                               "map_or_document", "historical_map_or_document"}
                if effective_type not in allowed_doc:
                    continue
                if not role_ev:
                    title = (c.get("title") or "").strip()
                    desc = (c.get("description") or c.get("sourceDescription") or "").strip()
                    if not title and not desc:
                        continue
                c["assetTypeValidationStatus"] = "PASS"

            # Hard rule: event_depiction requires historical_event or archival_context
            if temporal_intent == "event_depiction" and asset_match in ("unknown", "modern_legacy"):
                continue  # reject: event depiction needs clear temporal provenance

            # Hard rule: consequence_or_legacy event_depiction requires either
            # sourceDepictedDateEvidence overlap with the target event year, or
            # explicit fall/opening subject evidence.
            if temporal_intent == "event_depiction" and editorial_role_str == "consequence_or_legacy":
                depicted = semantic_ev.get("sourceDepictedDateEvidence", [])
                fall_open = semantic_ev.get("fallOpeningSubjectEvidence", [])
                division_subj = semantic_ev.get("divisionSubjectEvidence", [])
                # Determine target event year from the scene's voiceover/period
                target_years: set[str] = set()
                cur_period = (visual_plan.get("period") or "") if visual_plan else ""
                target_years.update(t for t in cur_period.split() if t.isdigit() and len(t) == 4)
                cur_scene = scene or {}
                for tok in (cur_scene.get("voiceover") or "").split():
                    clean = tok.strip(".,;:!?()[]{}'\"")
                    if clean.isdigit() and len(clean) == 4:
                        target_years.add(clean)
                has_depicted_overlap = bool(target_years) and bool(set(depicted) & target_years)
                has_fall_subject = bool(fall_open)
                has_division_subject = bool(division_subj)
                if not (has_depicted_overlap or has_fall_subject):
                    continue  # reject: no direct depicted-date or fall/opening evidence
                if has_division_subject and not has_depicted_overlap and not has_fall_subject:
                    continue  # reject: division/family asset for distinct event

            # Hard rule: construction/battle scenes require direct visual evidence
            CONSTRUCTION_ROLES = {"battle_or_assault", "military_technology"}
            if editorial_role_str in CONSTRUCTION_ROLES:
                const_subj = semantic_ev.get("constructionSubjectEvidence", [])
                if not const_subj:
                    continue  # reject: no direct visual evidence of construction/barricade/battle

            # Hard rule: border closure/construction scenes require physical barrier evidence
            if editorial_role_str == "border_closure_construction":
                closure_subj = semantic_ev.get("borderClosureSubjectEvidence", [])
                c_title = (c.get("title") or "").lower()
                c_desc = (c.get("description") or c.get("sourceDescription") or "").lower()
                c_combined = f"{c_title} {c_desc}"
                c_combined_u = _unaccent(c_combined)
                reject = any(
                    _unaccent(ind) in c_combined_u or ind in c_combined
                    for ind in _BORDER_CLOSURE_REJECT_INDICATORS
                )
                if not closure_subj or reject:
                    continue  # reject: no direct evidence or wrong subject (family/checkpoint/commemoration)

            # Renderability pre-check: candidate must be renderable post-download
            renderability = _check_renderability(c, editorial_role_str)
            c["renderabilityStatus"] = renderability["status"]
            c["renderabilityReasons"] = renderability["reasons"]
            c["mapReadabilityScore"] = renderability["mapReadabilityScore"]
            if renderability["status"] == "FAIL":
                continue  # reject: candidate cannot pass render preflight

            valid_scored.append((s, reasons, c))

        if valid_scored:
            bs, breasons, bcandidate = valid_scored[0]
            if dest_exists:
                ok = True
                best_score = bs
            else:
                source_url = bcandidate.get("sourceUrl") or bcandidate.get("thumbnailUrl", "")
                if source_url:
                    _download_attempted = True
                    ok = download(source_url, dest)
                    if ok:
                        best_score = bs
                else:
                    ok = False

            if ok and (dest_exists or (dest.exists() and dest.stat().st_size > 1000)):
                selected_candidate = bcandidate
                selected_candidate["score"] = bs
                selected_candidate["scoreReasons"] = breasons
                selected_candidate["visualTemporalIntent"] = _classify_temporal_intent(scene or {})
                selected_candidate["assetTemporalMatch"] = _determine_asset_temporal_match(bcandidate, visual_plan or {}, scene)
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
        else:
            # No valid candidate passed filtering
            total_count = len(scored)
            filtered_reasons = []
            for s, _, c in scored:
                c_type = c.get("strategy", "")
                prov = c.get("provider", "")
                reject = []
                if s < 0:
                    reject.append("negative_score")
                if s < MIN_SCORE and s >= 0:
                    reject.append(f"score_{s}_below_min_{MIN_SCORE}")
                if prov == "pexels" and editorial_role_str in HARD_HISTORICAL_ROLES:
                    reject.append("pexels_not_allowed_for_hard_historical")
                c_w = c.get("width", 0) or 0
                c_h = c.get("height", 0) or 0
                if c_w > 10000 or c_h > 10000:
                    reject.append("decompression_bomb_risk")
                filtered_reasons.append(f"score={s} rejects={reject}")
            provider_failures.append({
                "provider": provider,
                "reason": f"all {total_count} candidates filtered out: {'; '.join(filtered_reasons[:3])}",
            })
            continue

    if not fallback_used and selected_candidate:
        fallback_used = provider_chain[0]
        fallback_reason = "primary provider succeeded"

    if not ok and not selected_candidate:
        _failure_classification = "download_failed" if _download_attempted else "resolution_exhausted"

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
        "failure_classification": _failure_classification,
    }


def resolve_queries_for_provider(
    provider: str,
    visual_plan: dict[str, Any] | None,
    strategy: str,
    visual_prompt: str,
    image_prompt: str,
) -> list[str]:
    if not visual_plan:
        result = visual_prompt or image_prompt
        return [result] if result else []

    if provider == "wikimedia_commons":
        qs = list(visual_plan.get("searchQueries", []))
        if visual_prompt:
            qs.append(visual_prompt[:200])
        return qs[:3]

    if provider in ("pexels", "pixabay"):
        qs = []
        for sq in visual_plan.get("searchQueries", [])[:3]:
            qs.append(sq[:200])
        if image_prompt:
            qs.append(image_prompt[:200])
        if visual_prompt:
            qs.append(visual_prompt[:200])
        return qs[:3]

    if provider == "freeai":
        gen_prompt = visual_plan.get("imageGenerationPrompt", "") or visual_prompt
        if gen_prompt:
            return [gen_prompt[:500]]
        result = visual_prompt
        return [result] if result else []

    if provider == "pollinations":
        result = visual_prompt or image_prompt
        return [result] if result else []

    result = visual_prompt or image_prompt
    return [result] if result else []


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
            ent_u = _unaccent(ent)
            title_u = _unaccent(title)
            query_u = _unaccent(query_used)
            # Check full entity and individual tokens
            ent_tokens = set(ent_u.split())
            all_text_u = f"{title_u} {query_u}"
            if (ent.lower() in title or ent.lower() in query_used or
                ent_u in title_u or ent_u in query_u or
                (len(ent_tokens) >= 1 and ent_tokens.intersection(all_text_u.split()))):
                score += SCORING_WEIGHTS["entity_match"]
                reasons.append(f"Entity match: {ent}")
                break

    if visual_plan:
        period = (visual_plan.get("period") or "").lower()
        location = (visual_plan.get("location") or "").lower()
        title_u = _unaccent(title)
        query_u = _unaccent(query_used)
        period_u = _unaccent(period)
        location_u = _unaccent(location)
        if period and (period in title or period in query_used or period_u in title_u or period_u in query_u):
            score += SCORING_WEIGHTS["period_or_location_match"]
            reasons.append(f"Period match: {period}")
        if location and (location in title or location in query_used or location_u in title_u or location_u in query_u):
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

    license_normalized = license_val.lower().replace("-", " ").replace("_", " ")
    CLEAR_LICENSE_PREFIXES = ("public domain", "cc0", "cc by", "cc by sa",
                              "pexels license", "pixabay license")
    is_clear = any(license_normalized.startswith(p) for p in CLEAR_LICENSE_PREFIXES)
    is_unknown = license_val in ("unknown", "") or not license_val
    if is_clear:
        score += SCORING_WEIGHTS["clear_license"]
        reasons.append(f"Clear license: {license_val}")
    elif is_unknown:
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
            if consecutive_scenes_with_same_type >= 2:
                score += SCORING_WEIGHTS.get("same_asset_type", -20)
                reasons.append(f"Same assetType as previous scene")

    return score, reasons


# Terms that identify a map/plan/diagram/division document vs ordinary photographs
_MAP_INDICATORS = [
    "map", "karte", "cartography", "cartografía", "atlas", "plan",
    "diagram", "diagrama",
    "occupation zones", "besatzungszonen",
    "sectors", "sektoren", "sector map",
    "division of", "divided city", "dividing line", "boundary",
    "annexation", "partition", "teilung",
    "four zones", "zone map",
]  # Generic map/division/sector indicators — no topic-specific locations
_DOCUMENT_INDICATORS = [
    "document", "dokument", "treaty", "vertrag", "newspaper",
    "zeitung", "decree", "dekret", "letter", "brief",
    "manuscript", "manuskript", "charter", "urkunde",
    "communiqué", "communique", "proclamation", "verkündung",
    "newsweek", "front page", "headline", "announcement",
]
_PHOTO_INDICATORS = [
    "photograph", "photography", "photo", "fotografie", "foto",
    "taken in", "image of the", "picture of", "view of",
    "aufgenommen", "blick auf", "ansicht",
    "this image", "this photo",
    "families separated", "separated by the wall", "separated families",
    "construction workers", "building the wall",
    "border guards", "checkpoint", "crossing the",
    "night view of", "front of the",
    "wasserturm", "restaurant", "hotel",
]  # Generic photo/description indicators — no topic-specific terms


def _infer_effective_asset_type(candidate: dict, declared_type: str) -> str:
    """Infer actual asset type from candidate title/URL metadata.

    When declaredAssetType is 'historical_map' but the candidate is an
    ordinary photograph, this function returns 'historical_photograph'.
    """
    title = (candidate.get("title") or "").lower()
    url = (candidate.get("sourceUrl") or "").lower()
    combined = f"{title} {url}"
    combined_u = _unaccent(combined)

    # Document/newspaper evidence (checked first: a document ABOUT a map is still a document)
    for ind in _DOCUMENT_INDICATORS:
        if _unaccent(ind) in combined_u or ind in combined:
            return "document"

    # Map/plan/diagram evidence
    for ind in _MAP_INDICATORS:
        if _unaccent(ind) in combined_u or ind in combined:
            return "historical_map"

    # Explicit photograph/photo evidence
    for ind in _PHOTO_INDICATORS:
        if _unaccent(ind) in combined_u or ind in combined:
            return "historical_photograph"

    return declared_type


# Terms that disqualify a map/document for context_map (blank templates, outline-only)
_BLANK_MAP_REJECT_TERMS = [
    "blank", "template", "outline only", "location map only",
    "for e.g. location maps", "unlabeled", "no labels",
    "blank map", "empty map", "placeholder",
]


def _check_renderability(candidate: dict, editorial_role: str = "") -> dict:
    """Shared renderability pre-check used by both fetch candidate filtering and render preflight.

    Returns {status: "PASS"|"FAIL", reasons: [...], mapReadabilityScore: float}
    A candidate that FAILS must never be selectable.
    """
    reasons: list[str] = []
    w = candidate.get("width", 0) or 0
    h = candidate.get("height", 0) or 0
    title = (candidate.get("title") or "").lower()
    combined = f"{title} {(candidate.get('sourceUrl') or '').lower()}"
    combined_u = _unaccent(combined)

    # Dimension check
    if w < RENDER_MIN_WIDTH and h < RENDER_MIN_HEIGHT:
        reasons.append(f"dimensions_too_small ({w}x{h} < {RENDER_MIN_WIDTH}x{RENDER_MIN_HEIGHT})")

    # Map readability for context_map
    map_readability = 0.0
    if editorial_role == "context_map":
        if w and h and w > h:
            map_readability = min(w / 1080, h / 1920) * (1 - abs(w / h - 9 / 16) / 2)
            map_readability = round(min(map_readability, 1.0), 2)
        if map_readability < MIN_MAP_READABILITY:
            reasons.append(f"map_readability_too_low ({map_readability:.2f} < {MIN_MAP_READABILITY})")

    # Blank/template rejection for context_map
    if editorial_role == "context_map":
        for term in _BLANK_MAP_REJECT_TERMS:
            if _unaccent(term) in combined_u or term in combined:
                reasons.append(f"blank_or_template_map (term='{term}')")
                break

    status = "PASS" if not reasons else "FAIL"
    return {
        "status": status,
        "reasons": reasons,
        "mapReadabilityScore": map_readability,
    }


# Rejection indicators for border_closure_construction: the image must not be
# primarily about family separation, commemorations, or generic checkpoints.
_BORDER_CLOSURE_REJECT_INDICATORS = [
    "families separated", "family separated", "family separation",
    "familientrennung", "separated by the wall", "separated families",
    "clinging hands", "farewell", "goodbye", "wedding", "bride", "groom",
    "commemoration", "commemorative", "anniversary", "celebration",
    "celebrating",
    "border crossing", "grenzübergang",
]  # Generic reject indicators — no topic-specific locations or names

# Direct subject indicators that the fall/opening of a wall/border is
# actually depicted in the image — required when target event year is 1989 and
# the candidate must show that event (not a retrospective/contextual mention).
_FALL_OPENING_SUBJECT_INDICATORS = [
    "fall of the wall", "fall of the",
    "wall opening",
    "people on the wall", "people atop the wall", "atop the",
    "crowd celebrating", "crowd on the", "celebrations at",
    "wall coming down", "wall being dismantled", "dismantling the wall",
    "border open", "border opening", "opening of the wall",
]  # Generic fall/demolition indicators — no topic-specific location names

# Subject indicators that the image is about family separation / 1961 border
# closure — used to reject reuse for distinct events (e.g. the 1989 fall).
_DIVISION_SUBJECT_INDICATORS = [
    "families separated", "family separated", "family separation",
    "separated by the wall", "separated families", "clinging hands",
    "farewell", "goodbye", "wedding", "bride", "groom",
    "construction of the wall", "barbed wire", "barricades",
]


_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_DASH_RANGE_RE = re.compile(r"\b(1[89]\d{2})\s*[-–—]\s*(1[89]\d{2}|20\d{2})\b")


def _classify_date_evidence(candidate: dict) -> tuple[list[str], list[str]]:
    """Split year mentions into depicted vs context-only.

    Heuristics:
      - A bare year embedded in the descriptive narrative (after a period or in
        a clause describing what the photo shows) is treated as depicted.
      - A year that is part of a dashed range (e.g. '1961 - 1989') or that
        appears in a retrospective title with a date range
        is treated as context-only.
      - Years appearing only in the URL are context-only unless the URL slug
        contains the year adjacent to depicted-subject keywords (weak signal,
        not used for depicted by default).
    """
    title = (candidate.get("title") or "")
    description = (candidate.get("description") or candidate.get("sourceDescription") or "")
    combined_for_range = f"{title} {description}"

    context_years: set[str] = set()
    depicted_years: set[str] = set()

    # 1. Dashed ranges → all years in the range are context-only.
    for m in _DASH_RANGE_RE.finditer(combined_for_range):
        start_y = int(m.group(1))
        end_y = int(m.group(2))
        if end_y < start_y:
            start_y, end_y = end_y, start_y
        for y in range(start_y, end_y + 1):
            context_years.add(str(y))

    # 2. Title-only year mentions where the title is a collection/retrospective
    #    phrase → context. Heuristic: title tokens '1961', '1989' adjacent to
    #    retrospective without depicting verbs.
    # A year may also appear in a depicting sentence elsewhere in the title; in
    # that case it must be classified as depicted (cannot short-circuit on
    # context_years from a range).
    title_lower = title.lower()
    retrospective_cues = [
        "1961 - 1989", "1961–1989", "1961—1989",
        "1961-1989",
        "a city torn apart", "booklet", "collection",
    ]  # Generic retrospective/collection indicator cues — no topic-specific terms
    # Collect all year matches in title; classify each by its window.
    title_year_matches = list(_YEAR_RE.finditer(title_lower))
    for m in title_year_matches:
        y = m.group(1)
        window_start = max(0, m.start() - 30)
        window_end = min(len(title_lower), m.end() + 30)
        window = title_lower[window_start:window_end]
        if any(cue in window for cue in retrospective_cues):
            context_years.add(y)
        else:
            # Not retrospective in this mention → depicts that year.
            depicted_years.add(y)

    # 3. Description sentence-level: a year that appears in a sentence whose
    #    subject is the depicted scene. We treat description years as depicted
    #    only when the sentence contains depicting verbs/subjects.
    if description:
        desc_lower = description.lower()
        # Description year: split by sentences and classify each mention.
        sentences = re.split(r'(?<=[.!?])\s+', desc_lower)
        depicting_cues = [
            "taken in", "photographed", "aufgenommen", "shows",
            "depicts", "depicts the", "in this photo", "this image",
            "this photo", "is seen", "celebrating", "people on",
            "atop",
            "wall coming down", "dismantling",
            "construction of the wall",
            "erecting", "building the wall", "barbed wire",
            "congratulate", "married", "marriage", "newly wed", "newlyweds",
            "from the window", "families separated", "family separated",
            "wedding", "on 8 september", "september 1961", "in 1961",
            "in 1989", "november 1989", "16. november", "on 16",
            "of the bride", "of the groom", "of a young",
            "smiles", "waving", "waved", "look on",
        ]  # Generic depiction cues — dates serve as anchors for any topic period
        context_cues = [
            "for more information", "booklet", "collection",
            "historical collections", "cia's historical",
            "from the booklet", "visit cia",
        ]
        for sent in sentences:
            for m in _YEAR_RE.finditer(sent):
                y = m.group(1)
                window = sent
                is_depicting = any(cue in window for cue in depicting_cues)
                is_context = any(cue in window for cue in context_cues)
                if is_depicting and not is_context:
                    depicted_years.add(y)
                elif is_context:
                    context_years.add(y)
                else:
                    # Ambiguous description sentence → treat as context only.
                    context_years.add(y)

    # 4. URLs: years in URLs are context-only (filenames rarely prove depiction).

    # 4. URLs: years in URLs are context-only (filenames rarely prove depiction).
    url = (candidate.get("sourceUrl") or "")
    for m in _YEAR_RE.finditer(url):
        context_years.add(m.group(1))

    # A year may appear in both sets if mentioned multiple ways (e.g. "1961"
    # is part of a retrospective range AND embedded in a depicting sentence).
    # A year is "depicted" if there is ANY explicit depiction cue for it, even
    # if it also appears in a range. A year is "context" if it only appears in
    # retrospective/range/title contexts. Keep the two sets independent; reuse
    # logic consults sourceDepictedDateEvidence as the authoritative signal.
    return sorted(depicted_years), sorted(context_years)


def _check_semantic_evidence(candidate: dict, scene: dict, topic: str) -> dict:
    """Evaluate semantic provenance of a candidate against the scene's historical context.
    
    Uses scene visualPlan metadata (location, period, entities) to build
    dynamic topic/location/period term lists instead of hardcoded terms.
    
    Returns a semanticEvidence dict with:
      topicTermsMatched, locationTermsMatched, periodTermsMatched,
      sourceTitle, sourceDescription, semanticConfidence.
    """
    title = (candidate.get("title") or "").lower()
    description = (candidate.get("description") or candidate.get("sourceDescription") or "").lower()
    combined = f"{title} {description}"
    combined_u = _unaccent(combined)
    source_url = (candidate.get("sourceUrl") or "").lower()

    # Build topic terms from scene context
    vp = scene.get("visualPlan") or {}
    topic_terms = set()
    topic_terms.add(topic.lower())
    for ent in vp.get("entities", []):
        topic_terms.add(ent.lower())
    for sq in vp.get("searchQueries", []):
        topic_terms.add(sq.lower())
    # Topic terms derived exclusively from scene metadata (no hardcoded topic vocabulary)

    # Location terms from scene visualPlan
    location_raw = vp.get("location", "")
    location_terms = set()
    if location_raw:
        location_terms.add(location_raw.lower())
        for part in location_raw.replace(",", " ").split():
            location_terms.add(part.lower())
    # Location terms derived exclusively from scene visualPlan.location (no hardcoded locations)

    # Period terms from scene visualPlan
    period_raw = vp.get("period", "")
    period_terms = set()
    if period_raw:
        period_terms.add(period_raw.lower())
        for part in period_raw.split():
            period_terms.add(part.lower())
    # Period terms derived exclusively from scene visualPlan.period (no hardcoded dates/periods)

    # Accent-insensitive matching
    def _matches(term: str, text: str, text_u: str) -> bool:
        return term in text or _unaccent(term) in text_u

    topic_matched = [t for t in topic_terms if _matches(t, combined, combined_u) or _matches(t, source_url, _unaccent(source_url))]
    location_matched = [t for t in location_terms if _matches(t, combined, combined_u) or _matches(t, source_url, _unaccent(source_url))]
    period_matched = [t for t in period_terms if _matches(t, combined, combined_u) or _matches(t, source_url, _unaccent(source_url))]

    # Generic-only check: reject if only generic words match
    generic_words = {"berlin", "berlín", "families", "familias", "history", "historia",
                     "wall", "muro", "germany", "alemania", "europe", "europa",
                     "cold", "war", "guerra", "fría", "fria", "post", "pos"}
    non_generic_matched = [
        t for t in (topic_matched + location_matched + period_matched)
        if t.lower() not in generic_words
    ]

    # Metadata-first: a candidate with null title and null description
    # cannot receive semanticConfidence above low.
    # When title AND description are both null/empty, confidence is always low
    # regardless of URL matches.
    has_title = bool(title)
    has_description = bool(description)

    if not has_title and not has_description:
        sem_conf = "low"
    elif has_title and len(non_generic_matched) >= 2:
        sem_conf = "high"
    elif has_title and len(non_generic_matched) >= 1:
        sem_conf = "medium"
    elif has_title and not non_generic_matched:
        sem_conf = "low"
    elif not has_title and has_description and len(non_generic_matched) >= 1:
        sem_conf = "medium"
    elif not has_title and has_description:
        sem_conf = "low"
    else:
        sem_conf = "low"

    # Role-specific evidence: match editorial role terms against candidate
    role_terms_by_role = {
        "context_map": ["map", "cartography", "zones", "divided", "division", "occupation",
                        "boundary", "sector",
                        "karte", "besatzungszonen", "sektoren", "teilung"],  # German generic: occupation zones, sectors, division
        "civilian_impact": ["family", "families", "familie", "civilian", "zivilist",
                           "refugee", "flüchtling", "escape", "flucht",
                           "border crossing", "grenzübergang", "checkpoint",
                           "separated", "getrennt", "farewell", "goodbye"],
        "battle_or_assault": ["construction", "bau", "building", "barbed wire", "stacheldraht",
                             "barricades", "barrikaden", "concrete", "beton",
                             "border guards", "grenzsoldaten", "soldiers", "military"],
        "border_closure_construction": ["barbed wire", "stacheldraht", "barricade", "barrikaden",
                                       "road block", "roadblock", "road blockade", "strassensperre",
                                       "border closure", "border closed", "grenzsperre",
                                       "abriegelung", "sperranlagen",
                                       "construction", "bau", "building", "erecting",
                                       "concrete barrier", "beton", "wall construction"],
        "consequence_or_legacy": ["fall", "opening", "öffnung", "celebration",
                                  "feier", "crowd", "menge", "wall coming down",
                                  "border open", "freedom", "freiheit", "1989"],
        "character_portrait": ["portrait", "porträt", "leader", "führer", "president",
                              "king", "queen", "general", "dictator"],
        "military_technology": ["tank", "panzer", "weapon", "waffe", "aircraft", "flugzeug",
                               "warship", "kriegsschiff", "artillery", "artillerie"],
        "document_or_date": ["document", "dokument", "treaty", "vertrag", "newspaper",
                            "zeitung", "decree", "dekret", "letter", "brief"],
    }
    editorial_role = vp.get("editorialRole", "")
    role_terms = role_terms_by_role.get(editorial_role, [])
    role_evidence = [t for t in role_terms if _matches(t, combined, combined_u)]

    # Boost semantic confidence for maps/documents with role evidence
    if editorial_role == "context_map" and role_evidence and sem_conf == "low":
        # A candidate with explicit map/document terms in its title warrants at least
        # medium confidence even if topic/period matches were only generic words.
        # e.g., occupation-zone maps with division/zones terms in title but generic location words
        sem_conf = "medium"

    # Asset type evidence
    asset_type = candidate.get("strategy", "")
    requested_type = vp.get("primaryAssetType", "")
    asset_type_evidence = [asset_type, requested_type] if asset_type and requested_type else [asset_type] if asset_type else []

    # Source/subject evidence: what the image directly depicts vs contextual reference
    _direct_visual_indicators = [
        "construction workers", "building the wall", "barbed wire", "barbed-wire",
        "barricade", "erecting", "border guards building", "road blockade",
        "workers building", "soldiers building", "concrete barrier",
        "pour concrete", "laying bricks", "digging trench",
        "separated families", "family separated", "goodbye",
        "farewell", "clinging hands", "crossing the border",
        "people atop", "crowd celebrating", "crowd on the",
        "celebrations at", "fall of the", "opening of the",
    ]  # Generic direct visual indicators — no topic-specific actions or names
    # Construction-specific subject indicators (narrower, for battle_or_assault role)
    _construction_subject_indicators = [
        "construction workers", "building the wall", "erecting barrier",
        "barbed wire installation", "barricade erection", "erecting",
        "digging trench", "pouring concrete", "laying bricks",
        "workmen building", "workers building", "soldiers building",
        "concrete barrier", "road blockade", "barbed wire",
    ]
    # Border-closure construction indicators (broader, for border_closure_construction role)
    _border_closure_subject_indicators = [
        "barbed wire", "barbed-wire", "stacheldraht",
        "barricade", "barricades", "barrikaden",
        "road block", "roadblock", "road blockade", "roadblockade",
        "strassensperre", "strassen sperre",
        "border closure", "border closed", "closure of the border",
        "grenzsperre", "grenze abgeriegelt",
        "abriegelung", "abriegelungen",
        "sperranlagen", "sperrzone",
        "construction workers", "building the wall", "erecting barrier",
        "erecting", "construction of the wall",
        "concrete barrier", "concrete wall", "wall construction",
        "wall segment", "border fortification",
    ]  # Generic border-closure indicators — no topic-specific German compound nouns
    _contextual_indicators = [
        "booklet about", "book about", "story of the", "history of the",
        "description of", "account of", "chronicle of", "cover of",
        "artist's book", "exhibition about", "museum display",
        "text about", "publication about",
    ]
    source_subject_evidence = [t for t in _direct_visual_indicators if _unaccent(t) in combined_u or t in combined]
    construction_subject_evidence = [t for t in _construction_subject_indicators if _unaccent(t) in combined_u or t in combined]
    border_closure_subject_evidence = [t for t in _border_closure_subject_indicators if _unaccent(t) in combined_u or t in combined]
    contextual_ref_evidence = [t for t in _contextual_indicators if _unaccent(t) in combined_u or t in combined]
    # Extract indirect indicators from title for contextual reference
    for t in role_evidence:
        if t not in source_subject_evidence and t not in contextual_ref_evidence:
            contextual_ref_evidence.append(t)

    # Date evidence: separate depicted dates from context/retrospective ranges.
    depicted_dates, context_dates = _classify_date_evidence(candidate)

    # Fall/opening subject evidence (for consequence_or_legacy with event 1989)
    fall_opening_evidence = [t for t in _FALL_OPENING_SUBJECT_INDICATORS
                             if _unaccent(t) in combined_u or t in combined]
    # Division/family-separation subject evidence (used to reject reuse for
    # distinct events like the 1989 fall).
    division_subject_evidence = [t for t in _DIVISION_SUBJECT_INDICATORS
                                 if _unaccent(t) in combined_u or t in combined]

    return {
        "topicTermsMatched": list(set(topic_matched)),
        "locationTermsMatched": list(set(location_matched)),
        "periodTermsMatched": list(set(period_matched)),
        "sourceTitle": candidate.get("title") or None,
        "sourceDescription": candidate.get("description") or candidate.get("sourceDescription") or None,
        "semanticConfidence": sem_conf,
        "roleEvidence": role_evidence,
        "assetTypeEvidence": asset_type_evidence,
        "sourceSubjectEvidence": source_subject_evidence,
        "constructionSubjectEvidence": construction_subject_evidence,
        "borderClosureSubjectEvidence": border_closure_subject_evidence,
        "fallOpeningSubjectEvidence": fall_opening_evidence,
        "divisionSubjectEvidence": division_subject_evidence,
        "sourceDepictedDateEvidence": depicted_dates,
        "sourceContextDateEvidence": context_dates,
        "contextualReferenceEvidence": contextual_ref_evidence,
    }


def score_editorial_role(asset_type: str, editorial_role: str | None,
                         temporal_intent: str | None = None) -> tuple[int, list[str]]:
    if not editorial_role:
        return 0, []
    prefs = EDITORIAL_ROLE_PREFERENCES.get(editorial_role, {})
    preferred = prefs.get("preferred", set())
    if not is_asset_type_allowed(editorial_role, asset_type, temporal_intent):
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
    "atmospheric_broll": ["city", "landscape", "architecture", "view", "scene", "atmosphere"],
    "document": ["document", "manuscript", "letter", "scroll"],
    "map": ["map", "atlas", "cartography"],
    "illustration": ["illustration", "drawing", "engraving", "miniature"],
    "painting": ["painting", "oil", "canvas", "fresco"],
}


def _try_hard_role_fallback(
    seg_query, visual_plan, strategy, scene_num, seg_dest, dest_exists,
    previous_entity_pool, args, pexels_key, pixabay_key, visual_prompt,
    image_prompt, anti_rep_context, scene, seg_at, dur_frac, seg,
    editorial_role, seg_idx,
):
    """Fallback for hard historical roles after Wikimedia exhaustion."""
    fb_providers = []
    if pexels_key: fb_providers.append("pexels")
    if pixabay_key: fb_providers.append("pixabay")
    if not fb_providers:
        return None
    fb_queries = [seg_query] if seg_query else []
    if visual_plan:
        for sq in visual_plan.get("searchQueries", []):
            if sq not in fb_queries:
                fb_queries.append(sq)
    all_cands = []
    for prov in fb_providers:
        for q in fb_queries[:4]:
            batch = search_pexels(q, pexels_key, args.max_candidates) if prov == "pexels" else search_pixabay(q, pixabay_key, args.max_candidates)
            for c in batch:
                c["strategy"] = strategy; c["provider"] = prov; c["queryUsed"] = q
            all_cands.extend(batch)
    if not all_cands:
        return None
    scored = []
    for c in all_cands:
        s, reasons = score_candidate(c, visual_plan, scene_num, previous_entity_pool, anti_rep_context)
        sem_ev = _check_semantic_evidence(c, scene or {}, "")
        c["semanticEvidence"] = sem_ev
        temporal_intent = _classify_temporal_intent(scene or {})
        c["visualTemporalIntent"] = temporal_intent
        c["assetTemporalMatch"] = _determine_asset_temporal_match(c, visual_plan or {}, scene)
        rend = _check_renderability(c, editorial_role)
        c["renderabilityStatus"] = rend["status"]
        c["renderabilityReasons"] = rend["reasons"]
        c["mapReadabilityScore"] = rend["mapReadabilityScore"]
        if s < 0:
            reasons.append("fb_reject: negative_score"); continue
        if sem_ev["semanticConfidence"] == "low":
            reasons.append("fb_reject: low_semantic"); continue
        if temporal_intent == "event_depiction" and c["assetTemporalMatch"] in ("modern_legacy", "unknown"):
            reasons.append(f"fb_reject: {c['assetTemporalMatch']}_for_event_depiction"); continue
        if editorial_role == "battle_or_assault" and not sem_ev.get("constructionSubjectEvidence"):
            reasons.append("fb_reject: no_construction_evidence"); continue
        if rend["status"] == "FAIL":
            reasons.append("fb_reject: render_fail"); continue
        tm = sem_ev.get("topicTermsMatched", [])
        lm = sem_ev.get("locationTermsMatched", [])
        if not tm and not lm:
            reasons.append("fb_reject: no_topic_or_location"); continue
        scored.append((s, reasons, c))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    bs, breasons, bc = scored[0]
    src = bc.get("sourceUrl") or bc.get("thumbnailUrl", "")
    if not src:
        return None
    fb_ok = dest_exists or (download(src, seg_dest) and seg_dest.exists() and seg_dest.stat().st_size > 1000)
    if not fb_ok:
        return None
    bc["score"] = bs; bc["scoreReasons"] = breasons
    bc["visualTemporalIntent"] = _classify_temporal_intent(scene or {})
    bc["assetTemporalMatch"] = _determine_asset_temporal_match(bc, visual_plan or {}, scene)
    seg_entry = {
        "segmentIndex": seg_idx, "path": str(seg_dest),
        "assetType": seg_at,
        "durationSec": round(scene["targetDurationSec"] * dur_frac, 1) if scene else 6.0,
        "transition": seg.get("transition", "cut"),
        "provider": bc.get("provider"), "sourceUrl": bc.get("sourceUrl"),
        "license": bc.get("license"), "author": bc.get("author"),
        "score": bs, "scoreReasons": breasons,
        "width": bc.get("width"), "height": bc.get("height"),
        "editorialReason": seg.get("editorialReason", ""),
        "downloadedAt": datetime.now(timezone.utc).isoformat(),
        "duplicateRisk": "none", "previousSimilarAssets": [],
        "reuseAllowed": False, "reuseReason": "",
        "focalRegion": seg.get("focalRegion", "center"),
        "cropMode": seg.get("cropMode", "full_map"),
        "overlayText": seg.get("overlayText", ""),
        "mapReadabilityScore": bc.get("mapReadabilityScore"),
        "visualAuthenticityRisk": None,
        "semanticEvidence": bc.get("semanticEvidence"),
        "visualTemporalIntent": bc.get("visualTemporalIntent"),
        "assetTemporalMatch": bc.get("assetTemporalMatch"),
        "declaredAssetType": bc.get("declaredAssetType"),
        "effectiveAssetType": bc.get("effectiveAssetType"),
        "assetTypeValidationStatus": bc.get("assetTypeValidationStatus"),
        "renderabilityStatus": bc.get("renderabilityStatus"),
        "renderabilityReasons": bc.get("renderabilityReasons"),
        "originalSceneNumber": None, "originalEditorialRole": None,
        "originalVisualTemporalIntent": None, "reuseCompatibilityReason": None,
        "provenanceType": "illustrative",
        "fallbackReason": f"Wikimedia returned no candidates for editorialRole={editorial_role}",
        "originalEditorialRole": editorial_role,
        "queryUsed": bc.get("queryUsed", seg_query) if seg_query else bc.get("queryUsed", ""),
    }
    er_s, er_r = score_editorial_role(seg_at, editorial_role,
                                        _classify_temporal_intent(scene or {}))
    if seg_entry["score"] is not None:
        seg_entry["score"] += er_s
    seg_entry["scoreReasons"] = (seg_entry.get("scoreReasons") or []) + er_r
    seg_entry["editorialScore"] = er_s
    seg_entry["editorialRole"] = editorial_role
    print(f"  scene {scene_num} seg {seg_idx}: FALLBACK ({bc.get('provider')}) score={bs} provenance=illustrative")
    return seg_entry


def build_historical_queries(
    visual_plan: dict[str, Any] | None,
    seg: dict[str, Any] | None,
    strategy: str,
    visual_prompt: str,
    image_prompt: str,
    scene: dict | None = None,
) -> list[str]:
    queries: list[str] = []
    if not visual_plan:
        result = visual_prompt or image_prompt
        return [result] if result else []

    entities = visual_plan.get("entities", [])
    period = visual_plan.get("period", "")
    location = visual_plan.get("location", "")
    asset_type = (seg.get("assetType") if seg else None) or visual_plan.get("primaryAssetType", "")
    event_query = (seg.get("searchQuery") if seg else None) or ""
    at_terms = ASSET_TYPE_QUERY_TERMS.get(asset_type, [asset_type.replace("_", " ")])

    # Level 0: segment searchQuery (most specific, use as-is for Wikimedia)
    if event_query and event_query not in queries:
        queries.append(event_query)

    # Level 1: scene searchQueries from visualPlan (broadest relevance)
    for sq in visual_plan.get("searchQueries", []):
        if sq not in queries:
            queries.append(sq)

    # Level 2: role-aware scene query variants (English + German for Wikimedia)
    if scene:
        scene_variants = _build_scene_query_variants(scene, visual_plan)
        for sv in scene_variants:
            if sv not in queries:
                queries.append(sv)

    # Level 3: entity + concrete asset type (highly specific)
    for ent in entities:
        for term in at_terms:
            q = f"{ent} {term}".strip()
            if q and q not in queries:
                queries.append(q)

    # Level 4: event/entity + period + location (contextual)
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
        base = context_parts[0]
        for extra in context_parts[1:]:
            q = f"{base} {extra}".strip()
            if q and q not in queries and len(q) < 150:
                queries.append(q)

    # Level 5: event + term
    if event_query:
        for term in at_terms:
            q = f"{event_query} {term}".strip()
            if q and q not in queries:
                queries.append(q)

    # Level 6: location/period + asset type (good when entities are empty)
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

    # Level 7: entity + documentary fallback
    for ent in entities:
        q = f"{ent} illustration".strip()
        if q and q not in queries:
            queries.append(q)

    # Level 8: generic prompt fallback
    if visual_prompt and visual_prompt not in queries:
        queries.append(visual_prompt[:200])
    if image_prompt and image_prompt not in queries:
        queries.append(image_prompt[:200])

    return queries[:16]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _get_source_role(asset_or_seg):
    """Return the canonical source editorial role from an asset envelope or segment."""
    return (asset_or_seg.get("sourceEditorialRole")
            or asset_or_seg.get("originalEditorialRole")
            or asset_or_seg.get("editorialRole", ""))


def _validate_segment_for_role(seg_at, editorial_role, candidate=None,
                               semantic_ev=None, temporal_intent=None, source_role=None,
                               visual_plan=None):
    """Authoritative shared validator for segment acceptance.

    Called from normal fetching, hard-role fallback, and reuse paths.
    Returns {ok, status, reasons, requestedAssetType, sceneEditorialRole,
             sourceEditorialRole, effectiveAssetType}.
    """
    reasons: list[str] = []
    role_prefs = EDITORIAL_ROLE_PREFERENCES.get(editorial_role, {})
    se = semantic_ev or (candidate or {}).get("semanticEvidence") or {}
    vp = visual_plan or {}

    # ── 1. Forbidden requested type (shared contract) ───────────────────
    if seg_at and not is_asset_type_allowed(editorial_role, seg_at, temporal_intent):
        return {"ok": False, "status": "REJECTED_FORBIDDEN_TYPE",
                "reasons": [f"requested={seg_at} forbidden for {editorial_role}"],
                "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                "sourceEditorialRole": source_role, "effectiveAssetType": None}

    # ── 2. Effective candidate type (shared contract) ───────────────────
    eff = None
    if candidate:
        declared = candidate.get("declaredAssetType") or vp.get("primaryAssetType", "")
        eff = candidate.get("effectiveAssetType") or _infer_effective_asset_type(candidate, declared)
        if eff and not is_asset_type_allowed(editorial_role, eff, temporal_intent):
            return {"ok": False, "status": "REJECTED_FORBIDDEN_EFFECTIVE_TYPE",
                    "reasons": [f"effective={eff} forbidden for {editorial_role}"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": eff}

    # ── 3. Event depiction temporal guard ────────────────────────────────
    atm = (candidate or {}).get("assetTemporalMatch", "")
    if temporal_intent == "event_depiction" and atm in ("unknown", "modern_legacy"):
        return {"ok": False, "status": "REJECTED_TEMPORAL_MATCH",
                "reasons": [f"event_depiction needs archival_context, got {atm}"],
                "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                "sourceEditorialRole": source_role, "effectiveAssetType": eff}

    # ── 4. context_map hard rule ─────────────────────────────────────────
    if editorial_role == "context_map":
        allowed_ct = {"map", "historical_map", "document", "newspaper",
                      "map_or_document", "historical_map_or_document"}
        ct_eff = eff or (vp.get("primaryAssetType", ""))
        if ct_eff not in allowed_ct:
            return {"ok": False, "status": "REJECTED_CONTEXT_MAP_TYPE",
                    "reasons": [f"context_map requires map/document, got {ct_eff}"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": ct_eff}
        role_ev = se.get("roleEvidence", [])
        if not role_ev:
            return {"ok": False, "status": "REJECTED_CONTEXT_MAP_EVIDENCE",
                    "reasons": ["context_map requires map/document roleEvidence"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": ct_eff}
        if atm == "unknown":
            return {"ok": False, "status": "REJECTED_CONTEXT_MAP_TEMPORAL",
                    "reasons": ["context_map requires clear temporal match"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": ct_eff}

    # ── 5. document_or_date hard rule ────────────────────────────────────
    if editorial_role == "document_or_date":
        allowed_doc = {"map", "historical_map", "document", "newspaper",
                       "map_or_document", "historical_map_or_document"}
        doc_eff = eff or (vp.get("primaryAssetType", ""))
        if doc_eff not in allowed_doc:
            return {"ok": False, "status": "REJECTED_DOCUMENT_TYPE",
                    "reasons": [f"document_or_date requires map/document, got {doc_eff}"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": doc_eff}
        role_ev = se.get("roleEvidence", [])
        cd_title = (candidate or {}).get("title", "") or ""
        cd_desc = (candidate or {}).get("description", "") or (candidate or {}).get("sourceDescription", "") or ""
        if not role_ev and not cd_title and not cd_desc:
            return {"ok": False, "status": "REJECTED_DOCUMENT_EVIDENCE",
                    "reasons": ["document_or_date requires title or description"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": doc_eff}

    # ── 6. consequence_or_legacy event_depiction date/fall check ─────────
    if temporal_intent == "event_depiction" and editorial_role == "consequence_or_legacy":
        depicted = se.get("sourceDepictedDateEvidence", [])
        fall_open = se.get("fallOpeningSubjectEvidence", [])
        division_subj = se.get("divisionSubjectEvidence", [])
        target_years = set()
        for tok in (vp.get("period", "") or "").split():
            if tok.isdigit() and len(tok) == 4:
                target_years.add(tok)
        if not target_years:
            period_raw = vp.get("period", "")
            for m in re.findall(r"\b(\d{4})\b", period_raw):
                target_years.add(m)
        has_overlap = bool(target_years) and bool(set(depicted) & target_years)
        if not (has_overlap or fall_open):
            return {"ok": False, "status": "REJECTED_CONSEQUENCE_EVENT",
                    "reasons": ["consequence_or_legacy event_depiction needs depicted-date overlap or fall/opening evidence"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": eff}
        if division_subj and not has_overlap and not fall_open:
            return {"ok": False, "status": "REJECTED_CONSEQUENCE_DIVISION",
                    "reasons": ["division/family asset incompatible with distinct event"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": eff}

    # ── 7. Construction / border-closure evidence ────────────────────────
    if editorial_role in ("battle_or_assault", "military_technology", "border_closure_construction"):
        cbj = se.get("constructionSubjectEvidence", [])
        bsj = se.get("borderClosureSubjectEvidence", [])
        if editorial_role == "border_closure_construction":
            if not bsj:
                return {"ok": False, "status": "REJECTED_CONSTRUCTION_EVIDENCE",
                        "reasons": ["border_closure_construction requires border evidence"],
                        "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                        "sourceEditorialRole": source_role, "effectiveAssetType": eff}
            c_title = (candidate or {}).get("title", "") or ""
            c_desc = (candidate or {}).get("description", "") or (candidate or {}).get("sourceDescription", "") or ""
            c_combined = f"{c_title} {c_desc}"
            c_combined_u = _unaccent(c_combined)
            reject_border = any(
                _unaccent(ind) in c_combined_u or ind in c_combined
                for ind in _BORDER_CLOSURE_REJECT_INDICATORS
            )
            if reject_border:
                return {"ok": False, "status": "REJECTED_BORDER_CLOSURE_SUBJECT",
                        "reasons": ["border_closure_construction rejected: family/checkpoint/commemoration subject"],
                        "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                        "sourceEditorialRole": source_role, "effectiveAssetType": eff}
        elif not cbj:
            return {"ok": False, "status": "REJECTED_CONSTRUCTION_EVIDENCE",
                    "reasons": [f"{editorial_role} requires constructionEvidence"],
                    "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                    "sourceEditorialRole": source_role, "effectiveAssetType": eff}

    # ── 8. Renderability ─────────────────────────────────────────────────
    rend = (candidate or {}).get("renderabilityStatus", "")
    if rend == "FAIL":
        return {"ok": False, "status": "REJECTED_RENDERABILITY",
                "reasons": (candidate or {}).get("renderabilityReasons", ["renderability failed"]),
                "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                "sourceEditorialRole": source_role, "effectiveAssetType": eff}

    # ── 9. Semantic confidence floor ─────────────────────────────────────
    sem_conf = se.get("semanticConfidence", "low")
    if sem_conf == "low" and editorial_role in HARD_HISTORICAL_ROLES:
        return {"ok": False, "status": "REJECTED_LOW_CONFIDENCE",
                "reasons": [f"hard historical role {editorial_role} requires medium+ confidence"],
                "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
                "sourceEditorialRole": source_role, "effectiveAssetType": eff}

    return {"ok": True, "status": "PASS", "reasons": [],
            "requestedAssetType": seg_at, "sceneEditorialRole": editorial_role,
            "sourceEditorialRole": source_role,
            "effectiveAssetType": eff}

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
    previous_valid_asset = None
    for scene in scenes:
        scene_num = int(scene["sceneNumber"])
        visual_plan = scene.get("visualPlan")
        visual_prompt = scene.get("visualPrompt", "")
        image_prompt = scene.get("imagePrompt", "")
        is_last_scene = (scene_num == scenes[-1]["sceneNumber"])

        if visual_plan:
            strategy = visual_plan.get("strategy", "historical_archive")
            provider_chain = STRATEGY_CHAINS.get(strategy, STRATEGY_CHAINS["historical_archive"])
        else:
            strategy = "legacy"
            provider_chain = ["pollinations"]
            visual_prompt = visual_prompt or image_prompt or ""
            image_prompt = ""

        editorial_role = visual_plan.get("editorialRole") if visual_plan else None

        # Reuse previous valid asset for CTA (last scene) or consequence_or_legacy
        # Only reuse when semantic evidence matches the new scene's temporal intent.
        should_reuse = False
        if is_last_scene and previous_valid_asset is not None:
            should_reuse = True
        elif editorial_role == "consequence_or_legacy" and previous_valid_asset is not None:
            should_reuse = True

        if should_reuse:
            reuse_temporal_intent = _classify_temporal_intent(scene)
            prev_asset_match = previous_valid_asset.get("assetTemporalMatch", "")
            if reuse_temporal_intent == "event_depiction" and prev_asset_match in ("modern_legacy", "unknown"):
                should_reuse = False
                print(f"  scene {scene_num}: reuse BLOCKED (event_depiction cannot reuse {prev_asset_match} asset)")

        if should_reuse:
            src_role = _get_source_role(previous_valid_asset)
            dst_role = editorial_role or ""
            BLOCKED_REUSE = {"context_map", "document_or_date"}
            if src_role in BLOCKED_REUSE and dst_role in ("consequence_or_legacy",):
                should_reuse = False
                print(f"  scene {scene_num}: reuse BLOCKED (src={src_role} incompatible with dst={dst_role})")
            if should_reuse:
                for pseg in previous_valid_asset.get("segments") or []:
                    if not is_asset_type_allowed(dst_role, pseg.get("assetType", ""), reuse_temporal_intent):
                        should_reuse = False
                        print(f"  scene {scene_num}: reuse BLOCKED (seg type={pseg.get('assetType')} forbidden for {dst_role})")
                        break

        if should_reuse:
            reuse_temporal_intent = _classify_temporal_intent(scene)
            dst_role = editorial_role or ""

            # ── Shared validator for reused segments ─────────────────────
            reuse_validation_failed = False
            reuse_validation_reasons: list[str] = []
            for pseg in (previous_valid_asset.get("segments") or []):
                pseg_at = pseg.get("assetType", "")
                pseg_se = pseg.get("semanticEvidence", {})
                src_r = _get_source_role(previous_valid_asset)
                rsv = _validate_segment_for_role(
                    pseg_at, dst_role,
                    candidate=pseg,
                    semantic_ev=pseg_se,
                    temporal_intent=reuse_temporal_intent,
                    source_role=src_r,
                    visual_plan=visual_plan)
                if not rsv["ok"]:
                    reuse_validation_failed = True
                    reuse_validation_reasons.append(
                        f"seg {pseg.get('segmentIndex', '?')}: {rsv['status']}")
            if reuse_validation_failed:
                should_reuse = False
                print(f"  scene {scene_num}: reuse BLOCKED by validator ({' / '.join(reuse_validation_reasons[:3])})")

        if should_reuse:
            reuse_temporal_intent = _classify_temporal_intent(scene)
            asset_meta = dict(previous_valid_asset)
            asset_meta["sceneNumber"] = scene_num
            asset_meta["reuseReason"] = "reuse_previous_valid_asset"
            asset_meta["visualTemporalIntent"] = reuse_temporal_intent

            # Check reuse compatibility for event_depiction scenes
            reuse_blocked = False
            reuse_block_reason = ""
            if reuse_temporal_intent == "event_depiction":
                prev_se = None
                if "segments" in asset_meta and asset_meta["segments"]:
                    prev_se = asset_meta["segments"][0].get("semanticEvidence", {})
                # Use sourceDepictedDateEvidence (preferred) over periodTermsMatched
                # because title ranges like "1961 - 1989" pollute periodTermsMatched.
                prev_depicted_years = set()
                if prev_se:
                    for term in prev_se.get("sourceDepictedDateEvidence", []):
                        if term.isdigit() and len(term) == 4:
                            prev_depicted_years.add(term)
                    # Fallback to periodTermsMatched only if depicted is empty
                    if not prev_depicted_years:
                        for term in prev_se.get("periodTermsMatched", []):
                            if term.isdigit() and len(term) == 4:
                                # Exclude years known to be context-only
                                ctx = set(prev_se.get("sourceContextDateEvidence", []))
                                if term not in ctx:
                                    prev_depicted_years.add(term)
                # Get the current scene's period year
                current_period = (visual_plan.get("period") or "").lower()
                current_years = {t for t in current_period.split() if t.isdigit() and len(t) == 4}
                # Also extract years from voiceover (e.g. "1989" in "El Muro cayó en 1989")
                scene_vo = (scene.get("voiceover") or "")
                for token in scene_vo.split():
                    clean = token.strip(".,;:!?()[]{}'\"")
                    if clean.isdigit() and len(clean) == 4:
                        current_years.add(clean)
                # Reuse requires overlap of depicted years with target event years.
                if current_years and prev_depicted_years and not current_years.intersection(prev_depicted_years):
                    reuse_blocked = True
                    reuse_block_reason = (f"depicted-date mismatch: asset depicted {prev_depicted_years}, "
                                           f"scene needs {current_years}")
                    print(f"  scene {scene_num}: reuse BLOCKED ({reuse_block_reason})")
                # Reject reuse where original editorial role is civilian_impact and the
                # target narration is a distinct event (e.g. the fall in 1989).
                orig_role_check = _get_source_role(previous_valid_asset)
                if orig_role_check == "civilian_impact" and current_years and prev_depicted_years and not current_years.intersection(prev_depicted_years):
                    reuse_blocked = True
                    reuse_block_reason = (f"civilian_impact asset cannot depict distinct event "
                                           f"(asset={prev_depicted_years}, target={current_years})")
                    print(f"  scene {scene_num}: reuse BLOCKED ({reuse_block_reason})")
                # Subject compatibility: division/family asset cannot be reused for fall/opening.
                if prev_se:
                    division_subj = prev_se.get("divisionSubjectEvidence", [])
                    fall_open = prev_se.get("fallOpeningSubjectEvidence", [])
                    if division_subj and not fall_open and current_years and prev_depicted_years and not current_years.intersection(prev_depicted_years):
                        reuse_blocked = True
                        reuse_block_reason = (f"division/family subject incompatible with target event "
                                               f"(division={division_subj[:2]})")
                        print(f"  scene {scene_num}: reuse BLOCKED ({reuse_block_reason})")

            if reuse_blocked:
                should_reuse = False
            else:
                # Re-evaluate temporal match in current scene's context
                current_match = _determine_asset_temporal_match(previous_valid_asset, visual_plan or {}, scene)
                asset_meta["assetTemporalMatch"] = current_match
                # Build reuse compatibility reason citing specific evidence
                prev_se_reason = None
                if asset_meta.get("segments"):
                    prev_se_reason = asset_meta["segments"][0].get("semanticEvidence", {})
                reuse_compat_parts = []
                if reuse_temporal_intent == "event_depiction":
                    depicted = (prev_se_reason or {}).get("sourceDepictedDateEvidence", [])
                    fall_open = (prev_se_reason or {}).get("fallOpeningSubjectEvidence", [])
                    if depicted:
                        reuse_compat_parts.append(f"sourceDepictedDateEvidence={depicted} overlaps target event")
                    if fall_open:
                        reuse_compat_parts.append(f"fallOpeningSubjectEvidence={fall_open[:2]}")
                elif reuse_temporal_intent == "legacy_or_commemoration":
                    orig_role_reason = _get_source_role(previous_valid_asset)
                    if orig_role_reason == "civilian_impact":
                        reuse_compat_parts.append("human legacy of division (divided families)")
                    else:
                        reuse_compat_parts.append(f"reused archival asset suitable for commemoration context (origRole={orig_role_reason})")
                reuse_compat_parts.append("visual consistency across consecutive scenes")
                reuse_compatibility_reason = "; ".join(reuse_compat_parts)

                # Track original provenance
                orig_scene = previous_valid_asset.get("originalSceneNumber") or previous_valid_asset.get("sceneNumber")
                orig_role = _get_source_role(previous_valid_asset)
                orig_vti = previous_valid_asset.get("originalVisualTemporalIntent") or previous_valid_asset.get("visualTemporalIntent")

                asset_meta["originalSceneNumber"] = orig_scene
                asset_meta["originalEditorialRole"] = orig_role
                asset_meta["originalVisualTemporalIntent"] = orig_vti
                asset_meta["reuseCompatibilityReason"] = reuse_compatibility_reason

                # Deep-copy segments and update with reuse metadata + original provenance
                if "segments" in asset_meta:
                    asset_meta["segments"] = [dict(seg) for seg in asset_meta["segments"]]
                    for seg in asset_meta["segments"]:
                        seg["reuseReason"] = "reuse_previous_valid_asset"
                        seg["reuseCompatibilityReason"] = reuse_compatibility_reason
                        seg["editorialReason"] = "reused from previous scene for visual consistency"
                        seg["visualTemporalIntent"] = reuse_temporal_intent
                        seg["assetTemporalMatch"] = current_match
                        seg["originalSceneNumber"] = orig_scene
                        seg["originalEditorialRole"] = orig_role
                        seg["originalVisualTemporalIntent"] = orig_vti
                asset_meta["selected"] = True
                asset_meta["error"] = None
                results.append(asset_meta)
                print(f"  scene {scene_num}: REUSE previous valid asset (role={editorial_role})"
                      f" original=scene-{orig_scene} compat={reuse_compatibility_reason[:60]}")
                time.sleep(SCENE_PAUSE_SEC)
                previous_valid_asset = asset_meta
                continue

        visual_sequence = visual_plan.get("visualSequence") if visual_plan else None

        if visual_sequence:
            segments = []
            segment_results = []
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

                # Build historical queries for hard historical roles or event_depiction scenes
                is_event_depiction = scene and _classify_temporal_intent(scene) == "event_depiction"
                if editorial_role in HARD_HISTORICAL_ROLES or is_event_depiction:
                    hist_queries = build_historical_queries(visual_plan, seg, strategy, visual_prompt, image_prompt, scene=scene)
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
                    topic=data.get("topic", ""),
                    scene=scene,
                )

                cand = result["selected_candidate"]
                dur_frac = seg.get("durationFraction", 1.0 / len(visual_sequence))
                editorial_role = visual_plan.get("editorialRole") if visual_plan else None

                def _build_seg_entry(c, ok_flag, path_override=None):
                    p = path_override or str(seg_dest)
                    return {
                        "segmentIndex": seg_idx,
                        "path": p if ok_flag else None,
                        "assetType": seg_at,
                        "durationSec": round(scene["targetDurationSec"] * dur_frac, 1),
                        "transition": seg.get("transition", "cut"),
                        "provider": c.get("provider") if c else None,
                        "sourceUrl": c.get("sourceUrl") if c else None,
                        "license": c.get("license") if c else None,
                        "author": c.get("author") if c else None,
                        "score": c.get("score") if c else None,
                        "scoreReasons": c.get("scoreReasons") if c else None,
                        "width": c.get("width") if c else None,
                        "height": c.get("height") if c else None,
                        "editorialReason": seg.get("editorialReason", ""),
                        "downloadedAt": datetime.now(timezone.utc).isoformat() if ok_flag else None,
                        "duplicateRisk": "none",
                        "previousSimilarAssets": [],
                        "reuseAllowed": False,
                        "reuseReason": "",
                        "focalRegion": seg.get("focalRegion", "center"),
                        "cropMode": seg.get("cropMode", "full_map"),
                        "overlayText": seg.get("overlayText", ""),
                        "mapReadabilityScore": c.get("mapReadabilityScore") if c else None,
                        "visualAuthenticityRisk": None,
                        "semanticEvidence": c.get("semanticEvidence") if c else None,
                        "visualTemporalIntent": c.get("visualTemporalIntent") if c else None,
                        "assetTemporalMatch": c.get("assetTemporalMatch") if c else None,
                        "declaredAssetType": c.get("declaredAssetType") if c else None,
                        "effectiveAssetType": c.get("effectiveAssetType") if c else None,
                        "assetTypeValidationStatus": c.get("assetTypeValidationStatus") if c else None,
                        "renderabilityStatus": c.get("renderabilityStatus") if c else None,
                        "renderabilityReasons": c.get("renderabilityReasons") if c else None,
                        "originalSceneNumber": None,
                        "originalEditorialRole": None,
                        "originalVisualTemporalIntent": None,
                        "reuseCompatibilityReason": None,
                    }

                seg_entry = _build_seg_entry(cand, result["ok"])

                # ── Shared validator ─────────────────────────────────────
                segment_accepted = False
                if result["ok"] and cand:
                    temporal_intent = _classify_temporal_intent(scene)
                    sv = _validate_segment_for_role(
                        seg_at, editorial_role, candidate=cand,
                        temporal_intent=temporal_intent,
                        source_role=editorial_role, visual_plan=visual_plan)
                    seg_entry["segmentValidationStatus"] = sv["status"]
                    seg_entry["segmentValidationReasons"] = sv["reasons"]
                    seg_entry["requestedAssetType"] = sv["requestedAssetType"]
                    seg_entry["sceneEditorialRole"] = sv["sceneEditorialRole"]
                    seg_entry["sourceEditorialRole"] = sv["sourceEditorialRole"]
                    seg_entry["effectiveAssetType"] = sv.get("effectiveAssetType")
                    if sv["ok"]:
                        segment_accepted = True
                    else:
                        seg_entry["error"] = f"Validation rejected: {sv['status']}"
                        seg_entry["path"] = None
                        print(f"  scene {scene_num} seg {seg_idx}: REJECTED ({sv['status']})")

                # ── Hard-role fallback ────────────────────────────────────
                if (not segment_accepted
                        and editorial_role in HARD_HISTORICAL_ROLES
                        and result.get("failure_classification") == "resolution_exhausted"):
                    fb_entry = _try_hard_role_fallback(
                        seg_query=seg_query,
                        visual_plan=visual_plan,
                        strategy=strategy,
                        scene_num=scene_num,
                        seg_dest=seg_dest,
                        dest_exists=seg_exists,
                        previous_entity_pool=previous_entity_pool,
                        args=args,
                        pexels_key=pexels_key,
                        pixabay_key=pixabay_key,
                        visual_prompt=visual_prompt,
                        image_prompt=image_prompt,
                        anti_rep_context=anti_rep_context,
                        scene=scene,
                        seg_at=seg_at,
                        dur_frac=dur_frac,
                        seg=seg,
                        editorial_role=editorial_role,
                        seg_idx=seg_idx,
                    )
                    if fb_entry is not None:
                        # Build candidate-like dict for validator
                        fb_cand = {
                            "provider": fb_entry.get("provider"),
                            "sourceUrl": fb_entry.get("sourceUrl"),
                            "title": "",
                            "description": "",
                            "width": fb_entry.get("width"),
                            "height": fb_entry.get("height"),
                            "score": fb_entry.get("score"),
                            "scoreReasons": fb_entry.get("scoreReasons"),
                            "semanticEvidence": fb_entry.get("semanticEvidence"),
                            "visualTemporalIntent": fb_entry.get("visualTemporalIntent"),
                            "assetTemporalMatch": fb_entry.get("assetTemporalMatch"),
                            "declaredAssetType": fb_entry.get("declaredAssetType"),
                            "effectiveAssetType": fb_entry.get("effectiveAssetType"),
                            "assetTypeValidationStatus": fb_entry.get("assetTypeValidationStatus"),
                            "renderabilityStatus": fb_entry.get("renderabilityStatus"),
                            "renderabilityReasons": fb_entry.get("renderabilityReasons"),
                            "mapReadabilityScore": fb_entry.get("mapReadabilityScore"),
                        }
                        temporal_intent = _classify_temporal_intent(scene)
                        fsv = _validate_segment_for_role(
                            seg_at, editorial_role, candidate=fb_cand,
                            temporal_intent=temporal_intent,
                            source_role=editorial_role, visual_plan=visual_plan)
                        if fsv["ok"]:
                            fb_entry["segmentValidationStatus"] = fsv["status"]
                            fb_entry["segmentValidationReasons"] = fsv["reasons"]
                            fb_entry["requestedAssetType"] = fsv["requestedAssetType"]
                            fb_entry["sceneEditorialRole"] = fsv["sceneEditorialRole"]
                            fb_entry["sourceEditorialRole"] = fsv["sourceEditorialRole"]
                            fb_entry["effectiveAssetType"] = fsv.get("effectiveAssetType")
                            seg_entry = fb_entry
                            segment_accepted = True
                        else:
                            seg_entry["error"] = f"Fallback rejected: {fsv['status']}"
                            seg_entry["path"] = None
                            print(f"  scene {scene_num} seg {seg_idx}: fallback REJECTED ({fsv['status']})")

                if not segment_accepted and editorial_role in HARD_HISTORICAL_ROLES and result.get("provider_attempt_order") == ["wikimedia_commons"]:
                    seg_entry["error"] = seg_entry.get("error") or "ASSET_UNRESOLVED"
                    print(f"  scene {scene_num} seg {seg_idx}: ASSET_UNRESOLVED ({seg_query[:50]})")
                elif not segment_accepted and not result["ok"]:
                    seg_entry["error"] = seg_entry.get("error") or "Download failed"
                    print(f"  scene {scene_num} seg {seg_idx}: FAILED ({seg_query[:50]})")

                if segment_accepted:
                    segment_results.append(True)

                    # ── Canonical accepted candidate ──────────────────
                    is_fallback = seg_entry.get("provenanceType") == "illustrative"
                    if is_fallback:
                        accepted_candidate = {
                            "sourceUrl": seg_entry.get("sourceUrl") or "",
                            "author": seg_entry.get("author") or "",
                            "provider": seg_entry.get("provider") or "",
                            "queryUsed": seg_entry.get("queryUsed") or seg_query or "",
                        }
                    else:
                        accepted_candidate = cand if cand else {}

                    source_url = (accepted_candidate.get("sourceUrl") or "").rstrip("/")
                    if source_url:
                        used_urls.add(source_url)
                    author = (accepted_candidate.get("author") or "").strip()
                    provider = accepted_candidate.get("provider", "")
                    author_key = f"{provider}|{author}" if author and provider else ""
                    if author_key:
                        used_authors[author_key] = scene_num
                    q_used = (accepted_candidate.get("queryUsed") or "").lower().strip()
                    if q_used:
                        used_queries.append((scene_num, q_used))
                    if seg_at:
                        used_asset_types.append(seg_at)
                    actual_provider = seg_entry.get("provider", accepted_candidate.get("provider", "?"))
                    actual_score = seg_entry.get("score", accepted_candidate.get("score", "?"))
                    print(f"  scene {scene_num} seg {seg_idx}: OK ({actual_provider}) score={actual_score}")
                else:
                    segment_results.append(False)
                    seg_entry["segmentValidationStatus"] = seg_entry.get("segmentValidationStatus", "REJECTED")
                    seg_entry["segmentValidationReasons"] = seg_entry.get("segmentValidationReasons", [str(seg_entry.get("error", "unknown failure"))])

                # Editorial role scoring (on accepted segments)
                if editorial_role and segment_accepted:
                    er_score, er_reasons = score_editorial_role(seg_at, editorial_role,
                                                                _classify_temporal_intent(scene))
                    if seg_entry["score"] is not None:
                        seg_entry["score"] = seg_entry["score"] + er_score
                    seg_entry["scoreReasons"] = (seg_entry.get("scoreReasons") or []) + er_reasons
                    seg_entry["editorialScore"] = er_score
                    seg_entry["editorialRole"] = editorial_role

                # Map readability for map-type assets
                if seg_at in ("historical_map", "map", "document"):
                    w = seg_entry.get("width", 0) or 0
                    h = seg_entry.get("height", 0) or 0
                    if w and h and w > h:
                        readability = min(w / 1080, h / 1920) * (1 - abs(w / h - 9 / 16) / 2)
                        seg_entry["mapReadabilityScore"] = round(min(readability, 1.0), 2)

                segments.append(seg_entry)
                time.sleep(SCENE_PAUSE_SEC)

            ok = all(segment_results)
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
                "title": (first_seg.get("semanticEvidence") or {}).get("sourceTitle"),
                "description": (first_seg.get("semanticEvidence") or {}).get("sourceDescription"),
                "author": first_seg.get("author"),
                "license": first_seg.get("license"),
                "score": first_seg.get("score"),
                "scoreReasons": first_seg.get("scoreReasons"),
                "downloadedAt": first_seg.get("downloadedAt"),
                "error": None if ok else "Some segments failed",
                "visualTemporalIntent": first_seg.get("visualTemporalIntent"),
                "assetTemporalMatch": first_seg.get("assetTemporalMatch"),
                "declaredAssetType": first_seg.get("declaredAssetType"),
                "effectiveAssetType": first_seg.get("effectiveAssetType"),
                "assetTypeValidationStatus": first_seg.get("assetTypeValidationStatus"),
                "renderabilityStatus": first_seg.get("renderabilityStatus"),
                "renderabilityReasons": first_seg.get("renderabilityReasons"),
                "mapReadabilityScore": first_seg.get("mapReadabilityScore"),
                "semanticEvidence": first_seg.get("semanticEvidence"),
                "originalSceneNumber": None,
                "originalEditorialRole": None,
                "originalVisualTemporalIntent": None,
                "editorialRole": visual_plan.get("editorialRole"),
                "sourceEditorialRole": visual_plan.get("editorialRole"),
                "reuseCompatibilityReason": None,
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
                topic=data.get("topic", ""),
                scene=scene,
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
                "semanticEvidence": selected_candidate.get("semanticEvidence") if selected_candidate else None,
                "visualTemporalIntent": _classify_temporal_intent(scene),
                "assetTemporalMatch": selected_candidate.get("assetTemporalMatch") if selected_candidate else None,
                "declaredAssetType": selected_candidate.get("declaredAssetType") if selected_candidate else None,
                "effectiveAssetType": selected_candidate.get("effectiveAssetType") if selected_candidate else None,
                "assetTypeValidationStatus": selected_candidate.get("assetTypeValidationStatus") if selected_candidate else None,
                "renderabilityStatus": selected_candidate.get("renderabilityStatus") if selected_candidate else None,
                "renderabilityReasons": selected_candidate.get("renderabilityReasons") if selected_candidate else None,
                "mapReadabilityScore": selected_candidate.get("mapReadabilityScore") if selected_candidate else None,
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
        if asset_meta.get("selected") and asset_meta.get("error") is None:
            previous_valid_asset = asset_meta
        time.sleep(SCENE_PAUSE_SEC)

    data["assets"] = results
    data["updatedAt"] = datetime.now(timezone.utc).isoformat()

    has_asset_unresolved = any(
        seg.get("error") == "ASSET_UNRESOLVED"
        for r in results
        if r.get("segments")
        for seg in r["segments"]
    ) or any(
        r.get("error") == "ASSET_UNRESOLVED"
        for r in results
    )
    all_ok = all(r.get("selected", False) for r in results) and not has_asset_unresolved
    data["status"] = "ASSETS_READY" if all_ok else ("ASSET_UNRESOLVED" if has_asset_unresolved else "ASSETS_PARTIAL")
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    print(json.dumps({"jobId": job_id, "success": all_ok}))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
