"""Offline tests for Slice 2 VIDEO rendering path. No network, no Docker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT = Path(__file__).resolve().parents[1]
if str(_PROJECT / "bin") not in sys.path:
    sys.path.insert(0, str(_PROJECT / "bin"))

import shorts_creator.validation.asset as asset_validation
from shorts_creator.assets.bridge import apply_visual_assets_v2_to_metadata
from shorts_creator.rendering.preparer import build_render_timeline
from shorts_creator.rendering.renderer import (
    build_asset_input_args,
    build_video_normalize_filter,
)


# ── Renderer pure helpers ────────────────────────────────────────────────────


def test_build_asset_input_args_video_stream_loop():
    assert build_asset_input_args("VIDEO", "/workspace/clip.mp4") == [
        "-stream_loop", "-1", "-i", "/workspace/clip.mp4",
    ]


def test_build_asset_input_args_image_loop_one():
    assert build_asset_input_args("IMAGE", "/workspace/img.jpg") == [
        "-loop", "1", "-i", "/workspace/img.jpg",
    ]


def test_build_asset_input_args_defaults_to_image():
    assert build_asset_input_args("", "/workspace/img.jpg")[0] == "-loop"


def test_video_normalize_filter_semantics():
    chain = build_video_normalize_filter(4.0)
    assert "trim=duration=4.0" in chain
    assert "setpts=PTS-STARTPTS" in chain
    assert "fps=25" in chain
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in chain
    assert "crop=1080:1920" in chain
    assert "setsar=1" in chain
    assert "format=yuv420p" in chain
    # No image motion, no audio filter, no :a stream reference
    assert "zoompan" not in chain
    assert "pan" not in chain
    assert ":a" not in chain
    assert "aresample" not in chain and "anull" not in chain


# ── Prepare transport ────────────────────────────────────────────────────────


def _scene(n=1, dur=6.0):
    return {"sceneNumber": n, "targetDurationSec": dur, "subtitleTiming": {"cues": []}}


def test_prepare_preserves_video_facts_and_keeps_editorial_duration(tmp_path):
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    assets = [{
        "sceneNumber": 1,
        "segments": [{
            "segmentIndex": 1, "path": "assets/clip.mp4", "durationFraction": 1.0,
            "mediaKind": "VIDEO", "mimeType": "video/mp4",
            "sourceDurationSec": 4.0, "fps": 30.0,
        }],
    }]
    rt = build_render_timeline([_scene(1, 6.0)], assets, scenes_dir, scene_audio_durations={1: 5.65})
    assert rt[0]["mediaKind"] == "VIDEO"
    assert rt[0]["mimeType"] == "video/mp4"
    assert rt[0]["sourceDurationSec"] == 4.0
    assert rt[0]["fps"] == 30.0
    # Editorial duration comes from audio/timeline, never from the source clip.
    assert rt[0]["durationSec"] != 4.0
    assert rt[0]["durationSec"] == pytest.approx(6.0, abs=0.05)


def test_prepare_missing_media_kind_defaults_to_image(tmp_path):
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    assets = [{
        "sceneNumber": 1,
        "segments": [{"segmentIndex": 1, "path": "assets/a.jpg", "durationFraction": 1.0}],
    }]
    rt = build_render_timeline([_scene(1, 6.0)], assets, scenes_dir, scene_audio_durations={1: 5.65})
    assert rt[0]["mediaKind"] == "IMAGE"


def test_prepare_mixed_timeline_preserves_order_without_gaps(tmp_path):
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    assets = [{
        "sceneNumber": 1,
        "segments": [
            {"segmentIndex": 1, "path": "assets/a.mp4", "durationFraction": 0.5, "mediaKind": "VIDEO", "sourceDurationSec": 4.0},
            {"segmentIndex": 2, "path": "assets/b.jpg", "durationFraction": 0.5},
        ],
    }]
    rt = build_render_timeline([_scene(1, 12.0)], assets, scenes_dir, scene_audio_durations={1: 11.65})
    assert [e["mediaKind"] for e in rt] == ["VIDEO", "IMAGE"]
    assert rt[0]["endSec"] == pytest.approx(rt[1]["startSec"], abs=0.01)


# ── Asset validation media-aware ─────────────────────────────────────────────


def _probe_result(width, height, duration):
    return {"width": width, "height": height, "duration": duration}


def test_validate_video_asset_accepted(tmp_path, monkeypatch):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"mp4")
    monkeypatch.setattr(asset_validation, "_probe_video", lambda *a: _probe_result(1080, 1920, 8.0))
    assert asset_validation.validate_asset_file(str(p), tmp_path, video_dir=tmp_path, is_v2=True, media_kind="VIDEO") == []


def test_validate_video_asset_missing(tmp_path):
    failures = asset_validation.validate_asset_file("missing.mp4", tmp_path, video_dir=tmp_path, is_v2=True, media_kind="VIDEO")
    assert any(f["rule"] == "file_not_found" for f in failures)


def test_validate_video_asset_not_decodable(tmp_path, monkeypatch):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"garbage")
    monkeypatch.setattr(asset_validation, "_probe_video", lambda *a: None)
    failures = asset_validation.validate_asset_file(str(p), tmp_path, video_dir=tmp_path, is_v2=True, media_kind="VIDEO")
    assert any(f["rule"] == "not_decodable" for f in failures)


def test_validate_video_asset_zero_duration(tmp_path, monkeypatch):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"mp4")
    monkeypatch.setattr(asset_validation, "_probe_video", lambda *a: _probe_result(1080, 1920, 0.0))
    failures = asset_validation.validate_asset_file(str(p), tmp_path, video_dir=tmp_path, is_v2=True, media_kind="VIDEO")
    assert any(f["rule"] == "zero_duration" for f in failures)


def test_validate_video_asset_invalid_dimensions(tmp_path, monkeypatch):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"mp4")
    monkeypatch.setattr(asset_validation, "_probe_video", lambda *a: _probe_result(0, 0, 8.0))
    failures = asset_validation.validate_asset_file(str(p), tmp_path, video_dir=tmp_path, is_v2=True, media_kind="VIDEO")
    assert any(f["rule"] == "invalid_video_dimensions" for f in failures)


def test_validate_video_asset_never_opens_pillow(tmp_path, monkeypatch):
    # A non-image file that Pillow could never decode must still validate when
    # the ffprobe path succeeds, proving the VIDEO branch never calls Pillow.
    p = tmp_path / "clip.mp4"
    p.write_text("this is not an image")
    monkeypatch.setattr(asset_validation, "_probe_video", lambda *a: _probe_result(1080, 1920, 8.0))
    assert asset_validation.validate_asset_file(str(p), tmp_path, video_dir=tmp_path, is_v2=True, media_kind="VIDEO") == []


def test_validate_image_asset_unchanged(tmp_path, monkeypatch):
    from PIL import Image

    p = tmp_path / "img.jpg"
    Image.new("RGB", (720, 720), (100, 80, 60)).save(p, "JPEG")
    monkeypatch.setattr(asset_validation, "_probe_video", lambda *a: (_ for _ in ()).throw(AssertionError("image must not probe video")))
    failures = asset_validation.validate_asset_file(str(p), tmp_path, video_dir=tmp_path, is_v2=True, media_kind="IMAGE")
    assert failures == []


# ── Bridge unresolved hardening ──────────────────────────────────────────────


def _unresolved_meta():
    return {"script": {"scenes": [{"sceneNumber": 1, "visualPlan": {"visualSequence": [{"segmentIndex": 1}]}}]}}


def test_bridge_unresolved_video_preserves_media_kind_and_capability():
    unresolved = {"sceneNumber": 1, "segmentIndex": 1, "status": "NO_RESULTS", "provider": "pexels", "mediaKind": "VIDEO", "capabilityId": "pexels.video.stock", "assetPreference": "photograph"}
    metadata = apply_visual_assets_v2_to_metadata(_unresolved_meta(), {"resolvedAssets": [], "unresolvedSegments": [unresolved]})
    seg = metadata["assets"][0]["segments"][0]
    assert seg["mediaKind"] == "VIDEO"
    assert seg["capabilityId"] == "pexels.video.stock"


def test_bridge_unresolved_missing_media_kind_defaults_image():
    unresolved = {"sceneNumber": 1, "segmentIndex": 1, "status": "NO_RESULTS", "provider": "wikimedia_commons", "assetPreference": "photograph"}
    metadata = apply_visual_assets_v2_to_metadata(_unresolved_meta(), {"resolvedAssets": [], "unresolvedSegments": [unresolved]})
    seg = metadata["assets"][0]["segments"][0]
    assert seg["mediaKind"] == "IMAGE"


# ── Manifest visualType ──────────────────────────────────────────────────────


def _write_render_meta(job: Path, media_kind: str, path: str) -> Path:
    meta = {
        "jobId": "test-manifest-video",
        "script": {"scenes": [
            {"sceneNumber": 1, "targetDurationSec": 6.0,
             "subtitleTiming": {"cues": [], "timingSource": "estimated"}},
        ]},
        "audio": {
            "provider": "edge-tts", "voice": "es-ES-AlvaroNeural", "continuous": False,
            "scenes": [{"sceneNumber": 1, "path": str(job / "scenes" / "scene-01.mp3"), "exists": True, "durationSec": 6.0}],
        },
        "assets": [
            {"sceneNumber": 1, "selected": True, "segments": [
                {"segmentIndex": 1, "path": path, "segmentValidationStatus": "PASS", "error": None, "mediaKind": media_kind},
            ]},
        ],
        "renderTimeline": [
            {"sceneNumber": 1, "segmentIndex": 1, "startSec": 0.0, "endSec": 6.0,
             "durationSec": 6.0, "beatIndex": 1, "assetType": "broll", "motionType": "static",
             "assetPath": path, "audioPath": str(job / "scenes" / "scene-01.mp3"),
             "transitionIn": "cut", "transitionOut": "fade", "subtitleCueIndexes": [], "mediaKind": media_kind},
        ],
        "status": "SUBTITLES_READY",
        "updatedAt": "2026-01-01T00:00:00Z",
        "render": {"path": str(job / "video.mp4"), "durationSeconds": 6.0},
        "subtitles": {"path": str(job / "subtitle.ass"), "format": "ass"},
    }
    meta_path = job / "metadata.json"
    meta_path.write_text(json.dumps(meta))
    return meta_path


def test_manifest_video_visual_type(tmp_path, monkeypatch):
    import sys

    import render_job as render_cli
    import shorts_creator.rendering.renderer as rj

    rj.main = render_cli.main
    job = tmp_path / "job"
    job.mkdir()
    (job / "scenes").mkdir()
    (job / "assets").mkdir()
    (job / "assets" / "clip.mp4").write_bytes(b"mp4")
    (job / "scenes" / "scene-01.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
    meta_path = _write_render_meta(job, "VIDEO", str(job / "assets" / "clip.mp4"))
    monkeypatch.setattr(sys, "argv", ["render_job.py", str(meta_path), "--skip-render", "--skip-validation", "--skip-asset-validation"])
    assert render_cli.main() == 0
    manifest = json.loads((job / "job-manifest.json").read_text())
    assert manifest["scenes"][0]["visualType"] == "video"


def test_manifest_image_visual_type(tmp_path, monkeypatch):
    import sys

    import render_job as render_cli
    import shorts_creator.rendering.renderer as rj

    rj.main = render_cli.main
    job = tmp_path / "job"
    job.mkdir()
    (job / "scenes").mkdir()
    (job / "assets").mkdir()
    (job / "assets" / "img.jpg").write_bytes(b"x")
    (job / "scenes" / "scene-01.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
    meta_path = _write_render_meta(job, "IMAGE", str(job / "assets" / "img.jpg"))
    monkeypatch.setattr(sys, "argv", ["render_job.py", str(meta_path), "--skip-render", "--skip-validation", "--skip-asset-validation"])
    assert render_cli.main() == 0
    manifest = json.loads((job / "job-manifest.json").read_text())
    assert manifest["scenes"][0]["visualType"] == "image"
