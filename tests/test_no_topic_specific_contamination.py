"""Regression tests for topic-specific sourcing contamination.

Verifies that no Berlin, Constantinople, Istanbul, or other topic-specific
hardcoded vocabulary remains in reusable production source files.

Run: python3 -m pytest tests/test_no_topic_specific_contamination.py -v
"""

import inspect
import re
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))


# ── Prohibited topic-specific terms in production source ─────────────────

PROHIBITED_TERMS = [
    # Berlin-specific
    "berlin wall", "berliner mauer", "muro de berlín", "muro de berlin",
    "berliner mauer bau", "mauerbau",
    "sectors of berlin", "east berlin west berlin", "berlin sectors",
    "zones of berlin", "berlin zones",
    "fall of the berlin wall", "fall of the berlin",
    "juggling on the berlin wall", "atop the berlin wall",
    "checkpoint charlie",
    "berlin wall in",
    # Constantinople/Istanbul-specific
    "la caída de constantinopla",
    # Broader matches that should not appear as standalone terms in production lists
    # (individual numbers like 1961, 1989 may appear as token matches in generic code
    #  — we test that they're not in hardcoded literal term lists below)
]

# Production files to scan (exclude tests, docs, sessions, sample data)
PRODUCTION_FILES = [
    PROJECT / "bin" / "fetch_images.py",
    PROJECT / "bin" / "asset_validation.py",
    PROJECT / "bin" / "editorial_asset_contract.py",
]


def _source_lines(filepath: Path) -> list[tuple[int, str]]:
    lines = filepath.read_text().splitlines()
    return [(i + 1, line) for i, line in enumerate(lines)]


def _is_test_or_doc(filepath: Path) -> bool:
    return ("tests/" in str(filepath) or
            "docs/" in str(filepath) or
            "openspec/" in str(filepath) or
            "data/" in str(filepath))


# ── Source-level regression test ─────────────────────────────────────────


def test_no_prohibited_terms_in_bin_fetch_images_source():
    """bin/fetch_images.py must not contain prohibited topic-specific terms
    in production-level string literals or term lists."""
    content = (PROJECT / "bin" / "fetch_images.py").read_text()
    for term in PROHIBITED_TERMS:
        count = len(re.findall(re.escape(term), content, re.IGNORECASE))
        assert count == 0, (
            f"PROHIBITED: '{term}' found {count} time(s) in bin/fetch_images.py"
        )


def test_no_prohibited_terms_in_bin_asset_validation_source():
    """bin/asset_validation.py must not contain prohibited topic-specific terms
    in production-level term lists."""
    content = (PROJECT / "bin" / "asset_validation.py").read_text()
    for term in PROHIBITED_TERMS:
        count = len(re.findall(re.escape(term), content, re.IGNORECASE))
        assert count == 0, (
            f"PROHIBITED: '{term}' found {count} time(s) in bin/asset_validation.py"
        )


# ── Photosynthesis fixture: must not emit Berlin/Cold War/1961/1989 ─────


def test_photosynthesis_queries_no_berlin_contamination():
    """A photosynthesis scene must derive queries from its own metadata,
    never emitting Berlin, Mauer, 1961, 1989, Cold War, Constantinople."""
    from fetch_images import _build_scene_query_variants

    scene = {
        "voiceover": "La fotosíntesis convierte la luz solar en energía química en las hojas.",
        "visualPlan": {
            "editorialRole": "context_map",
            "period": "moderna",
            "location": "laboratorio virtual",
            "entities": ["fotosíntesis", "cloroplasto", "hoja"],
            "primaryAssetType": "document",
            "searchQueries": ["photosynthesis diagram", "chloroplast structure"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": "document", "searchQuery": "photosynthesis diagram plant leaf"}
            ],
        },
    }
    vp = scene["visualPlan"]

    queries = _build_scene_query_variants(scene, vp)
    all_text = " ".join(queries).lower()

    prohibited = ["berlin", "mauer", "1961", "1989", "cold war",
                  "constantinople", "istanbul", "guerra fría",
                  "caída del muro"]
    for term in prohibited:
        assert term not in all_text, (
            f"Photosynthesis query contains prohibited term '{term}': {all_text[:200]}"
        )

    # Must contain topic-derived terms
    assert any("photosynthesis" in q.lower() for q in queries) or \
           any("fotosíntesis" in q.lower() for q in queries) or \
           any("cloroplasto" in q.lower() for q in queries) or \
           any("chloroplast" in q.lower() for q in queries), \
        f"Photosynthesis scene queries must contain topic-derived terms: {queries[:5]}"


def test_photosynthesis_semantic_evidence_no_artificial_boost():
    """_check_semantic_evidence must not inject Berlin/ColdWar terms
    for a photosynthesis topic."""
    from fetch_images import _check_semantic_evidence

    candidate = {
        "title": "Diagram of photosynthesis in plant leaves",
        "description": "Chloroplast structure showing light and dark reactions",
        "sourceUrl": "https://example.com/photosynthesis.jpg",
    }
    scene = {
        "voiceover": "La fotosíntesis convierte luz en energía.",
        "visualPlan": {
            "editorialRole": "context_map",
            "period": "moderna",
            "location": "laboratorio virtual",
            "entities": ["fotosíntesis", "cloroplasto"],
            "primaryAssetType": "document",
            "searchQueries": ["photosynthesis diagram"],
        },
    }
    se = _check_semantic_evidence(candidate, scene, "Fotosíntesis")

    # Topic terms must come from scene metadata, not hardcoded Berlin/Cold War
    all_topic = " ".join(se.get("topicTermsMatched", [])).lower()
    all_period = " ".join(se.get("periodTermsMatched", [])).lower()
    all_location = " ".join(se.get("locationTermsMatched", [])).lower()

    prohibited = {"berlin", "mauer", "1961", "1989", "cold war",
                  "constantinople", "istanbul", "guerra fría",
                  "caída del muro", "fall of the wall"}
    for term in prohibited:
        assert term not in all_topic, f"'topicTermsMatched' contains prohibited '{term}'"
        assert term not in all_period, f"'periodTermsMatched' contains prohibited '{term}'"
        assert term not in all_location, f"'locationTermsMatched' contains prohibited '{term}'"


# ── French Revolution fixture: derives terms from its own metadata ───────


def test_french_revolution_queries_from_own_entities():
    """La Revolución Francesa scene must derive queries from Bastilla, París, 1789,
    never emitting Berlin/Wall/ColdWar terms."""
    from fetch_images import _build_scene_query_variants

    scene = {
        "voiceover": "El 14 de julio de 1789, el pueblo de París tomó la Bastilla.",
        "visualPlan": {
            "editorialRole": "battle_or_assault",
            "period": "1789",
            "location": "París",
            "entities": ["Bastilla", "Revolución Francesa", "París"],
            "primaryAssetType": "historical_photograph",
            "searchQueries": ["Storming of the Bastille 1789", "Prise de la Bastille"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": "historical_photograph",
                 "searchQuery": "Storming of the Bastille July 1789"}
            ],
        },
    }
    vp = scene["visualPlan"]

    queries = _build_scene_query_variants(scene, vp)
    all_text = " ".join(queries).lower()

    # Must NOT contain Berlin contamination
    prohibited = ["berlin", "mauer", "1961", "1989", "cold war",
                  "constantinople", "istanbul", "guerra fría",
                  "caída del muro"]
    for term in prohibited:
        assert term not in all_text, (
            f"French Revolution query contains prohibited term '{term}': {all_text[:200]}"
        )

    # Must contain topic-derived terms
    assert any(x in all_text for x in ["bastille", "bastilla", "1789", "parís", "paris"]), \
        f"French Revolution queries must contain topic-derived terms: {queries[:5]}"


def test_french_revolution_semantic_evidence_from_metadata():
    """_check_semantic_evidence must derive period=1789 and location=París from
    scene metadata for La Revolución Francesa, without hardcoded Berlin terms."""
    from fetch_images import _check_semantic_evidence

    candidate = {
        "title": "Prise de la Bastille, 14 juillet 1789",
        "description": "Painting of the storming of the Bastille in Paris",
        "sourceUrl": "https://example.com/bastille.jpg",
    }
    scene = {
        "voiceover": "El 14 de julio de 1789, el pueblo de París tomó la Bastilla.",
        "visualPlan": {
            "editorialRole": "battle_or_assault",
            "period": "1789",
            "location": "París",
            "entities": ["Bastilla", "Revolución Francesa", "París"],
            "primaryAssetType": "historical_photograph",
            "searchQueries": ["Storming of the Bastille 1789"],
        },
    }
    se = _check_semantic_evidence(candidate, scene, "Revolución Francesa")

    all_topic = " ".join(se.get("topicTermsMatched", [])).lower()
    all_period = " ".join(se.get("periodTermsMatched", [])).lower()
    all_location = " ".join(se.get("locationTermsMatched", [])).lower()

    prohibited = {"berlin", "mauer", "1961", "1989", "cold war",
                  "constantinople", "istanbul", "guerra fría",
                  "caída del muro", "fall of the wall"}
    for term in prohibited:
        assert term not in all_topic, f"'topicTermsMatched' contains prohibited '{term}'"
        assert term not in all_period, f"'periodTermsMatched' contains prohibited '{term}'"
        assert term not in all_location, f"'locationTermsMatched' contains prohibited '{term}'"

    # Must contain scene-derived terms
    assert any(x in all_topic for x in ["revolución francesa", "revolucion francesa",
                                        "revolución", "revolucion",
                                        "bastilla", "parís", "paris"]), \
        f"Topic terms must contain scene-derived terms: {all_topic}"


# ── Berlin fixture still works from its own metadata ─────────────────────


def test_berlin_fixture_queries_from_its_own_metadata():
    """A Berlin Wall scene with 'Muro de Berlín' entity and 'Berlín' location
    must still derive Berlin queries from its own metadata (not from hardcoded lists)."""
    from fetch_images import _build_scene_query_variants

    scene = {
        "voiceover": "El Muro de Berlín cayó en 1989.",
        "visualPlan": {
            "editorialRole": "consequence_or_legacy",
            "period": "1989",
            "location": "Berlín",
            "entities": ["Muro de Berlín", "1989"],
            "primaryAssetType": "historical_photograph",
            "searchQueries": ["Berlin Wall fall 1989"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": "historical_photograph",
                 "searchQuery": "Berlin Wall 1989 fall"}
            ],
        },
    }
    vp = scene["visualPlan"]

    queries = _build_scene_query_variants(scene, vp)
    all_text = " ".join(queries).lower()

    # Must contain Berlin terms from metadata
    assert any(x in all_text for x in ["berlin", "berlín", "1989", "muro de berlín"]), \
        f"Berlin scene queries should contain Berlin terms from metadata: {queries[:5]}"

    # Must NOT contain hardcoded German templates like "Berliner Mauer"
    # (since we removed those from production code)
    assert "berliner mauer karte" not in all_text, \
        "Hardcoded German template 'Berliner Mauer Karte' should not appear"
    assert "mauerbau berlin" not in all_text, \
        "Hardcoded German template 'Mauerbau Berlin' should not appear"


# ── Neutral-core query generation tests ──────────────────────────────────
# Historical domain vocabulary must not be injected into provider queries
# unless scene metadata explicitly requests or contains it.
# Editorial roles used in fixtures are compatibility requirements;
# they are not presented as generic product vocabulary.

_HISTORICAL_DEFAULT_TERMS = [
    "medieval", "castle", "fortress", "siege", "battle",
    "ancient", "old ruins", "cathedral", "vintage war",
    "historical scene", "historical photograph",
    "old historical", "old map historical", "ancient manuscript",
    "old fortress", "medieval castle", "historical siege",
    "battlefield", "medieval armor", "old cannon",
    "ancient city", "historical reconstruction",
    "medieval fortress", "historical reconstruction",
]


def _collect_all_queries(scene: dict, vp: dict) -> set[str]:
    """Collect query variants from all provider-type paths."""
    from fetch_images import (_build_scene_query_variants,
                              resolve_queries_for_provider)
    queries: set[str] = set()

    sv = _build_scene_query_variants(scene, vp)
    for q in sv:
        if q:
            queries.add(q.lower())

    for provider in ("wikimedia_commons", "pexels", "pixabay", "freeai",
                     "pollinations", "unknown"):
        pq = resolve_queries_for_provider(
            provider, vp, vp.get("strategy", "historical_archive"),
            scene.get("visualPrompt", ""), scene.get("imagePrompt", ""),
        )
        for q in pq:
            if q:
                queries.add(q.lower())

    return queries


def _no_historical_defaults_in(queries: set[str],
                                scene_name: str = "unknown") -> None:
    """Assert no historical default vocabulary appears in any query."""
    all_text = " ".join(sorted(queries))
    for term in _HISTORICAL_DEFAULT_TERMS:
        assert term not in all_text, (
            f"{scene_name} query contains historical default "
            f"'{term}': {all_text[:200]}"
        )


def test_photosynthesis_queries_no_historical_defaults():
    """Photosynthesis: queries from scene/topic metadata only;
    no medieval/castle/war/battle terms."""
    from fetch_images import _build_scene_query_variants

    scene = {
        "voiceover": "La fotosíntesis convierte la luz solar en energía química en las hojas.",
        "visualPrompt": "diagram of photosynthesis process in plant leaf",
        "imagePrompt": "plant leaf chloroplast diagram",
        "visualPlan": {
            "editorialRole": "context_map",  # compatibility fixture
            "period": "moderna",
            "location": "",
            "entities": ["fotosíntesis", "cloroplasto", "hoja"],
            "primaryAssetType": "document",
            "strategy": "map_or_document",
            "searchQueries": ["photosynthesis diagram", "chloroplast structure"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": "document",
                 "searchQuery": "photosynthesis diagram plant leaf"}
            ],
        },
    }
    vp = scene["visualPlan"]

    queries = _build_scene_query_variants(scene, vp)
    all_text = " ".join(queries).lower()

    prohibited = ["berlin", "mauer", "1961", "1989", "cold war",
                  "constantinople", "istanbul", "guerra fría",
                  "caída del muro"]
    for term in prohibited:
        assert term not in all_text, (
            f"Photosynthesis query contains prohibited '{term}': {all_text[:200]}"
        )

    assert any("photosynthesis" in q.lower() for q in queries) or \
           any("fotosíntesis" in q.lower() for q in queries) or \
           any("cloroplasto" in q.lower() for q in queries) or \
           any("chloroplast" in q.lower() for q in queries), \
        f"Photosynthesis scene queries must contain topic-derived terms: {queries[:5]}"

    all_queries = _collect_all_queries(scene, vp)
    _no_historical_defaults_in(all_queries, "Photosynthesis")


def test_technology_queries_no_historical_defaults():
    """Technology topic (blockchain): queries from metadata only;
    no historical/medieval/war/battle defaults.

    editorialRole='document_or_date' is a compatibility fixture;
    it is not presented as generic product vocabulary.
    """
    scene = {
        "voiceover": "Blockchain technology enables decentralized trust.",
        "visualPrompt": "distributed ledger network diagram",
        "imagePrompt": "blockchain transaction chain blocks",
        "visualPlan": {
            "editorialRole": "document_or_date",  # compatibility fixture
            "period": "",
            "location": "",
            "entities": ["blockchain", "distributed ledger", "transaction"],
            "primaryAssetType": "document",
            "strategy": "map_or_document",
            "searchQueries": ["blockchain diagram", "distributed ledger network"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": "document",
                 "searchQuery": "how blockchain works diagram"}
            ],
        },
    }
    vp = scene["visualPlan"]

    all_queries = _collect_all_queries(scene, vp)
    _no_historical_defaults_in(all_queries, "Blockchain")

    all_text = " ".join(sorted(all_queries))
    tech_terms = ["blockchain", "ledger", "transaction", "network", "diagram"]
    found = [t for t in tech_terms if t in all_text]
    assert len(found) >= 2, (
        f"Blockchain queries must contain technology terms "
        f"(found: {found}); all queries: {all_text[:200]}"
    )


def test_animals_queries_no_historical_defaults():
    """Animals topic (octopus): queries from metadata only;
    no historical/medieval/war/battle defaults.

    editorialRole='document_or_date' is a compatibility fixture;
    it is not presented as generic product vocabulary.
    """
    scene = {
        "voiceover": "Octopuses change color using chromatophores in their skin.",
        "visualPrompt": "octopus camouflaged on ocean floor",
        "imagePrompt": "cephalopod color change diagram",
        "visualPlan": {
            "editorialRole": "document_or_date",  # compatibility fixture
            "period": "",
            "location": "ocean",
            "entities": ["octopus", "camouflage", "chromatophore"],
            "primaryAssetType": "document",
            "strategy": "map_or_document",
            "searchQueries": ["octopus camouflage skin", "cephalopod color change"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": "document",
                 "searchQuery": "octopus chromatophore diagram"}
            ],
        },
    }
    vp = scene["visualPlan"]

    all_queries = _collect_all_queries(scene, vp)
    _no_historical_defaults_in(all_queries, "Octopus")

    all_text = " ".join(sorted(all_queries))
    animal_terms = ["octopus", "camouflage", "cephalopod",
                    "chromatophore", "skin", "ocean"]
    found = [t for t in animal_terms if t in all_text]
    assert len(found) >= 2, (
        f"Octopus queries must contain animal/topic terms "
        f"(found: {found}); all queries: {all_text[:200]}"
    )


def test_historical_event_queries_only_metadata_derived():
    """Historical event (French Revolution): historical terms appear ONLY
    because metadata explicitly contains them; no injected
    medieval/castle/fortress defaults beyond metadata."""
    from fetch_images import (_build_scene_query_variants,
                              resolve_queries_for_provider)
    import fetch_images as fi

    scene = {
        "voiceover": "El 14 de julio de 1789, el pueblo de París tomó la Bastilla.",
        "visualPrompt": "painting of the storming of the Bastille Paris 1789",
        "imagePrompt": "French Revolution Bastille",
        "visualPlan": {
            "editorialRole": "battle_or_assault",
            "period": "1789",
            "location": "París",
            "entities": ["Bastilla", "Revolución Francesa", "París"],
            "primaryAssetType": "historical_photograph",
            "strategy": "historical_archive",
            "searchQueries": ["Storming of the Bastille 1789",
                            "Prise de la Bastille"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": "historical_photograph",
                 "searchQuery": "Storming of the Bastille July 1789"}
            ],
        },
    }
    vp = scene["visualPlan"]

    queries = _build_scene_query_variants(scene, vp)
    all_text = " ".join(queries).lower()

    prohibited = ["berlin", "mauer", "1961", "1989", "cold war",
                  "constantinople", "istanbul", "guerra fría",
                  "caída del muro"]
    for term in prohibited:
        assert term not in all_text, (
            f"French Revolution query contains prohibited '{term}': {all_text[:200]}"
        )

    assert any(x in all_text for x in ["bastille", "bastilla",
               "1789", "parís", "paris"]), \
        f"French Revolution queries must contain topic-derived terms: {queries[:5]}"

    # Must NOT inject medieval/castle/fortress defaults
    injected = ["medieval", "castle fortress", "old fortress",
                "medieval castle", "ancient city"]
    for term in injected:
        assert term not in all_text, (
            f"French Revolution query injects non-metadata default "
            f"'{term}': {all_text[:200]}"
        )

    # resolve_queries_for_provider for pexels/pixabay must derive only
    # from metadata searchQueries (no injected templates)
    vp_clean = dict(vp)
    pq = resolve_queries_for_provider(
        "pexels", vp_clean, "historical_archive",
        scene.get("visualPrompt", ""), scene.get("imagePrompt", ""),
    )
    pq_text = " ".join(pq).lower()
    for term in injected:
        assert term not in pq_text, (
            f"resolve_queries_for_provider pexels injects "
            f"'{term}': {pq_text[:200]}"
        )


def test_weak_metadata_no_historical_fallback():
    """When visualPlan is empty and no prompts are available,
    resolve_queries_for_provider returns [] for all provider types.
    It never emits 'historical scene', strategy names, or genre words."""
    from fetch_images import resolve_queries_for_provider

    providers = ["wikimedia_commons", "pexels", "pixabay", "freeai",
                 "pollinations", "unknown"]

    for prov in providers:
        queries = resolve_queries_for_provider(prov, {}, "", "", "")
        assert queries == [], (
            f"Expected [] for provider={prov} with empty metadata, got {queries}"
        )

    # With visualPlan present but empty searchQueries and no prompts
    for prov in providers:
        queries = resolve_queries_for_provider(
            prov, {"searchQueries": []}, "", "", "",
        )
        assert queries == [], (
            f"Expected [] for provider={prov} with empty searchQueries, got {queries}"
        )

    # Never emit "historical scene" or strategy-name fallback
    for prov in providers:
        for vp in ({}, {"searchQueries": []}):
            queries = resolve_queries_for_provider(prov, vp, "any_strategy", "", "")
            all_text = " ".join(queries).lower()
            assert "historical scene" not in all_text, (
                f"Provider {prov} emitted 'historical scene' with weak metadata"
            )
            assert "any_strategy" not in all_text, (
                f"Provider {prov} used strategy name as query text"
            )
            for genre in ("medieval", "castle", "fortress", "war", "ancient"):
                assert genre not in all_text, (
                    f"Provider {prov} emitted genre word '{genre}' with weak metadata"
                )


def test_query_generation_functions_no_hidden_historical_defaults():
    """Source-level scan of query-generation and fallback functions:
    no hardcoded historical/medieval/war/battle/archive fallback strings,
    no strategy-name-as-query patterns in global/no-role-gate paths.

    Scope: resolve_queries_for_provider, _resolve_query_for_segment,
    build_historical_queries, the Pollinations branch in _fetch_one_asset.
    """
    import fetch_images as fi

    # ── 1. resolve_queries_for_provider (global, no role gating) ──────
    src1 = inspect.getsource(fi.resolve_queries_for_provider)
    assert 'historical scene' not in src1.lower(), \
        "resolve_queries_for_provider must not contain 'historical scene'"
    assert 'f"historical' not in src1, \
        "resolve_queries_for_provider must not contain f'historical' pattern"
    # Strategy name must never be interpolated into a query string.
    # Verify no f-string pattern like f'historical {strategy}...' remains.
    strategy_injection = re.findall(r'f".*\{strategy\}', src1)
    assert len(strategy_injection) == 0, (
        f"resolve_queries_for_provider interpolates strategy name "
        f"into query: {strategy_injection}"
    )
    # Same for strategy.replace
    strategy_replace = re.findall(r'f".*strategy\.replace', src1)
    assert len(strategy_replace) == 0, (
        f"resolve_queries_for_provider uses strategy.replace in query string"
    )

    # ── 2. _resolve_query_for_segment (global, no role gating) ────────
    src2 = inspect.getsource(fi._resolve_query_for_segment)
    assert 'historical scene' not in src2.lower(), \
        "_resolve_query_for_segment must not contain 'historical scene'"
    # With empty templates, this function returns [sq] cleanly for pexels/pixabay
    strategy_inj2 = re.findall(r'f".*\{strategy\}', src2)
    assert len(strategy_inj2) == 0, (
        f"_resolve_query_for_segment interpolates strategy name: {strategy_inj2}"
    )

    # ── 3. build_historical_queries (role-gated but check fallback) ───
    src3 = inspect.getsource(fi.build_historical_queries)
    assert 'historical scene' not in src3.lower(), \
        "build_historical_queries must not contain 'historical scene'"
    assert 'f"historical' not in src3, \
        "build_historical_queries must not contain f'historical' query pattern"

    # ── 4. Pollinations branch in _fetch_one_asset ─────────────────────
    src4 = inspect.getsource(fi._fetch_one_asset)
    # The Pollinations fallback line must not inject 'historical'
    poll_lines = [l for l in src4.split('\n') if 'pollinations' in l.lower()]
    for line in poll_lines:
        if 'historical' in line.lower() and '#' not in line[:line.find('historical')]:
            assert 'historical' not in line.lower() or 'poll_prompt' not in line, (
                f"Pollinations branch contains 'historical' injection: {line.strip()[:120]}"
            )

    # ── 5. STRATEGY_VISUAL_QUERIES all empty ───────────────────────────
    svq = fi.STRATEGY_VISUAL_QUERIES
    for strategy_name, templates in svq.items():
        assert templates == [], (
            f"STRATEGY_VISUAL_QUERIES['{strategy_name}'] is not empty: {templates}"
        )


# ── Generic indicators still topic-agnostic ───────────────────────────────


def test_generic_border_closure_indicators_are_topic_agnostic():
    """Generic border-closure indicators (barbed wire, barricades, etc.)
    apply to any border/fortification, not just Berlin."""
    from fetch_images import _BORDER_CLOSURE_REJECT_INDICATORS
    # All indicators must be generic — no "Checkpoint Charlie", no Berlin-specific names
    for ind in _BORDER_CLOSURE_REJECT_INDICATORS:
        assert "berlin" not in ind.lower(), \
            f"_BORDER_CLOSURE_REJECT_INDICATORS contains Berlin-specific term: '{ind}'"
        assert "charlie" not in ind.lower(), \
            f"_BORDER_CLOSURE_REJECT_INDICATORS contains location-specific term: '{ind}'"


def test_generic_fall_opening_indicators_are_topic_agnostic():
    """Fall/opening indicators must describe generic wall demolition, not Berlin-specific."""
    from fetch_images import _FALL_OPENING_SUBJECT_INDICATORS
    for ind in _FALL_OPENING_SUBJECT_INDICATORS:
        assert "berlin" not in ind.lower(), \
            f"_FALL_OPENING_SUBJECT_INDICATORS contains Berlin-specific term: '{ind}'"
        assert "juggling" not in ind.lower(), \
            f"_FALL_OPENING_SUBJECT_INDICATORS contains photo-specific term: '{ind}'"


def test_generic_map_indicators_are_topic_agnostic():
    """Map indicators must describe generic cartography, not Berlin sectors."""
    from fetch_images import _MAP_INDICATORS
    for ind in _MAP_INDICATORS:
        assert "berlin" not in ind.lower(), \
            f"_MAP_INDICATORS contains Berlin-specific term: '{ind}'"


def test_generic_photo_indicators_are_topic_agnostic():
    """Photo indicators must describe generic photographic evidence, not Berlin-specific."""
    from fetch_images import _PHOTO_INDICATORS
    for ind in _PHOTO_INDICATORS:
        assert "berlin" not in ind.lower(), \
            f"_PHOTO_INDICATORS contains Berlin-specific term: '{ind}'"


# ── No theme constraints remain in asset_validation ──────────────────────


def test_theme_constraints_empty():
    """THEME_CONSTRAINTS must be empty — no hardcoded themes."""
    from asset_validation import THEME_CONSTRAINTS
    assert len(THEME_CONSTRAINTS) == 0, (
        f"THEME_CONSTRAINTS must be empty, got: {list(THEME_CONSTRAINTS.keys())}"
    )


def test_legacy_keywords_no_topic_specific():
    """LEGACY_KEYWORDS must not contain Istanbul/Estambul."""
    from asset_validation import LEGACY_KEYWORDS
    assert "estambul" not in LEGACY_KEYWORDS and "Estambul" not in LEGACY_KEYWORDS, \
        f"LEGACY_KEYWORDS contains Istanbul-specific term"
    assert "istanbul" not in LEGACY_KEYWORDS, \
        f"LEGACY_KEYWORDS contains istanbul"


def test_modern_query_keywords_no_topic_specific():
    """MODERN_QUERY_KEYWORDS must not contain Istanbul/Estambul."""
    from asset_validation import MODERN_QUERY_KEYWORDS
    for kw in MODERN_QUERY_KEYWORDS:
        assert kw.lower() not in ("istanbul", "estambul"), \
            f"MODERN_QUERY_KEYWORDS contains Istanbul-specific term: '{kw}'"


# ── No hardcoded German Berlin query templates ───────────────────────────


def test_build_scene_query_variants_no_german_loc_hardcode():
    """_build_scene_query_variants source must not contain 'german_loc = \"Berlin\"'."""
    import fetch_images as fi
    src = inspect.getsource(fi._build_scene_query_variants)
    assert 'german_loc' not in src, (
        "_build_scene_query_variants must not hardcode german_loc"
    )
    assert 'german_terms' not in src, (
        "_build_scene_query_variants must not contain hardcoded german_terms dict"
    )
    assert 'Berliner Mauer' not in src, (
        "_build_scene_query_variants must not contain Berliner Mauer template"
    )


def test_period_equivalents_no_fall_of_berlin_wall():
    """period_equivalents must not map any period to 'fall of the berlin wall'."""
    import fetch_images as fi
    src = inspect.getsource(fi._determine_asset_temporal_match)
    assert 'fall of the berlin wall' not in src.lower(), (
        "period_equivalents must not contain 'fall of the berlin wall'"
    )


def test_location_equivalents_no_berlin_entries():
    """location_equivalents must not contain Berlin-specific entries."""
    import fetch_images as fi
    src = inspect.getsource(fi._determine_asset_temporal_match)
    assert 'berlín' not in src.lower().replace('location', ''), (
        "location_equivalents must not contain hardcoded Berlin entries"
    )


def test_entity_equivalents_no_muro_de_berlin():
    """entity_equivalents must not contain 'muro de berlín' or 'berlin wall'."""
    import fetch_images as fi
    src = inspect.getsource(fi._determine_asset_temporal_match)
    assert 'muro de berlín' not in src.lower(), (
        "entity_equivalents must not contain 'muro de berlín'"
    )
    assert 'berlin wall' not in src.lower(), (
        "entity_equivalents must not contain 'berlin wall'"
    )


def test_semantic_evidence_no_hardcoded_topic_terms_update():
    """_check_semantic_evidence source must not contain hardcoded
    topic_terms.update with Berlin/Cold War terms."""
    import fetch_images as fi
    src = inspect.getsource(fi._check_semantic_evidence)
    assert 'berlin wall' not in src.lower(), \
        "_check_semantic_evidence must not hardcode 'berlin wall' in topic_terms"
    assert 'berliner mauer' not in src.lower(), \
        "_check_semantic_evidence must not hardcode 'berliner mauer'"
    assert 'caída del muro' not in src.lower(), \
        "_check_semantic_evidence must not hardcode 'caída del muro'"


def test_retrospective_cues_no_berlin_entries():
    """_classify_date_evidence retrospective_cues must not contain Berlin-specific cues."""
    import fetch_images as fi
    src = inspect.getsource(fi._classify_date_evidence)
    assert 'the berlin wall' not in src.lower(), \
        "retrospective_cues must not contain 'the berlin wall'"
    assert 'berliner mauer' not in src.lower(), \
        "retrospective_cues must not contain 'berliner mauer'"
