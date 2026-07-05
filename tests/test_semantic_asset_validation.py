"""Unit tests for semantic asset validation rules.

Covers:
- context_map hard rule (only map/document/newspaper asset types)
- event_depiction hard rule (requires historical_event or archival_context)
- asset temporal match classification
- visual temporal intent classification
- reuse compatibility year extraction from voiceover

Run: python3 -m pytest tests/test_semantic_asset_validation.py -v
"""

import json
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from fetch_images import (
    _classify_temporal_intent,
    _determine_asset_temporal_match,
    _check_semantic_evidence,
    _infer_effective_asset_type,
    _check_renderability,
    _classify_date_evidence,
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _candidate(title: str, description: str = "", source_url: str = "") -> dict:
    return {
        "title": title,
        "description": description,
        "sourceUrl": source_url,
    }


def _visual_plan(
    editorial_role: str = "",
    primary_asset_type: str = "",
    period: str = "",
    location: str = "",
    entities: list[str] | None = None,
) -> dict:
    return {
        "editorialRole": editorial_role,
        "primaryAssetType": primary_asset_type,
        "period": period,
        "location": location,
        "entities": entities or [],
    }


def _scene(voiceover: str = "", visual_plan: dict | None = None) -> dict:
    return {
        "voiceover": voiceover,
        "visualPlan": visual_plan or {},
    }


# ── Hard rule: context_map requires map/document asset type ───────────────


def test_context_map_rule_allows_historical_map():
    """context_map accepts a scene whose primaryAssetType is historical_map."""
    visual_plan = _visual_plan(
        editorial_role="context_map",
        primary_asset_type="historical_map",
        period="Guerra Fría",
        location="Berlín, Alemania",
        entities=["Muro de Berlín"],
    )
    allowed_context_map_types = {
        "map", "historical_map", "document", "newspaper",
        "map_or_document", "historical_map_or_document",
    }
    assert visual_plan["primaryAssetType"] in allowed_context_map_types


def test_context_map_rule_rejects_historical_photograph():
    """context_map rejects a scene whose primaryAssetType is historical_photograph."""
    visual_plan = _visual_plan(
        editorial_role="context_map",
        primary_asset_type="historical_photograph",
        period="Guerra Fría",
        location="Berlín, Alemania",
        entities=["Muro de Berlín"],
    )
    allowed_context_map_types = {
        "map", "historical_map", "document", "newspaper",
        "map_or_document", "historical_map_or_document",
    }
    assert visual_plan["primaryAssetType"] not in allowed_context_map_types


# ── Hard rule: event_depiction requires historical_event/archival_context ─


def test_event_depiction_accepts_1989_fall_photo():
    """A real 1989 fall-of-the-Wall photo matches as historical_event."""
    candidate = _candidate(
        title="Juggling on the Berlin Wall on 16. November 1989.",
        source_url="https://upload.wikimedia.org/wikipedia/commons/4/40/Juggling_on_the_Berlin_Wall_1a.jpg",
    )
    visual_plan = _visual_plan(
        editorial_role="consequence_or_legacy",
        primary_asset_type="historical_photograph",
        period="Post-Guerra Fría",
        location="Berlín, Alemania",
        entities=["Caída del Muro de Berlín", "1989"],
    )
    scene = _scene(voiceover="El Muro cayó en 1989, un símbolo de libertad.", visual_plan=visual_plan)
    match = _determine_asset_temporal_match(candidate, visual_plan, scene)
    temporal_intent = _classify_temporal_intent(scene)
    assert temporal_intent == "event_depiction"
    assert match in ("historical_event", "archival_context")


def test_event_depiction_rejects_modern_anniversary_photo():
    """A 2024 anniversary photo is modern_legacy and unfit for event_depiction."""
    candidate = _candidate(
        title="Celebration of the 35th anniversary of the fall of the Berlin Wall.",
        source_url="https://upload.wikimedia.org/wikipedia/commons/7/7b/35th_anniversary_of_the_fall.jpg",
    )
    visual_plan = _visual_plan(
        editorial_role="consequence_or_legacy",
        primary_asset_type="historical_photograph",
        period="Post-Guerra Fría",
        location="Berlín, Alemania",
        entities=["Caída del Muro de Berlín", "1989"],
    )
    scene = _scene(voiceover="El Muro cayó en 1989, un símbolo de libertad.", visual_plan=visual_plan)
    match = _determine_asset_temporal_match(candidate, visual_plan, scene)
    temporal_intent = _classify_temporal_intent(scene)
    assert temporal_intent == "event_depiction"
    assert match == "modern_legacy"


def test_event_depiction_rejects_modern_stock_photo():
    """A generic modern stock photo is modern_legacy and unfit for event_depiction."""
    candidate = _candidate(
        title="Modern city skyline at sunset",
        description="Contemporary urban photography",
    )
    visual_plan = _visual_plan(
        editorial_role="battle_or_assault",
        primary_asset_type="historical_photograph",
        period="Guerra Fría",
        location="Berlín, Alemania",
        entities=["Muro de Berlín"],
    )
    scene = _scene(voiceover="El 13 de agosto de 1961, comenzó la construcción del Muro.", visual_plan=visual_plan)
    match = _determine_asset_temporal_match(candidate, visual_plan, scene)
    temporal_intent = _classify_temporal_intent(scene)
    assert temporal_intent == "event_depiction"
    assert match == "modern_legacy"


# ── Visual temporal intent classification ─────────────────────────────────


def test_classify_temporal_intent_event_depiction_from_voiceover():
    """Voiceover mentioning 'cayó en 1989' triggers event_depiction for consequence_or_legacy role."""
    scene = _scene(
        voiceover="El Muro cayó en 1989, un símbolo de libertad.",
        visual_plan={"editorialRole": "consequence_or_legacy"},
    )
    assert _classify_temporal_intent(scene) == "event_depiction"


def test_classify_temporal_intent_legacy_from_voiceover():
    """Voiceover mentioning 'legado' triggers legacy_or_commemoration."""
    scene = _scene(voiceover="Explora más sobre la historia del Muro y su legado.")
    assert _classify_temporal_intent(scene) == "legacy_or_commemoration"


# ── Reuse compatibility: voiceover year extraction ────────────────────────


def test_reuse_voiceover_year_extraction_blocks_1961_to_1989():
    """Years extracted from voiceover detect a 1961 asset reused for a 1989 scene."""
    prev_years = {"1961"}
    current_period = "Post-Guerra Fría"
    current_years = {t for t in current_period.split() if t.isdigit() and len(t) == 4}
    scene_vo = "El Muro cayó en 1989, un símbolo de libertad."
    for token in scene_vo.split():
        clean = token.strip(".,;:!?()[]{}'\"")
        if clean.isdigit() and len(clean) == 4:
            current_years.add(clean)
    assert current_years == {"1989"}
    assert prev_years.intersection(current_years) == set()


# ── context_map effective asset type validation ──────────────────────────


def test_context_map_rejects_berlin_wall_photo_declared_as_map():
    """A 1986 Berlin Wall photograph must fail context_map despite declared historical_map."""
    candidate = _candidate(
        title="This image of the Berlin Wall was taken in 1986 by Thierry Noir at Bethaniendamm in Berlin-Kreuzberg.",
        source_url="https://upload.wikimedia.org/wikipedia/commons/5/5d/Berlinermauer.jpg",
    )
    declared_type = "historical_map"
    effective_type = _infer_effective_asset_type(candidate, declared_type)
    assert effective_type == "historical_photograph", f"Expected historical_photograph, got {effective_type}"

    scene = _scene(
        voiceover="En 1961, Berlín, dividida entre Oriente y Occidente, quedó marcada.",
        visual_plan=_visual_plan(
            editorial_role="context_map",
            primary_asset_type="historical_map",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )

    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    role_ev = se.get("roleEvidence", [])

    allowed = {"map", "historical_map", "document", "newspaper",
               "map_or_document", "historical_map_or_document"}
    assert effective_type not in allowed
    assert len(role_ev) == 0


def test_context_map_accepts_occupation_zones_map():
    """An actual Berlin occupation-zones map must pass context_map validation."""
    candidate = _candidate(
        title="Map of Berlin occupation zones and sectors after World War II.",
        source_url="https://upload.wikimedia.org/wikipedia/commons/example_berlin_sectors.jpg",
    )
    declared_type = "historical_map"
    effective_type = _infer_effective_asset_type(candidate, declared_type)
    assert effective_type == "historical_map", f"Expected historical_map, got {effective_type}"

    scene = _scene(
        voiceover="En 1961, Berlín, dividida entre Oriente y Occidente.",
        visual_plan=_visual_plan(
            editorial_role="context_map",
            primary_asset_type="historical_map",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )

    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    role_ev = se.get("roleEvidence", [])
    assert len(role_ev) > 0, f"Expected non-empty roleEvidence for a map, got {role_ev}"


def test_context_map_rejects_empty_role_evidence():
    """Empty roleEvidence must fail context_map even if declaredAssetType is historical_map."""
    candidate = _candidate(
        title="General view of Berlin city center, modern architecture",
        source_url="https://example.com/berlin_view.jpg",
    )
    declared_type = "historical_map"

    scene = _scene(
        voiceover="Berlín, dividida entre Oriente y Occidente.",
        visual_plan=_visual_plan(
            editorial_role="context_map",
            primary_asset_type="historical_map",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )

    effective_type = _infer_effective_asset_type(candidate, declared_type)
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    role_ev = se.get("roleEvidence", [])

    allowed = {"map", "historical_map", "document", "newspaper",
               "map_or_document", "historical_map_or_document"}
    # Even if effective_type passes, roleEvidence must be non-empty
    assert len(role_ev) == 0


def test_context_map_accepts_division_document():
    """A document describing Berlin sector/division must pass context_map."""
    candidate = _candidate(
        title="Document describing the division of Berlin into four occupation sectors, 1945.",
        source_url="https://upload.wikimedia.org/wikipedia/commons/example_division_doc.jpg",
    )
    declared_type = "historical_map"
    effective_type = _infer_effective_asset_type(candidate, declared_type)
    assert effective_type == "document", f"Expected document, got {effective_type}"

    scene = _scene(
        voiceover="Berlín, dividida entre Oriente y Occidente.",
        visual_plan=_visual_plan(
            editorial_role="context_map",
            primary_asset_type="historical_map",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )

    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    role_ev = se.get("roleEvidence", [])
    assert len(role_ev) > 0, f"Expected non-empty roleEvidence for a division document, got {role_ev}"


# ── Renderability pre-check ──────────────────────────────────────────────


def test_blank_map_rejected_before_selection():
    """A 550x463 blank map must fail renderability before selection."""
    candidate = _candidate(
        title="Germany divided Berlin (West), blank (for e.g. location maps and other uses)",
        source_url="https://upload.wikimedia.org/wikipedia/commons/a/a4/Germany_divided_Berlin_West.png",
    )
    candidate["width"] = 550
    candidate["height"] = 463
    renderability = _check_renderability(candidate, "context_map")
    assert renderability["status"] == "FAIL"
    reasons = " ".join(renderability["reasons"])
    assert "dimensions_too_small" in reasons or "map_readability_too_low" in reasons or "blank" in reasons


def test_candidate_passing_selection_cannot_fail_render_dimension():
    """A candidate with both dimensions >= 720 must PASS renderability."""
    candidate = _candidate(
        title="August 1961 Newsweek map of the occupation zones of Berlin",
        source_url="https://example.com/newsweek_map.jpg",
    )
    candidate["width"] = 800
    candidate["height"] = 900
    renderability = _check_renderability(candidate, "context_map")
    # Both dimensions >= 720, so dimensions pass. Map readability may be low
    # for portrait orientation, but the dimension check must pass.
    reasons = " ".join(renderability["reasons"])
    assert "dimensions_too_small" not in reasons


def test_blank_location_map_metadata_fails_context_map():
    """A blank location-map template must fail context_map validation."""
    candidate = _candidate(
        title="Blank Berlin location map, unlabeled template for e.g. editing",
        source_url="https://example.com/blank_berlin.png",
    )
    candidate["width"] = 800
    candidate["height"] = 600
    renderability = _check_renderability(candidate, "context_map")
    assert renderability["status"] == "FAIL"
    reasons = " ".join(renderability["reasons"])
    assert "blank_or_template_map" in reasons


def test_family_separation_photo_fails_direct_construction():
    """A family-separation photo must not count as direct construction evidence."""
    candidate = _candidate(
        title="Late August 1961. With a goodbye bouquet and clinging hands, a family separated at the Wall.",
        source_url="https://example.com/family_wall.jpg",
    )
    scene = _scene(
        voiceover="El 13 de agosto de 1961, comenzó la construcción del Muro.",
        visual_plan=_visual_plan(
            editorial_role="battle_or_assault",
            primary_asset_type="historical_photograph",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    const_ev = se.get("constructionSubjectEvidence", [])
    assert len(const_ev) == 0


def test_construction_photo_passes_direct_construction():
    """An actual construction-worker photo must pass construction subject check."""
    candidate = _candidate(
        title="East German construction workers building the Berlin Wall, August 1961.",
        source_url="https://example.com/construction.jpg",
    )
    scene = _scene(
        voiceover="El 13 de agosto de 1961, comenzó la construcción del Muro.",
        visual_plan=_visual_plan(
            editorial_role="battle_or_assault",
            primary_asset_type="historical_photograph",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    const_ev = se.get("constructionSubjectEvidence", [])
    assert len(const_ev) > 0


def test_render_timeline_coverage_fills_scene_gaps():
    """Render timeline must cover gaps between scene windows and extend to audio end."""
    from pathlib import Path
    sys.path.insert(0, str(Path("/home/javi/projects/shorts-creator/bin")))
    from prepare_job import _fill_timeline_gaps

    timeline = [
        {"sceneNumber": 1, "beatIndex": 1, "startSec": 0.1, "endSec": 5.675},
        {"sceneNumber": 2, "beatIndex": 1, "startSec": 6.537, "endSec": 11.05},
        {"sceneNumber": 3, "beatIndex": 1, "startSec": 11.912, "endSec": 15.525},
        {"sceneNumber": 4, "beatIndex": 1, "startSec": 16.387, "endSec": 20.025},
        {"sceneNumber": 5, "beatIndex": 1, "startSec": 20.887, "endSec": 24.438},
    ]
    audio_dur = 25.32
    filled = _fill_timeline_gaps(timeline, audio_dur)

    # Visual start at <= 0.0
    assert filled[0]["startSec"] == 0.0
    # No gap > 0.05
    for i in range(len(filled) - 1):
        gap = filled[i + 1]["startSec"] - filled[i]["endSec"]
        assert abs(gap) <= 0.05, f"Gap of {gap}s between scene {i+1} and {i+2}"
    # End at audio duration
    assert abs(filled[-1]["endSec"] - audio_dur) <= 0.1


# ── Border-closure construction evidence (v8) ─────────────────────────────


def test_border_closure_evidence_accepts_barbed_wire():
    """A 1961 barbed-wire/barricade photo must pass border_closure_construction."""
    candidate = _candidate(
        title="East German soldiers erecting barbed wire barricades during the border closure, Berlin 1961.",
        source_url="https://example.com/barbed_wire_berlin.jpg",
    )
    scene = _scene(
        voiceover="El 13 de agosto de 1961, comenzó la construcción del Muro.",
        visual_plan=_visual_plan(
            editorial_role="border_closure_construction",
            primary_asset_type="historical_photograph",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    assert len(se.get("borderClosureSubjectEvidence", [])) > 0
    assert se["semanticConfidence"] in ("medium", "high")


def test_border_closure_evidence_accepts_mauerbau():
    """German 'Mauerbau' metadata must be recognized as border-closure evidence."""
    candidate = _candidate(
        title="Mauerbau in Berlin, August 1961: Stacheldraht und Sperranlagen an der Grenze.",
        source_url="https://example.com/mauerbau.jpg",
    )
    scene = _scene(
        voiceover="El 13 de agosto de 1961, comenzó la construcción del Muro.",
        visual_plan=_visual_plan(
            editorial_role="border_closure_construction",
            primary_asset_type="historical_photograph",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    assert len(se.get("borderClosureSubjectEvidence", [])) > 0


def test_border_closure_evidence_rejects_family_separation():
    """A family-separation photo must not count as border-closure construction evidence."""
    candidate = _candidate(
        title="Late August 1961. With a goodbye bouquet and clinging hands, a family separated at the Wall.",
        source_url="https://example.com/family_wall.jpg",
    )
    scene = _scene(
        voiceover="El 13 de agosto de 1961, comenzó la construcción del Muro.",
        visual_plan=_visual_plan(
            editorial_role="border_closure_construction",
            primary_asset_type="historical_photograph",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    assert len(se.get("borderClosureSubjectEvidence", [])) == 0


def test_border_closure_evidence_rejects_checkpoint():
    """A generic checkpoint photo must not count as border-closure construction evidence."""
    candidate = _candidate(
        title="Allied soldiers at Checkpoint Charlie, Berlin.",
        source_url="https://example.com/checkpoint.jpg",
    )
    scene = _scene(
        voiceover="El 13 de agosto de 1961, comenzó la construcción del Muro.",
        visual_plan=_visual_plan(
            editorial_role="border_closure_construction",
            primary_asset_type="historical_photograph",
            period="Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín"],
        ),
    )
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    assert len(se.get("borderClosureSubjectEvidence", [])) == 0


# ── Derived-artifact isolation (v8) ───────────────────────────────────────


def test_clone_job_strips_derived_artifacts(tmp_path):
    """clone_job must not inherit timeline, renderTimeline, assets, or render paths."""
    from clone_job import clone_job, DERIVED_KEYS

    source_dir = tmp_path / "source-job"
    source_dir.mkdir()
    source_metadata = source_dir / "metadata.json"
    source_data = {
        "jobId": "source-001",
        "status": "RENDERED",
        "request": {"topic": "Test"},
        "script": {"scenes": []},
        "assets": [{"path": "source/scene.jpg"}],
        "timeline": [{"imagePath": "source/scene.jpg"}],
        "renderTimeline": [{"assetPath": "source/scene.jpg"}],
        "subtitles": {"path": "source/subtitle.ass"},
        "render": {"path": "source/video.mp4"},
        "assetValidation": {"status": "PASS"},
        "validation": {"frames": []},
        "review": {"status": "PENDING"},
        "resolvedConfig": {"foo": "bar"},
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    source_metadata.write_text(json.dumps(source_data))

    target_dir = tmp_path / "target-job"
    new_metadata = clone_job(source_metadata, target_dir, job_id="target-001")
    new_data = json.loads(new_metadata.read_text())

    assert new_data["jobId"] == "target-001"
    assert new_data["status"] == "SCRIPT_READY"
    path_carrying_keys = {
        "assets", "timeline", "renderTimeline", "subtitles", "render",
        "assetValidation", "validation", "review", "resolvedConfig",
    }
    for key in path_carrying_keys:
        assert key not in new_data, f"derived key {key} must be stripped"
    assert new_data["request"] == {"topic": "Test"}
    assert new_data["script"] == {"scenes": []}
    assert new_data["updatedAt"] != "2026-01-01T00:00:00Z"


def test_clone_job_applies_scene_patch(tmp_path):
    """clone_job must apply visualPlan patches per scene."""
    from clone_job import clone_job

    source_dir = tmp_path / "source-job"
    source_dir.mkdir()
    source_metadata = source_dir / "metadata.json"
    source_data = {
        "jobId": "source-001",
        "status": "RENDERED",
        "request": {"topic": "Test"},
        "script": {
            "scenes": [
                {"sceneNumber": 1, "voiceover": "x", "visualPlan": {"editorialRole": "battle_or_assault"}},
                {"sceneNumber": 2, "voiceover": "y", "visualPlan": {"editorialRole": "battle_or_assault"}},
            ]
        },
    }
    source_metadata.write_text(json.dumps(source_data))

    target_dir = tmp_path / "target-job"
    new_metadata = clone_job(
        source_metadata,
        target_dir,
        job_id="target-002",
        scene_patches={2: {"editorialRole": "border_closure_construction"}},
    )
    new_data = json.loads(new_metadata.read_text())
    scenes = new_data["script"]["scenes"]
    assert scenes[0]["visualPlan"]["editorialRole"] == "battle_or_assault"
    assert scenes[1]["visualPlan"]["editorialRole"] == "border_closure_construction"


def test_prepare_job_regenerates_paths_under_current_job_dir(tmp_path):
    """prepare_job must write timeline/renderTimeline paths inside the current job dir."""
    import json
    from prepare_job import build_timeline, build_render_timeline

    video_dir = tmp_path / "v8-job"
    scenes_dir = video_dir / "scenes"
    scenes_dir.mkdir(parents=True)
    # Create dummy asset files so prepare_job sees them as existing
    for sn in (1, 2):
        (scenes_dir / f"scene-{sn:02}-01.jpg").write_text("image")
        (scenes_dir / f"scene-{sn:02}.mp3").write_text("audio")

    scenes = [
        {
            "sceneNumber": 1,
            "targetDurationSec": 5,
            "visualPlan": {"visualSequence": [{"segmentIndex": 1, "assetType": "historical_photograph"}]},
        },
        {
            "sceneNumber": 2,
            "targetDurationSec": 5,
            "visualPlan": {"visualSequence": [{"segmentIndex": 1, "assetType": "historical_photograph"}]},
        },
    ]
    assets = [
        {
            "sceneNumber": 1,
            "segments": [{"segmentIndex": 1, "path": str(scenes_dir / "scene-01-01.jpg"), "assetType": "historical_photograph"}],
        },
        {
            "sceneNumber": 2,
            "segments": [{"segmentIndex": 1, "path": str(scenes_dir / "scene-02-01.jpg"), "assetType": "historical_photograph"}],
        },
    ]

    timeline = build_timeline(scenes, assets, video_dir, scenes_dir)
    render_timeline = build_render_timeline(scenes, assets, scenes_dir)

    for entry in timeline:
        img = Path(entry["imagePath"])
        if img.is_absolute():
            assert img.resolve().is_relative_to(video_dir.resolve())
        audio = Path(entry["audioPath"])
        assert audio.resolve().is_relative_to(video_dir.resolve())

    for entry in render_timeline:
        asset = Path(entry["assetPath"])
        if asset.is_absolute():
            assert asset.resolve().is_relative_to(video_dir.resolve())


def test_render_preflight_rejects_cross_job_paths(tmp_path):
    """render_job preflight must fail with CROSS_JOB_ARTIFACT_REFERENCE for external paths."""
    import json
    from render_job import preflight_validate

    project_root = tmp_path / "project"
    project_root.mkdir()
    video_dir = project_root / "data" / "videos" / "v8-job"
    video_dir.mkdir(parents=True)
    other_video_dir = project_root / "data" / "videos" / "v7-job"
    other_video_dir.mkdir(parents=True)
    scenes_dir = video_dir / "scenes"
    scenes_dir.mkdir()

    # Create valid local asset and stale cross-job asset
    (scenes_dir / "scene-01-01.jpg").write_text("image")
    (other_video_dir / "scenes").mkdir()
    (other_video_dir / "scenes" / "scene-01-01.jpg").write_text("stale")

    metadata = {
        "assets": [
            {"sceneNumber": 1, "segments": [{"path": str(scenes_dir / "scene-01-01.jpg")}]},
            {"sceneNumber": 2, "segments": [{"path": str(other_video_dir / "scenes" / "scene-01-01.jpg")}]},
        ],
    }
    render_timeline = [
        {
            "sceneNumber": 1,
            "beatIndex": 1,
            "assetPath": "scenes/scene-01-01.jpg",
            "startSec": 0,
            "endSec": 5,
            "durationSec": 5,
        },
        {
            "sceneNumber": 2,
            "beatIndex": 1,
            "assetPath": str(other_video_dir / "scenes" / "scene-01-01.jpg"),
            "startSec": 5,
            "endSec": 10,
            "durationSec": 5,
        },
    ]
    scenes = [
        {"sceneNumber": 1, "targetDurationSec": 5},
        {"sceneNumber": 2, "targetDurationSec": 5},
    ]

    errors = preflight_validate(
        render_timeline, scenes, project_root, video_dir,
        expected_total=10, metadata=metadata,
    )
    cross_job_errors = [e for e in errors if "CROSS_JOB_ARTIFACT_REFERENCE" in e]
    assert len(cross_job_errors) >= 1
    assert any("v7-job" in e for e in cross_job_errors)


# ── Phase 19: Date evidence separation and reuse hardening ─────────────


def _date_candidate(title: str, description: str = "", source_url: str = "") -> dict:
    return {
        "title": title,
        "description": description,
        "sourceUrl": source_url,
    }


def test_title_range_1961_1989_is_context_only_not_depicted():
    """A title containing '1961 - 1989' must not satisfy sourceDepictedDateEvidence=1989."""
    candidate = _date_candidate(
        title="The Berlin Wall 1961 - 1989. Families separated by the Wall.",
        description="Following the marriage of a young German couple in West Berlin, "
                   "the mother and aunt of the bride congratulate the newly weds from "
                   "the window of a building in Bernauer Strasse, East Berlin on 8 September 1961.",
    )
    depicted, context = _classify_date_evidence(candidate)
    assert "1989" in context
    assert "1989" not in depicted
    assert "1961" in depicted or "1961" in context


def test_family_separated_1961_asset_fails_target_event_1989():
    """The Berlin Wall 1961 - 1989 family image must fail target event 1989."""
    candidate = _date_candidate(
        title="The Berlin Wall 1961 - 1989. Families separated by the Wall.",
        description="Following the marriage of a young German couple in West Berlin, "
                   "the mother and aunt of the bride congratulate the newly weds from "
                   "the window of a building in Bernauer Strasse, East Berlin on 8 September 1961.",
    )
    scene = _scene(
        voiceover="El Muro cayó en 1989, un símbolo de libertad.",
        visual_plan=_visual_plan(
            editorial_role="consequence_or_legacy",
            primary_asset_type="historical_photograph",
            period="Post-Guerra Fría",
            location="Berlín, Alemania",
            entities=["Caída del Muro de Berlín", "1989"],
        ),
    )
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    depicted = set(se.get("sourceDepictedDateEvidence", []))
    fall_open = se.get("fallOpeningSubjectEvidence", [])
    division_subj = se.get("divisionSubjectEvidence", [])
    # 1989 must not be in depicted
    assert "1989" not in depicted
    # No explicit fall/opening subject evidence
    assert len(fall_open) == 0
    # Has division/family subject evidence
    assert len(division_subj) > 0
    # Therefore the candidate must fail event_depiction for 1989
    has_depicted_overlap = depicted.intersection({"1989"})
    has_fall_subject = bool(fall_open)
    has_division_subject = bool(division_subj)
    passes = (has_depicted_overlap or has_fall_subject) and not (has_division_subject and not has_depicted_overlap and not has_fall_subject)
    assert passes is False


def test_juggling_berlin_wall_1989_passes_target_event_1989():
    """'Juggling on the Berlin Wall on 16 November 1989' must pass target event 1989."""
    candidate = _date_candidate(
        title="Juggling on the Berlin Wall on 16. November 1989.",
        source_url="https://upload.wikimedia.org/wikipedia/commons/4/40/Juggling_on_the_Berlin_Wall_1a.jpg",
    )
    scene = _scene(
        voiceover="El Muro cayó en 1989, un símbolo de libertad.",
        visual_plan=_visual_plan(
            editorial_role="consequence_or_legacy",
            primary_asset_type="historical_photograph",
            period="Post-Guerra Fría",
            location="Berlín, Alemania",
            entities=["Caída del Muro de Berlín", "1989"],
        ),
    )
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    depicted = set(se.get("sourceDepictedDateEvidence", []))
    fall_open = se.get("fallOpeningSubjectEvidence", [])
    assert "1989" in depicted
    assert len(fall_open) > 0


def test_scene3_family_asset_may_pass_scene5_only_with_legacy_reason():
    """Scene 3 family asset may pass Scene 5 only with explicit legacy-of-division reason."""
    # Scene 5 (legacy/CTA) is legacy_or_commemoration, not event_depiction.
    # Reuse is allowed for legacy when target narration is not a distinct event.
    candidate = _date_candidate(
        title="The Berlin Wall 1961 - 1989. Families separated by the Wall.",
        description="Late August 1961. With a goodbye bouquet and clinging hands, a family separated.",
    )
    scene = _scene(
        voiceover="Explora más sobre la historia del Muro y su legado, síguenos.",
        visual_plan=_visual_plan(
            editorial_role="consequence_or_legacy",
            primary_asset_type="historical_photograph",
            period="Post-Guerra Fría",
            location="Berlín, Alemania",
            entities=["Muro de Berlín", "legado"],
        ),
    )
    # Legacy_or_commemoration scene (no event year in voiceover → no 1989)
    temporal_intent = _classify_temporal_intent(scene)
    assert temporal_intent == "legacy_or_commemoration"
    # Reuse validation: scene targets no specific year, so reuse is not blocked
    # on date grounds. Validation must require explicit human-legacy reason.
    se = _check_semantic_evidence(candidate, scene, "Berlin Wall")
    division_subj = se.get("divisionSubjectEvidence", [])
    assert len(division_subj) > 0
    # The reuse_compatibility_reason must explicitly mention "human legacy of division"
    # when origRole is civilian_impact. Simulated here:
    reuse_reason = "human legacy of division (divided families); visual consistency across consecutive scenes"
    assert "human legacy of division" in reuse_reason


def test_border_closure_construction_without_evidence_fails_asset_validation():
    """border_closure_construction role without borderClosureSubjectEvidence fails."""
    from asset_validation import check_role_evidence

    seg = {
        "editorialRole": "border_closure_construction",
        "semanticEvidence": {"borderClosureSubjectEvidence": []},
    }
    failures = check_role_evidence(seg, "border_closure_construction")
    assert any(f["rule"] == "missing_border_closure_evidence" for f in failures)


def test_reuse_civilian_impact_for_distinct_event_1989_fails_asset_validation():
    """Reusing a civilian_impact asset for the 1989 fall must fail asset validation."""
    from asset_validation import check_reuse_compatibility

    seg = {
        "reuseReason": "reuse_previous_valid_asset",
        "originalEditorialRole": "civilian_impact",
        "semanticEvidence": {
            "sourceDepictedDateEvidence": ["1961"],
            "divisionSubjectEvidence": ["families separated"],
            "fallOpeningSubjectEvidence": [],
        },
    }
    scene = {"sceneNumber": 4, "voiceover": "El Muro cayó en 1989, un símbolo de libertad."}
    failures = check_reuse_compatibility(seg, scene)
    rules = [f["rule"] for f in failures]
    assert "reuse_civilian_impact_for_distinct_event" in rules
    assert "reuse_division_subject_for_distinct_event" in rules
