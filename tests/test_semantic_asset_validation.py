"""Regression tests for asset validation, shorts_creator.rendering.preparer, clone_job, and shorts_creator.rendering.renderer.

These tests are neutral preserved regressions that do not depend on the
legacy fetch_images V1 stack. They cover:

- render_timeline gap-filling (shorts_creator.rendering.preparer)
- clone_job derived-artifact stripping and scene patching
- shorts_creator.rendering.preparer path regeneration
- shorts_creator.rendering.renderer cross-job preflight
- render_timeline per-scene sequential continuity
- shorts_creator.validation.asset role-evidence and reuse-compatibility rules

Run: python3 -m pytest tests/test_semantic_asset_validation.py -v
"""

import json
import sys
from pathlib import Path


def test_render_timeline_coverage_fills_scene_gaps():
    """Render timeline must cover gaps between scene windows and extend to audio end."""
    from pathlib import Path
    sys.path.insert(0, str(Path("/home/javi/projects/shorts-creator/bin")))
    from shorts_creator.rendering.preparer import _fill_timeline_gaps

    timeline = [
        {"sceneNumber": 1, "beatIndex": 1, "startSec": 0.1, "endSec": 5.675},
        {"sceneNumber": 2, "beatIndex": 1, "startSec": 6.537, "endSec": 11.05},
        {"sceneNumber": 3, "beatIndex": 1, "startSec": 11.912, "endSec": 15.525},
        {"sceneNumber": 4, "beatIndex": 1, "startSec": 16.387, "endSec": 20.025},
        {"sceneNumber": 5, "beatIndex": 1, "startSec": 20.887, "endSec": 24.438},
    ]
    audio_dur = 25.32
    filled = _fill_timeline_gaps(timeline, audio_dur)

    assert filled[0]["startSec"] == 0.0
    for i in range(len(filled) - 1):
        gap = filled[i + 1]["startSec"] - filled[i]["endSec"]
        assert abs(gap) <= 0.05, f"Gap of {gap}s between scene {i+1} and {i+2}"
    assert abs(filled[-1]["endSec"] - audio_dur) <= 0.1


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
    """shorts_creator.rendering.preparer must write timeline/renderTimeline paths inside the current job dir."""
    import json
    from shorts_creator.rendering.preparer import build_timeline, build_render_timeline

    video_dir = tmp_path / "v8-job"
    scenes_dir = video_dir / "scenes"
    scenes_dir.mkdir(parents=True)
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
    render_timeline = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 4.65, 2: 4.65})

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
    """shorts_creator.rendering.renderer preflight must fail with CROSS_JOB_ARTIFACT_REFERENCE for external paths."""
    import json
    from shorts_creator.rendering.renderer import preflight_validate

    project_root = tmp_path / "project"
    project_root.mkdir()
    video_dir = project_root / "data" / "videos" / "v8-job"
    video_dir.mkdir(parents=True)
    other_video_dir = project_root / "data" / "videos" / "v7-job"
    other_video_dir.mkdir(parents=True)
    scenes_dir = video_dir / "scenes"
    scenes_dir.mkdir()

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


def test_render_timeline_per_scene_sequential_continuity():
    """build_render_timeline with per-scene (non-continuous) audio must produce
    sequential, non-overlapping timing entries accumulated across scenes.
    Regression for la-2026-07-05-203359 where every renderTimeline entry started
    at ~0.0.
    """
    import sys, os
    from pathlib import Path

    PROJECT = Path(__file__).resolve().parents[1]
    bin_path = str(PROJECT / "bin")
    old_path = list(sys.path)
    sys.path.insert(0, bin_path)
    try:
        from shorts_creator.rendering.preparer import build_render_timeline
    finally:
        sys.path[:] = old_path

    scenes = [
        {
            "sceneNumber": 1, "voiceover": "S1 voice", "subtitle": "S1",
            "targetDurationSec": 6.0, "visualTemporalIntent": "event_depiction",
            "visualPlan": {"editorialRole": "battle_or_assault", "strategy": "historical_archive",
                           "primaryAssetType": "historical_photograph",
                           "visualSequence": []},
            "narrativeBeats": [{"beatIndex": 1, "startCueIndex": 0, "endCueIndex": 0}],
            "subtitleTiming": {"cues": [{"startSec": 0.0, "endSec": 6.0, "text": "S1"}]},
        },
        {
            "sceneNumber": 2, "voiceover": "S2 voice", "subtitle": "S2",
            "targetDurationSec": 6.0, "visualTemporalIntent": "event_depiction",
            "visualPlan": {"editorialRole": "document_or_date", "strategy": "historical_archive",
                           "primaryAssetType": "historical_photograph",
                           "visualSequence": []},
            "narrativeBeats": [{"beatIndex": 1, "startCueIndex": 0, "endCueIndex": 0}],
            "subtitleTiming": {"cues": [{"startSec": 0.0, "endSec": 6.0, "text": "S2"}]},
        },
        {
            "sceneNumber": 3, "voiceover": "S3 voice", "subtitle": "S3",
            "targetDurationSec": 6.0, "visualTemporalIntent": "event_depiction",
            "visualPlan": {"editorialRole": "civilian_impact", "strategy": "historical_archive",
                           "primaryAssetType": "historical_photograph",
                           "visualSequence": []},
            "narrativeBeats": [{"beatIndex": 1, "startCueIndex": 0, "endCueIndex": 0}],
            "subtitleTiming": {"cues": [{"startSec": 0.0, "endSec": 6.0, "text": "S3"}]},
        },
    ]
    assets = [
        {"sceneNumber": 1, "selected": True, "assetType": "historical_photograph",
         "segments": [{"segmentIndex": 1, "path": "/tmp/s1.jpg", "durationSec": 6.0, "transition": "cut", "assetType": "historical_photograph"}]},
        {"sceneNumber": 2, "selected": True, "assetType": "historical_photograph",
         "segments": [{"segmentIndex": 1, "path": "/tmp/s2.jpg", "durationSec": 6.0, "transition": "cut", "assetType": "historical_photograph"}]},
        {"sceneNumber": 3, "selected": True, "assetType": "historical_photograph",
         "segments": [{"segmentIndex": 1, "path": "/tmp/s3.jpg", "durationSec": 6.0, "transition": "cut", "assetType": "historical_photograph"}]},
    ]
    scenes_dir = Path("/tmp")

    rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 5.65, 2: 5.65, 3: 5.65})

    assert len(rt) >= 3, f"Expected at least 3 entries, got {len(rt)}"
    starts = [e["startSec"] for e in rt]
    ends = [e["endSec"] for e in rt]
    durs = [e["durationSec"] for e in rt]

    assert all(starts[i] < starts[i + 1] for i in range(len(starts) - 1)), (
        f"Start times must be increasing, got {starts}"
    )
    for i in range(len(rt) - 1):
        gap = starts[i + 1] - ends[i]
        assert gap < 0.05, f"Gap of {gap}s between entry {i} (ends {ends[i]}) and entry {i + 1} (starts {starts[i + 1]})"
    assert abs(starts[0]) < 0.05, f"First start should be ~0, got {starts[0]}"
    assert abs(ends[-1] - 18.0) < 1.0, f"Total duration should be ~18s, got {ends[-1]}"
    for i, d in enumerate(durs):
        assert d > 0, f"Entry {i} duration {d} must be positive"


def test_border_closure_construction_without_evidence_fails_asset_validation():
    """border_closure_construction role without borderClosureSubjectEvidence fails."""
    from shorts_creator.validation.asset import check_role_evidence

    seg = {
        "editorialRole": "border_closure_construction",
        "semanticEvidence": {"borderClosureSubjectEvidence": []},
    }
    failures = check_role_evidence(seg, "border_closure_construction")
    assert any(f["rule"] == "missing_border_closure_evidence" for f in failures)


def test_reuse_civilian_impact_for_distinct_event_1989_fails_asset_validation():
    """Reusing a civilian_impact asset for the 1989 fall must fail asset validation."""
    from shorts_creator.validation.asset import check_reuse_compatibility

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
