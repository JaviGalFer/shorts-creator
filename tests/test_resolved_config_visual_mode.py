"""resolvedConfig.visuals effective visual-mode metadata tests.

These use render_job with skip flags so only the resolvedConfig construction
runs offline (no Docker, no network).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[1]
if str(_PROJECT / "bin") not in sys.path:
    sys.path.insert(0, str(_PROJECT / "bin"))


def _build_meta(job, asset_path):
    return {
        "jobId": "test-rvc-visuals",
        "request": {
            "duration": {"targetSec": 20, "minSec": 18, "maxSec": 22},
            "visuals": {"visualMode": "IMAGES_ONLY"},
        },
        "script": {"scenes": [{"sceneNumber": 1, "targetDurationSec": 5.0, "subtitleTiming": {"cues": [], "timingSource": "estimated"}}]},
        "audio": {"provider": "edge-tts", "voice": "x", "continuous": False, "scenes": [{"sceneNumber": 1, "path": str(job / "scenes" / "scene-01.mp3"), "exists": True, "durationSec": 5.0}]},
        "assets": [{"sceneNumber": 1, "selected": True, "segments": [{"segmentIndex": 1, "path": asset_path, "segmentValidationStatus": "PASS", "error": None, "mediaKind": "IMAGE", "provider": "pexels", "score": 60.0, "queryUsed": "q"}]}],
        "renderTimeline": [{"sceneNumber": 1, "segmentIndex": 1, "startSec": 0.0, "endSec": 5.0, "durationSec": 5.0, "beatIndex": 1, "assetType": "broll", "motionType": "static", "assetPath": asset_path, "audioPath": str(job / "scenes" / "scene-01.mp3"), "transitionIn": "cut", "transitionOut": "fade", "subtitleCueIndexes": [], "mediaKind": "IMAGE"}],
        "status": "SUBTITLES_READY",
        "updatedAt": "2026-01-01T00:00:00Z",
        "render": {"path": str(job / "video.mp4"), "durationSeconds": 5.0},
        "subtitles": {"path": str(job / "subtitle.ass"), "format": "ass"},
    }


def _run_renderer(visuals, tmp_path, monkeypatch):
    import render_job as render_cli
    import shorts_creator.rendering.renderer as rj

    rj.main = render_cli.main
    job = tmp_path / "job"
    job.mkdir()
    (job / "scenes").mkdir()
    (job / "assets").mkdir()
    (job / "assets" / "a.jpg").write_bytes(b"x")
    (job / "scenes" / "scene-01.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
    meta = _build_meta(job, "assets/a.jpg")
    meta["request"]["visuals"] = visuals
    meta_path = job / "metadata.json"
    meta_path.write_text(json.dumps(meta))
    monkeypatch.setattr(sys, "argv", ["render_job.py", str(meta_path), "--skip-render", "--skip-validation", "--skip-asset-validation"])
    assert render_cli.main() == 0
    return json.loads(meta_path.read_text())


def test_missing_visual_mode_effective_images_only(tmp_path, monkeypatch):
    saved = _run_renderer({}, tmp_path, monkeypatch)
    visuals = saved["resolvedConfig"]["visuals"]
    assert visuals["visualMode"] == "IMAGES_ONLY"
    assert visuals["mode"] == "images"


def test_explicit_images_only(tmp_path, monkeypatch):
    saved = _run_renderer({"visualMode": "IMAGES_ONLY"}, tmp_path, monkeypatch)
    visuals = saved["resolvedConfig"]["visuals"]
    assert visuals["visualMode"] == "IMAGES_ONLY"
    assert visuals["mode"] == "images"


def test_legacy_mode_images_preserved(tmp_path, monkeypatch):
    saved = _run_renderer({"mode": "images"}, tmp_path, monkeypatch)
    visuals = saved["resolvedConfig"]["visuals"]
    assert visuals["visualMode"] == "IMAGES_ONLY"
    assert visuals["mode"] == "images"


def test_videos_only_has_no_legacy_mode(tmp_path, monkeypatch):
    saved = _run_renderer({"visualMode": "VIDEOS_ONLY"}, tmp_path, monkeypatch)
    visuals = saved["resolvedConfig"]["visuals"]
    assert visuals["visualMode"] == "VIDEOS_ONLY"
    assert "mode" not in visuals


def test_auto_has_no_legacy_mode(tmp_path, monkeypatch):
    saved = _run_renderer({"visualMode": "AUTO"}, tmp_path, monkeypatch)
    visuals = saved["resolvedConfig"]["visuals"]
    assert visuals["visualMode"] == "AUTO"
    assert "mode" not in visuals


def test_mixed_has_no_legacy_mode(tmp_path, monkeypatch):
    saved = _run_renderer({"visualMode": "MIXED"}, tmp_path, monkeypatch)
    visuals = saved["resolvedConfig"]["visuals"]
    assert visuals["visualMode"] == "MIXED"
    assert "mode" not in visuals


def test_request_visuals_preserved(tmp_path, monkeypatch):
    saved = _run_renderer({"visualMode": "VIDEOS_ONLY", "allowGeneratedImages": False}, tmp_path, monkeypatch)
    assert saved["request"]["visuals"]["visualMode"] == "VIDEOS_ONLY"
    assert saved["request"]["visuals"]["allowGeneratedImages"] is False
    assert "mode" not in saved["request"]["visuals"]


def test_conflicting_visuals_fall_back_images_only(tmp_path, monkeypatch):
    saved = _run_renderer({"mode": "images", "visualMode": "VIDEOS_ONLY"}, tmp_path, monkeypatch)
    visuals = saved["resolvedConfig"]["visuals"]
    assert visuals["visualMode"] == "IMAGES_ONLY"
    assert visuals["mode"] == "images"
