"""Focused orchestration tests for bounded generic post-TTS duration fitting."""

import json
import subprocess
from pathlib import Path

import pytest

from shorts_creator.pipeline import orchestrator
from shorts_creator.rendering.preparer import project_render_duration


def _metadata(tmp_path: Path, durations=(4.0, 4.0, 4.0, 4.0, 4.0)) -> Path:
    scenes = []
    audio = []
    for number, duration in enumerate(durations, start=1):
        scenes.append({"sceneNumber": number, "voiceover": "uno dos tres cuatro cinco seis siete ocho nueve diez once", "visualPlan": {"_schemaVersion": 2}})
        audio.append({"sceneNumber": number, "durationSec": duration, "activeAudioDurationSec": duration})
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps({
        "jobId": "duration-fit", "status": "AUDIO_READY",
        "request": {"duration": {"targetSec": 30, "minSec": 27, "maxSec": 30}, "visuals": {}},
        "script": {"scenes": scenes}, "audio": {"continuous": False, "scenes": audio},
    }))
    return path


def test_projection_uses_active_audio_plus_tail():
    scenes = [{"sceneNumber": 1}, {"sceneNumber": 2}]
    audio = {"scenes": [
        {"sceneNumber": 1, "durationSec": 10, "activeAudioDurationSec": 9.5},
        {"sceneNumber": 2, "durationSec": 10},
    ]}
    assert project_render_duration(scenes, audio, tail_pause_sec=0.35) == 20.2


def test_in_range_audio_requires_no_repair(tmp_path):
    path = _metadata(tmp_path, (5.5, 5.5, 5.5, 5.5, 5.5))
    ok, reason = orchestrator._run_duration_fitting(str(path), verbose=False)
    data = json.loads(path.read_text())
    assert ok and reason is None
    assert data["durationFitting"]["repairAttempts"] == 0
    assert data["durationFitting"]["status"] == "PASS"


def test_short_audio_repairs_forces_regeneration_then_passes(tmp_path, monkeypatch):
    path = _metadata(tmp_path)
    repaired = {"scenes": json.loads(path.read_text())["script"]["scenes"]}
    calls = []

    def fake_repair(script, **kwargs):
        calls.append(kwargs)
        return repaired, []

    def fake_run(cmd, verbose, stage):
        assert stage == "audio"
        assert "--force-regenerate" in cmd
        data = json.loads(path.read_text())
        for entry in data["audio"]["scenes"]:
            entry["activeAudioDurationSec"] = 5.2
            entry["durationSec"] = 5.2
        data["status"] = "AUDIO_READY"
        path.write_text(json.dumps(data))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(orchestrator, "repair_voiceover_duration", fake_repair)
    monkeypatch.setattr(orchestrator, "run_subprocess", fake_run)
    ok, reason = orchestrator._run_duration_fitting(str(path), verbose=False)
    data = json.loads(path.read_text())
    assert ok and reason is None
    assert calls[0]["direction"] == "EXPAND"
    assert data["durationFitting"]["repairAttempts"] == 1
    assert data["durationFitting"]["history"][0]["decision"] == "EXPAND"
    assert all(target >= 7 for target in calls[0]["scene_word_targets"])


def test_exhausted_repairs_blocks_prepare(tmp_path, monkeypatch):
    path = _metadata(tmp_path)
    monkeypatch.setattr(orchestrator, "repair_voiceover_duration", lambda script, **kw: (script, []))
    monkeypatch.setattr(
        orchestrator, "run_subprocess",
        lambda cmd, verbose, stage: subprocess.CompletedProcess(cmd, 0, "", ""),
    )
    ok, reason = orchestrator._run_duration_fitting(str(path), verbose=False)
    data = json.loads(path.read_text())
    assert not ok
    assert reason == "DURATION_FITTING_EXHAUSTED"
    assert data["status"] == "REVIEW_REQUIRED"
    assert "DURATION_FITTING_EXHAUSTED" in data["reviewReasons"]
    assert data["durationFitting"]["repairAttempts"] == 2


def test_invalid_repair_blocks_without_audio_regeneration(tmp_path, monkeypatch):
    path = _metadata(tmp_path)
    monkeypatch.setattr(orchestrator, "repair_voiceover_duration", lambda script, **kw: (None, [{"code": "bad"}]))
    ok, reason = orchestrator._run_duration_fitting(str(path), verbose=False)
    data = json.loads(path.read_text())
    assert not ok
    assert reason == "DURATION_FITTING_REPAIR_FAILED"
    assert data["status"] == "REVIEW_REQUIRED"


def test_real_regression_decision_is_expand_approximately_75_words():
    from shorts_creator.contracts.duration import evaluate_duration_fitting
    result = evaluate_duration_fitting(
        current_word_count=52, projected_duration_sec=20.813,
        target_sec=30, min_sec=27, max_sec=30,
    )
    assert result["decision"] == "EXPAND"
    assert result["proposedWords"] == 75
